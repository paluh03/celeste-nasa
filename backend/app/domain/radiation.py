"""Motor de clasificacion de radiacion (TEPC) por capas A/B/C.

La referencia se genera desde el export del TEPC con
``python -m app.scripts.build_radiation_reference``. Todo aqui es puro: no hay
HTTP ni base de datos.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "radiation_reference.json"

COLOR_GREEN = 1
COLOR_YELLOW = 2
COLOR_RED = 3

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient"
STATUS_INVALID = "invalid"

EQ_MIN = 0.001
EQ_MAX = 100_000.0
DOSE_MIN = 0.001
DOSE_MAX = 1_000.0
MAX_GAP_MIN = 60.0
Q_RANGE = (1.2, 3.5)


@dataclass(frozen=True)
class MetricStats:
    n: int
    p50: float
    p95: float
    p99: float
    median_ln: float
    mad_ln: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class Stratum:
    region: str
    hour: int | None
    module: str | None
    epoch: str | None
    n: int
    below_min_n: bool
    eq: MetricStats | None
    dose: MetricStats | None


@dataclass(frozen=True)
class DailyStats:
    n: int
    insufficient: bool
    total_mean: float | None
    p95: float | None
    p99: float | None


@dataclass(frozen=True)
class ReferenceData:
    source: str
    product: str
    period: dict
    variables: list[str]
    strata: list[Stratum]
    daily: dict[str, DailyStats]
    limits: dict[str, float]
    thresholds: dict[str, float]
    min_cell_n: int
    notes: str


@dataclass(frozen=True)
class Layer:
    color: int | None
    status: str
    value: float | None = None
    p95: float | None = None
    p99: float | None = None
    fraction: float | None = None
    detail: str = ""


def _metric(payload: dict | None) -> MetricStats | None:
    if not payload:
        return None
    return MetricStats(
        n=int(payload["n"]),
        p50=float(payload["p50"]),
        p95=float(payload["p95"]),
        p99=float(payload["p99"]),
        median_ln=float(payload["median_ln"]),
        mad_ln=float(payload["mad_ln"]),
        minimum=float(payload["min"]),
        maximum=float(payload["max"]),
    )


@lru_cache(maxsize=1)
def reference() -> ReferenceData:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    strata = [
        Stratum(
            region=item["region"],
            hour=item.get("hour"),
            module=item.get("module"),
            epoch=item.get("epoch"),
            n=int(item["n"]),
            below_min_n=bool(item.get("below_min_n", False)),
            eq=_metric(item.get("eq")),
            dose=_metric(item.get("dose")),
        )
        for item in payload["strata"]
    ]
    daily = {
        key: DailyStats(
            n=int(value["n"]),
            insufficient=bool(value["insufficient"]),
            total_mean=value.get("total_mean"),
            p95=value.get("p95"),
            p99=value.get("p99"),
        )
        for key, value in payload["daily"].items()
    }
    return ReferenceData(
        source=payload["source"],
        product=payload["product"],
        period=payload["period"],
        variables=payload["variables"],
        strata=strata,
        daily=daily,
        limits={key: float(value) for key, value in payload["limits"].items()},
        thresholds={key: float(value) for key, value in payload["thresholds"].items()},
        min_cell_n=int(payload["min_cell_n"]),
        notes=payload["notes"],
    )


def _find(
    metric: str,
    region: str,
    hour: int | None,
    module: str | None,
    epoch: str | None,
) -> Stratum | None:
    ref = reference()
    for stratum in ref.strata:
        if stratum.region != region or stratum.hour != hour:
            continue
        if stratum.module != module or stratum.epoch != epoch:
            continue
        if getattr(stratum, metric) is None:
            continue
        if stratum.n < ref.min_cell_n:
            continue
        return stratum
    return None


def select_stratum(
    region: str,
    hour: int | None,
    metric: str,
    module: str | None = None,
    epoch: str | None = None,
) -> tuple[Stratum | None, bool]:
    """Retroceso jerarquico: epoca -> modulo -> hora; la region se conserva."""
    requested = (region, hour, module, epoch)
    candidates = [
        requested,
        (region, hour, module, None),
        (region, hour, None, None),
        (region, None, None, None),
    ]
    for index, (candidate_region, candidate_hour, candidate_module, candidate_epoch) in enumerate(
        candidates
    ):
        found = _find(
            metric,
            candidate_region,
            candidate_hour,
            candidate_module,
            candidate_epoch,
        )
        if found is not None:
            return found, index > 0
    general = _find(metric, "all", None, None, None)
    return general, True


def log_z(value: float, stats: MetricStats) -> float:
    spread = 1.4826 * stats.mad_ln
    if spread <= 0:
        return 0.0
    return (math.log(value) - stats.median_ln) / spread


def classify_instant(
    value: float | None,
    stats: MetricStats | None,
    recent_values: list[float] | None = None,
    persistence: int = 3,
) -> Layer:
    if value is None or value <= 0:
        return Layer(color=None, status=STATUS_INVALID, detail="invalid")
    if stats is None:
        return Layer(color=None, status=STATUS_INSUFFICIENT, value=value, detail="no_stratum")

    if value <= stats.p95:
        return Layer(
            color=COLOR_GREEN,
            status=STATUS_OK,
            value=value,
            p95=stats.p95,
            p99=stats.p99,
            detail="below_p95",
        )
    if value <= stats.p99:
        return Layer(
            color=COLOR_YELLOW,
            status=STATUS_OK,
            value=value,
            p95=stats.p95,
            p99=stats.p99,
            detail="between_p95_p99",
        )

    history = [*list(recent_values or []), value]
    sustained = len(history) >= persistence and all(
        item > stats.p99 for item in history[-persistence:]
    )
    return Layer(
        color=COLOR_RED if sustained else COLOR_YELLOW,
        status=STATUS_OK,
        value=value,
        p95=stats.p95,
        p99=stats.p99,
        detail="above_p99_sustained" if sustained else "above_p99_single",
    )


def classify_daily(
    total: float | None,
    coverage: float,
    stats: DailyStats | None,
) -> Layer:
    if total is None or coverage < 0.2:
        return Layer(color=None, status=STATUS_INSUFFICIENT, value=total, detail="no_coverage")
    if stats is None or stats.insufficient or stats.p95 is None or stats.p99 is None:
        return Layer(
            color=None,
            status=STATUS_INSUFFICIENT,
            value=total,
            detail="no_daily_reference",
        )
    if total <= stats.p95:
        color, detail = COLOR_GREEN, "below_p95"
    elif total <= stats.p99:
        color, detail = COLOR_YELLOW, "between_p95_p99"
    else:
        color, detail = COLOR_RED, "above_p99"
    return Layer(
        color=color,
        status=STATUS_OK,
        value=total,
        p95=stats.p95,
        p99=stats.p99,
        detail=detail,
    )


def fraction_color(
    fraction: float | None,
    amber: float = 0.5,
    red: float = 0.8,
) -> Layer:
    if fraction is None:
        return Layer(color=None, status=STATUS_INSUFFICIENT, detail="no_fraction")
    if fraction < amber:
        color, detail = COLOR_GREEN, "below_amber"
    elif fraction < red:
        color, detail = COLOR_YELLOW, "amber"
    else:
        color, detail = COLOR_RED, "red"
    return Layer(color=color, status=STATUS_OK, fraction=fraction, detail=detail)


def classify_cumulative(f30: float | None, f_career: float | None) -> Layer:
    ref = reference()
    amber = ref.thresholds.get("fraction_amber", 0.5)
    red = ref.thresholds.get("fraction_red", 0.8)
    fractions = [value for value in (f30, f_career) if value is not None]
    if not fractions:
        return Layer(color=None, status=STATUS_INSUFFICIENT, detail="no_cumulative")
    worst = max(fractions)
    layer = fraction_color(worst, amber, red)
    return Layer(
        color=layer.color,
        status=layer.status,
        fraction=worst,
        detail=layer.detail,
    )


def worst_color(*colors: int | None) -> int | None:
    present = [color for color in colors if color is not None]
    return max(present) if present else None


def integrate_msv(
    readings: list[tuple[datetime, float]],
    start: datetime | None = None,
    end: datetime | None = None,
) -> float:
    """Integra tasa equivalente (uSv/min) por trapecios, con tope de hueco."""
    points = sorted(
        (
            (moment, value)
            for moment, value in readings
            if (start is None or moment >= start) and (end is None or moment <= end)
        ),
        key=lambda item: item[0],
    )
    if len(points) < 2:
        return 0.0
    total = 0.0
    for (previous_time, previous_value), (current_time, current_value) in zip(
        points, points[1:], strict=False
    ):
        minutes = (current_time - previous_time).total_seconds() / 60.0
        minutes = min(minutes, MAX_GAP_MIN)
        if minutes <= 0:
            continue
        total += 0.5 * (previous_value + current_value) * minutes
    return total / 1000.0  # uSv -> mSv


def daily_window(
    readings: list[tuple[datetime, float]],
    day: date,
) -> tuple[float | None, float]:
    day_start = datetime.combine(day, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    inside = [(moment, value) for moment, value in readings if day_start <= moment < day_end]
    if not inside:
        return None, 0.0
    total = integrate_msv(inside, day_start, day_end)
    coverage = min(
        1.0,
        (inside[-1][0] - inside[0][0]).total_seconds() / 60.0 / 1440.0,
    )
    return total, coverage


def q_factor(eq_rate: float, dose_rate: float | None) -> float | None:
    if dose_rate is None or dose_rate <= 0:
        return None
    return eq_rate / dose_rate
