"""Modelo de cortisol salival (CLIA/ECLIA) para astronautas.

Todo es puro: conversion de unidades, ritmo circadiano, z/percentil y color.
La referencia viene de ``app/data/cortisol_reference.json``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Literal

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cortisol_reference.json"

Unit = Literal["ug_dl", "nmol_l"]
Band = Literal["morning", "midday", "afternoon", "night", "predawn"]
Reading = Literal["normal", "watch", "elevated", "flat"]

COLOR_GREEN = 1
COLOR_YELLOW = 2
COLOR_RED = 3


@dataclass(frozen=True)
class MorningReference:
    n: int
    mean: float
    sd: float
    sigma_ln: float
    median: float


@dataclass(frozen=True)
class ReferenceData:
    source: str
    method: str
    conversion: float
    all_sexes: MorningReference
    male: MorningReference
    female: MorningReference
    night_median: float
    start_hour: float
    end_hour: float
    green_z: float
    yellow_z: float
    floor_after_hour: float
    floor_value: float
    p95_morning: float
    p95_afternoon: float
    p95_night: float
    ratio_normal_min: float
    ratio_normal_max: float
    ratio_watch_max: float
    age_min: int
    age_max: int


@dataclass(frozen=True)
class SampleEvaluation:
    value_ug_dl: float
    value_nmol_l: float
    hour: float
    band: Band
    z: float
    percentile: float
    color: int
    expected_median_ug_dl: float
    expected_median_nmol_l: float
    direction: Literal["high", "low"]
    sex_color: int
    discordant: bool
    above_manufacturer_p95: bool
    flags: tuple[str, ...]


@lru_cache(maxsize=1)
def reference() -> ReferenceData:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    morning = payload["morning"]

    def group(key: str) -> MorningReference:
        item = morning[key]
        return MorningReference(
            n=int(item["n"]),
            mean=float(item["mean"]),
            sd=float(item["sd"]),
            sigma_ln=float(item["sigma_ln"]),
            median=float(item["median"]),
        )

    return ReferenceData(
        source=payload["source"],
        method=payload["method"],
        conversion=float(payload["conversion_nmol_per_ug"]),
        all_sexes=group("all"),
        male=group("male"),
        female=group("female"),
        night_median=float(payload["night"]["median"]),
        start_hour=float(payload["interpolation"]["start_hour"]),
        end_hour=float(payload["interpolation"]["end_hour"]),
        green_z=float(payload["thresholds"]["green_z"]),
        yellow_z=float(payload["thresholds"]["yellow_z"]),
        floor_after_hour=float(payload["assay_floor"]["after_hour"]),
        floor_value=float(payload["assay_floor"]["value_ug_dl"]),
        p95_morning=float(payload["manufacturer_p95"]["morning"]),
        p95_afternoon=float(payload["manufacturer_p95"]["afternoon"]),
        p95_night=float(payload["manufacturer_p95"]["night"]),
        ratio_normal_min=float(payload["ratio"]["normal_min"]),
        ratio_normal_max=float(payload["ratio"]["normal_max"]),
        ratio_watch_max=float(payload["ratio"]["watch_max"]),
        age_min=int(payload["age_range"][0]),
        age_max=int(payload["age_range"][1]),
    )


def to_ug_dl(value: float, unit: Unit) -> float:
    ref = reference()
    return value if unit == "ug_dl" else value / ref.conversion


def to_nmol_l(value_ug_dl: float) -> float:
    return value_ug_dl * reference().conversion


def hour_float(moment: datetime | time) -> float:
    return moment.hour + moment.minute / 60 + moment.second / 3600


def band_for(moment: datetime | time) -> Band:
    hour = hour_float(moment)
    if 6 <= hour < 10:
        return "morning"
    if 10 <= hour < 14:
        return "midday"
    if 14 <= hour < 19:
        return "afternoon"
    if 19 <= hour < 24:
        return "night"
    return "predawn"


def _reference_for(sex: str | None) -> MorningReference:
    ref = reference()
    if sex == "male":
        return ref.male
    if sex == "female":
        return ref.female
    return ref.all_sexes


def expected_median(hour: float, morning_median: float) -> float:
    """Mediana esperada: interpola en log entre 07:30 y 21:30.

    Antes de las 06:00 y desde las 21:30 se usa el ancla nocturna; entre 06:00 y
    07:30, la mediana matutina. Asi se reproduce la tabla de franjas del
    documento sin extrapolar la recta hacia la madrugada.
    """
    ref = reference()
    if hour >= ref.end_hour or hour < 6.0:
        return ref.night_median
    if hour <= ref.start_hour:
        return morning_median
    ratio = (math.log(ref.night_median) - math.log(morning_median)) / (
        ref.end_hour - ref.start_hour
    )
    return math.exp(math.log(morning_median) + ratio * (hour - ref.start_hour))


def z_score(value_ug_dl: float, expected: float, sigma_ln: float) -> float:
    return (math.log(value_ug_dl) - math.log(expected)) / sigma_ln


def percentile(z: float) -> float:
    return 100.0 * 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def color_for(z: float) -> int:
    ref = reference()
    if abs(z) <= ref.green_z:
        return COLOR_GREEN
    if abs(z) <= ref.yellow_z:
        return COLOR_YELLOW
    return COLOR_RED


def _manufacturer_limit(hour: float) -> float:
    ref = reference()
    if hour < 12:
        return ref.p95_morning
    if hour < 20:
        return ref.p95_afternoon
    return ref.p95_night


def evaluate_sample(
    value_ug_dl: float,
    measured_at: datetime,
    sex: str | None,
    age: int | None,
) -> SampleEvaluation:
    ref = reference()
    if value_ug_dl <= 0:
        raise ValueError("cortisol must be positive")

    hour = hour_float(measured_at)
    primary = _reference_for(None)
    expected = expected_median(hour, primary.median)
    z = z_score(value_ug_dl, expected, primary.sigma_ln)
    pct = percentile(z)
    color = color_for(z)
    flags: list[str] = []

    # Piso del ensayo: despues de las 11:00 un valor muy bajo es esperado.
    if hour >= ref.floor_after_hour and value_ug_dl < ref.floor_value:
        color = COLOR_GREEN
        flags.append("assay_floor")

    # Contraste con la referencia del mismo sexo (dudoso si difiere el color).
    sex_color = color
    discordant = False
    if sex is not None:
        own = _reference_for(sex)
        own_expected = expected_median(hour, own.median)
        own_z = z_score(value_ug_dl, own_expected, own.sigma_ln)
        sex_color = color_for(own_z)
        if hour >= ref.floor_after_hour and value_ug_dl < ref.floor_value:
            sex_color = COLOR_GREEN
        discordant = sex_color != color

    if sex is not None and discordant:
        flags.append("sex_discordant")

    above_p95 = value_ug_dl > _manufacturer_limit(hour)
    if above_p95:
        flags.append("above_manufacturer_p95")

    if age is not None and not (ref.age_min <= age <= ref.age_max):
        flags.append("age_out_of_range")

    return SampleEvaluation(
        value_ug_dl=value_ug_dl,
        value_nmol_l=to_nmol_l(value_ug_dl),
        hour=hour,
        band=band_for(measured_at),
        z=z,
        percentile=pct,
        color=color,
        expected_median_ug_dl=expected,
        expected_median_nmol_l=to_nmol_l(expected),
        direction="high" if z > 0 else "low",
        sex_color=sex_color,
        discordant=discordant,
        above_manufacturer_p95=above_p95,
        flags=tuple(flags),
    )


def ratio_reading(ratio: float) -> Reading:
    ref = reference()
    if ratio < ref.ratio_normal_min:
        return "flat"
    if ratio <= ref.ratio_normal_max:
        return "normal"
    if ratio <= ref.ratio_watch_max:
        return "watch"
    return "elevated"


def evening_night_ratio(
    samples: list[tuple[datetime, float]],
) -> tuple[date, float, Reading, float, float] | None:
    """Razon 15:30/21:00 del dia mas reciente con ambas franjas."""
    by_day: dict[date, dict[str, tuple[float, float]]] = {}
    for moment, value in samples:
        band = band_for(moment)
        if band not in ("afternoon", "night"):
            continue
        target = 15.5 if band == "afternoon" else 21.0
        distance = abs(hour_float(moment) - target)
        day = moment.date()
        bucket = by_day.setdefault(day, {})
        current = bucket.get(band)
        if current is None or distance < current[1]:
            bucket[band] = (value, distance)

    for day in sorted(by_day, reverse=True):
        bucket = by_day[day]
        if "afternoon" in bucket and "night" in bucket:
            afternoon = bucket["afternoon"][0]
            night = bucket["night"][0]
            ratio = afternoon / night
            return day, ratio, ratio_reading(ratio), afternoon, night
    return None


def personal_baseline(
    samples: list[tuple[datetime, float]],
    band: Band,
    current_value: float | None = None,
) -> tuple[int, float, float | None] | None:
    """Mediana propia por franja cuando hay 3+ muestras."""
    values = [value for moment, value in samples if band_for(moment) == band]
    if len(values) < 3:
        return None
    median_value = median(values)
    delta = None
    if current_value is not None and median_value > 0:
        delta = (current_value - median_value) / median_value * 100
    return len(values), median_value, delta


def reference_curve(step: float = 0.5) -> list[tuple[float, float, float, float]]:
    """Curva 24 h de la referencia agrupada: (hora, mediana, p10, p90) en ug/dL."""
    ref = reference()
    sigma = ref.all_sexes.sigma_ln
    points: list[tuple[float, float, float, float]] = []
    hour = 0.0
    while hour <= 24.0 + 1e-9:
        median_value = expected_median(hour, ref.all_sexes.median)
        low = median_value * math.exp(-ref.green_z * sigma)
        high = median_value * math.exp(ref.green_z * sigma)
        points.append((round(hour, 2), median_value, low, high))
        hour += step
    return points
