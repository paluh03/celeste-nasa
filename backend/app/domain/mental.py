"""Motor de salud mental: NASA-TLX, DMRS, EWMA y carga alostatica (ALI).

Funciones puras. El estado se guarda como insumos (tareas y estado de animo) y
toda la curva se recalcula al leer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, pstdev

ALPHA = 0.35
BETA_WORKLOAD = 0.55
BETA_MOOD = 0.45
SLEEP_DEBT_PENALTY = 8.0
MIN_STD_FLOOR = 5.0
DEFAULT_MU_WL = 50.0
DEFAULT_MU_DMRS = 75.0
BASELINE_WINDOW_DAYS = 7

DIMENSIONS = ("MD", "PD", "TD", "OP", "EF", "FR")

MOOD_WEIGHTS = {
    "m1_sleep": 0.15,
    "m2_vigor": 0.15,
    "m3_calm": 0.10,
    "m4_cohesion": 0.10,
    "m5_tension": 0.15,
    "m6_irrit": 0.10,
    "m7_dysphoria": 0.15,
    "m8_somatic": 0.10,
}

THRESHOLDS = {
    "ali_green_max": 45.0,
    "ali_orange_max": 65.0,
    "dmrs_optimal_min": 65.0,
    "dmrs_critical_min": 45.0,
    "burnout_low_wl": 45.0,
    "burnout_low_dmrs": 50.0,
    "acute_spe_mgy": 500.0,
    "yellow_ewma_wl": 65.0,
    "yellow_dmrs": 60.0,
    "orange_zmood": -1.5,
}

ZONES = {
    "green": 1,
    "yellow": 2,
    "orange": 3,
    "red": 4,
}


@dataclass(frozen=True)
class TlxResult:
    ratings: dict[str, int]
    weights: dict[str, float]
    overall: float
    mode: str


@dataclass(frozen=True)
class MoodResult:
    pa: float
    na: float
    dmrs: float


@dataclass(frozen=True)
class DayInput:
    day: date
    mission_day: int | None
    mood: dict[str, int]
    wl_day: float
    acute_24h_dose_mgy: float | None = None


@dataclass(frozen=True)
class DayResult:
    day: date
    mission_day: int | None
    wl_day: float
    dmrs: float
    pa: float
    na: float
    z_wl: float
    z_dmrs: float
    ewma_wl: float
    ewma_mood: float
    ali: float
    sleep_debt: bool
    burnout: bool
    acute_radiation: bool
    zone: str
    color: int
    reasons: tuple[str, ...]
    m1_sleep: int


def compute_tlx(
    ratings: dict[str, int],
    tallies: dict[str, int] | None,
    mode: str,
) -> TlxResult:
    missing = [dimension for dimension in DIMENSIONS if dimension not in ratings]
    if missing:
        raise ValueError(f"missing TLX dimensions: {', '.join(missing)}")

    for dimension in DIMENSIONS:
        value = int(ratings[dimension])
        if value < 0 or value > 100 or value % 5 != 0:
            raise ValueError(f"TLX rating out of range or not step 5: {dimension}")

    if mode == "WEIGHTED_FULL":
        if tallies is None:
            raise ValueError("tallies are required in WEIGHTED_FULL")
        if sum(int(tallies.get(dimension, 0)) for dimension in DIMENSIONS) != 15:
            raise ValueError("tallies must sum exactly 15")
        weights = {dimension: int(tallies.get(dimension, 0)) / 15.0 for dimension in DIMENSIONS}
    elif mode == "RAW_FAST":
        weights = {dimension: 1.0 / 6.0 for dimension in DIMENSIONS}
    else:
        raise ValueError(f"invalid eval mode: {mode}")

    overall = sum(int(ratings[dimension]) * weights[dimension] for dimension in DIMENSIONS)
    return TlxResult(
        ratings={dimension: int(ratings[dimension]) for dimension in DIMENSIONS},
        weights=weights,
        overall=overall,
        mode=mode,
    )


def compute_mood(mood: dict[str, int]) -> MoodResult:
    m = {key: int(mood[key]) for key in MOOD_WEIGHTS}
    pa = (m["m1_sleep"] + m["m2_vigor"] + m["m3_calm"] + m["m4_cohesion"]) / 40.0 * 100.0
    na = (m["m5_tension"] + m["m6_irrit"] + m["m7_dysphoria"] + m["m8_somatic"]) / 40.0 * 100.0

    total = 0.0
    total += MOOD_WEIGHTS["m1_sleep"] * m["m1_sleep"]
    total += MOOD_WEIGHTS["m2_vigor"] * m["m2_vigor"]
    total += MOOD_WEIGHTS["m3_calm"] * m["m3_calm"]
    total += MOOD_WEIGHTS["m4_cohesion"] * m["m4_cohesion"]
    total += MOOD_WEIGHTS["m5_tension"] * (10 - m["m5_tension"])
    total += MOOD_WEIGHTS["m6_irrit"] * (10 - m["m6_irrit"])
    total += MOOD_WEIGHTS["m7_dysphoria"] * (10 - m["m7_dysphoria"])
    total += MOOD_WEIGHTS["m8_somatic"] * (10 - m["m8_somatic"])

    return MoodResult(pa=pa, na=na, dmrs=total * 10.0)


def daily_workload(tasks: list[tuple[float, float]]) -> float:
    """Pondera el overall de cada tarea por su duracion (minutos)."""
    total_minutes = sum(duration for _, duration in tasks)
    if total_minutes <= 0:
        return 0.0
    return sum(overall * duration for overall, duration in tasks) / total_minutes


def ewma(previous: float, value: float, alpha: float = ALPHA) -> float:
    return alpha * value + (1.0 - alpha) * previous


def classify_zone(
    *,
    ali: float,
    dmrs: float,
    z_dmrs: float,
    ewma_wl: float,
    burnout: bool,
    acute_radiation: bool,
) -> tuple[str, int, tuple[str, ...]]:
    th = THRESHOLDS
    reasons: list[str] = []

    if ali >= th["ali_orange_max"]:
        reasons.append("ali_critical")
    if dmrs < th["dmrs_critical_min"]:
        reasons.append("mood_critical")
    if burnout:
        reasons.append("burnout")
    if acute_radiation:
        reasons.append("acute_radiation")
    if reasons:
        return "red", ZONES["red"], tuple(reasons)

    if ali >= th["ali_green_max"]:
        reasons.append("ali_accumulated")
    if dmrs < th["dmrs_optimal_min"]:
        reasons.append("mood_low")
    if z_dmrs <= th["orange_zmood"]:
        reasons.append("mood_below_baseline")
    if reasons:
        return "orange", ZONES["orange"], tuple(reasons)

    if ewma_wl >= th["yellow_ewma_wl"] and dmrs >= th["yellow_dmrs"]:
        return "yellow", ZONES["yellow"], ("acute_overload",)

    return "green", ZONES["green"], ("homeostasis",)


def build_series(days: list[DayInput]) -> list[DayResult]:
    ordered = sorted(days, key=lambda item: item.day)
    results: list[DayResult] = []
    previous_sleep: int | None = None

    for item in ordered:
        mood = compute_mood(item.mood)
        window = results[-BASELINE_WINDOW_DAYS:]

        if len(window) >= 3:
            mu_wl = mean(day.wl_day for day in window)
            sigma_wl = max(pstdev(day.wl_day for day in window), MIN_STD_FLOOR)
            mu_dmrs = mean(day.dmrs for day in window)
            sigma_dmrs = max(pstdev(day.dmrs for day in window), MIN_STD_FLOOR)
            previous_ewma_wl = window[-1].ewma_wl
            previous_ewma_mood = window[-1].ewma_mood
        else:
            mu_wl, sigma_wl = DEFAULT_MU_WL, MIN_STD_FLOOR
            mu_dmrs, sigma_dmrs = DEFAULT_MU_DMRS, MIN_STD_FLOOR
            previous_ewma_wl = item.wl_day
            previous_ewma_mood = mood.dmrs

        z_wl = (item.wl_day - mu_wl) / sigma_wl
        z_dmrs = (mood.dmrs - mu_dmrs) / sigma_dmrs

        ewma_wl = ewma(previous_ewma_wl, item.wl_day)
        ewma_mood = ewma(previous_ewma_mood, mood.dmrs)

        ali = BETA_WORKLOAD * ewma_wl + BETA_MOOD * (100.0 - ewma_mood)

        sleep_debt = bool(
            item.mood["m1_sleep"] <= 3 and previous_sleep is not None and previous_sleep <= 3
        )
        if sleep_debt:
            ali = min(100.0, ali + SLEEP_DEBT_PENALTY)

        burnout = (
            item.wl_day < THRESHOLDS["burnout_low_wl"]
            and mood.dmrs < THRESHOLDS["burnout_low_dmrs"]
        )
        acute_radiation = bool(
            item.acute_24h_dose_mgy is not None
            and item.acute_24h_dose_mgy >= THRESHOLDS["acute_spe_mgy"]
        )

        zone, color, reasons = classify_zone(
            ali=ali,
            dmrs=mood.dmrs,
            z_dmrs=z_dmrs,
            ewma_wl=ewma_wl,
            burnout=burnout,
            acute_radiation=acute_radiation,
        )

        results.append(
            DayResult(
                day=item.day,
                mission_day=item.mission_day,
                wl_day=item.wl_day,
                dmrs=mood.dmrs,
                pa=mood.pa,
                na=mood.na,
                z_wl=z_wl,
                z_dmrs=z_dmrs,
                ewma_wl=ewma_wl,
                ewma_mood=ewma_mood,
                ali=ali,
                sleep_debt=sleep_debt,
                burnout=burnout,
                acute_radiation=acute_radiation,
                zone=zone,
                color=color,
                reasons=reasons,
                m1_sleep=item.mood["m1_sleep"],
            )
        )
        previous_sleep = item.mood["m1_sleep"]

    return results
