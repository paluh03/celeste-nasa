"""Construye la tabla de referencia de radiacion desde un export del TEPC.

Acepta el ASCII-CDF que distribuye SPDF (lineas ``#`` + cabecera + datos) o un
CSV equivalente. Es generico: si el archivo trae DOSE, DOSE_EQ60, FLAG,
LOCATION, posicion o TIME_INTERVAL, los usa; si solo trae una tasa, construye
la referencia de esa variable.

Uso:
    uv run python -m app.scripts.build_radiation_reference
    uv run python -m app.scripts.build_radiation_reference --input otra.csv
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_INPUT = Path(__file__).resolve().parents[3] / "_local" / "data_radiacion.csv"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "radiation_reference.json"

FILL_VALUE = -1.0e30
MIN_CELL_N = 120
MIN_DAILY_N = 30
MAX_GAP_MIN = 60.0

COLUMN_ALIASES = {
    "epoch": "time",
    "time": "time",
    "datetime": "time",
    "date": "time",
    "dose": "dose",
    "avg_dose_rate": "dose",
    "dose_rate": "dose",
    "dose_eq60": "eq",
    "dose_eqv_rate": "eq",
    "avg_dose_eqv_rate": "eq",
    "time_interval": "interval",
    "latitude": "lat",
    "longitude": "lon",
    "altitude": "alt",
    "flag": "flag",
    "location": "location",
}

LIMITS = {"career_msv": 600.0, "window_30d_msv": 250.0, "spe_msv": 250.0}
THRESHOLDS = {
    "yellow_percentile": 95,
    "red_percentile": 99,
    "fraction_amber": 0.5,
    "fraction_red": 0.8,
    "persistence": 3,
    "min_cell_n": MIN_CELL_N,
}


def _normalize(text: str) -> str:
    cleaned = (
        text.strip()
        .lower()
        .replace("(", "_")
        .replace(")", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace(" ", "_")
    )
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def _canonical_column(header: str) -> str | None:
    key = _normalize(header)
    if key in COLUMN_ALIASES:
        return COLUMN_ALIASES[key]
    for prefix, canonical in COLUMN_ALIASES.items():
        if key.startswith(prefix):
            return canonical
    return None


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _number(value: str | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    if number <= FILL_VALUE:
        return None
    return number


def _quantile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    position = (len(sorted_values) - 1) * p
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def _stats(values: list[float]) -> dict | None:
    clean = [value for value in values if value is not None and value > 0]
    if not clean:
        return None
    ordered = sorted(clean)
    logs = [math.log(value) for value in clean]
    median_ln = _quantile(sorted(logs), 0.5)
    mad_ln = _quantile(sorted(abs(value - median_ln) for value in logs), 0.5)
    return {
        "n": len(clean),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
        "p50": round(_quantile(ordered, 0.50), 4),
        "p95": round(_quantile(ordered, 0.95), 4),
        "p99": round(_quantile(ordered, 0.99), 4),
        "median_ln": round(median_ln, 5),
        "mad_ln": round(mad_ln, 5),
    }


def read_samples(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#") and line.strip()
    )
    header = _split(lines[header_index])
    columns = [_canonical_column(name) for name in header]
    if "time" not in columns:
        raise SystemExit("el archivo no tiene columna de tiempo reconocible")

    samples: list[dict] = []
    for line in lines[header_index + 1 :]:
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) < len(columns):
            parts += [""] * (len(columns) - len(parts))
        row = dict(zip(columns, parts, strict=False))
        try:
            moment = _parse_time(row["time"])
        except (KeyError, ValueError):
            continue
        eq = _number(row.get("eq"))
        dose = _number(row.get("dose"))
        if eq is None and dose is None:
            continue
        interval = _number(row.get("interval"))
        samples.append(
            {
                "time": moment,
                "eq": eq,
                "dose": dose,
                "interval": interval if interval and interval > 0 else 1.0,
                "flag": (row.get("flag") or "").strip() or None,
                "location": (row.get("location") or "").strip() or None,
                "lat": _number(row.get("lat")),
                "lon": _number(row.get("lon")),
                "alt": _number(row.get("alt")),
            }
        )
    return samples


def _split(line: str) -> list[str]:
    return [part.strip() for part in line.split(",")]


def _stratum(samples: list[dict], metric: str, region, hour, module, epoch) -> dict | None:
    selected = [
        sample
        for sample in samples
        if sample[metric] is not None
        and (region is None or (sample["flag"] or "all") == region)
        and (hour is None or sample["time"].hour == hour)
        and (module is None or sample["location"] == module)
        and (epoch is None or str(sample["time"].year) == epoch)
    ]
    stats = _stats([sample[metric] for sample in selected])
    if stats is None:
        return None
    return {
        "region": region or "all",
        "hour": hour,
        "module": module,
        "epoch": epoch,
        "n": stats["n"],
        "below_min_n": stats["n"] < MIN_CELL_N,
        metric: stats,
    }


def build(path: Path) -> dict:
    samples = read_samples(path)
    if not samples:
        raise SystemExit("no se encontraron muestras validas")

    samples.sort(key=lambda item: item["time"])
    has_eq = any(sample["eq"] is not None for sample in samples)
    has_dose = any(sample["dose"] is not None for sample in samples)
    metrics = [name for name, present in (("eq", has_eq), ("dose", has_dose)) if present]

    regions = sorted({sample["flag"] for sample in samples if sample["flag"]} - {None})
    modules = sorted({sample["location"] for sample in samples if sample["location"]} - {None})
    epochs = sorted({str(sample["time"].year) for sample in samples})

    strata: list[dict] = []
    seen: set[tuple] = set()

    def add(stratum: dict | None) -> None:
        if stratum is None:
            return
        metric = "eq" if "eq" in stratum else "dose"
        key = (metric, stratum["region"], stratum["hour"], stratum["module"], stratum["epoch"])
        if key in seen:
            return
        seen.add(key)
        strata.append(stratum)

    for metric in metrics:
        add(_stratum(samples, metric, None, None, None, None))
        for region in regions or ["all"]:
            add(_stratum(samples, metric, region, None, None, None))
            for hour in range(24):
                add(_stratum(samples, metric, region, hour, None, None))
        for module in modules:
            add(_stratum(samples, metric, None, None, module, None))
        for epoch in epochs:
            add(_stratum(samples, metric, None, None, None, epoch))

    # Referencia diaria: solo con cobertura suficiente y varios dias.
    by_day: dict[str, dict] = {}
    for sample in samples:
        day = sample["time"].date().isoformat()
        bucket = by_day.setdefault(day, {"eq": [], "dose": [], "interval": 0.0})
        minutes = sample["interval"]
        bucket["interval"] += minutes
        if sample["eq"] is not None:
            bucket["eq"].append(sample["eq"] * minutes)
        if sample["dose"] is not None:
            bucket["dose"].append(sample["dose"] * minutes)

    daily: dict[str, dict] = {}
    complete_days = [day for day, bucket in by_day.items() if bucket["interval"] / 1440.0 >= 0.8]
    for metric in metrics:
        totals = [
            sum(bucket[metric]) / 1000.0  # uSv o uGy -> mSv/mGy
            for day, bucket in by_day.items()
            if bucket[metric] and bucket["interval"] / 1440.0 >= 0.8
        ]
        stats = _stats([value for value in totals if value > 0])
        daily[metric] = {
            "n": len(totals),
            "insufficient": len(totals) < MIN_DAILY_N,
            "total_mean": round(sum(totals) / len(totals), 4) if totals else None,
            "p95": stats["p95"] if stats and len(totals) >= MIN_DAILY_N else None,
            "p99": stats["p99"] if stats and len(totals) >= MIN_DAILY_N else None,
        }

    return {
        "source": path.name,
        "product": "ISS TEPC (CDF ASCII export)",
        "generated_from": str(path),
        "variables": [
            label
            for label, present in (
                ("AVG_DOSE_EQV_RATE (uSv/min)", has_eq),
                ("AVG_DOSE_RATE (uGy/min)", has_dose),
            )
            if present
        ],
        "period": {
            "start": samples[0]["time"].isoformat(),
            "end": samples[-1]["time"].isoformat(),
            "days": len(complete_days),
            "days_span": len(by_day),
        },
        "min_cell_n": MIN_CELL_N,
        "strata": strata,
        "daily": daily,
        "limits": LIMITS,
        "thresholds": THRESHOLDS,
        "notes": (
            "Referencia empirica en escala logaritmica. Si una celda tiene menos de "
            f"{MIN_CELL_N} muestras, el clasificador retrocede a un estrato mas general. "
            "La dosis diaria solo se clasifica cuando hay suficientes dias con cobertura >= 80%."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera la referencia de radiacion")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    payload = build(args.input)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    usable = [stratum for stratum in payload["strata"] if not stratum["below_min_n"]]
    print(f"escrito {OUTPUT}")
    period = payload["period"]
    print(f"periodo: {period['start']} -> {period['end']} ({period['days']} dia/s)")
    print(f"estratos: {len(payload['strata'])} (utilizables: {len(usable)})")
    for stratum in usable[:6]:
        metric = "eq" if "eq" in stratum else "dose"
        stats = stratum[metric]
        print(
            f"  {metric} region={stratum['region']} hour={stratum['hour']} "
            f"n={stats['n']} p50={stats['p50']} p95={stats['p95']} p99={stats['p99']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
