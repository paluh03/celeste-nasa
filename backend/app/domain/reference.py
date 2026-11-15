"""Referencia poblacional de ultrasonido cuantitativo de calcaneo.

Datos: Shin et al. (2005), Journal of Korean Medical Science, Tablas 2 y 3
(n = 3.053 adultos coreanos), agrupados por sexo y rango de edad.

Se guardan como artefacto versionado en ``app/data/reference_ultrasound.json``
y se regeneran con ``python -m app.scripts.build_reference``.

Aqui no hay HTTP ni base de datos: solo seleccion de grupo y puntajes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "reference_ultrasound.json"

STATUS_UNKNOWN = "unknown"
STATUS_NORMAL = "normal"
STATUS_OSTEOPENIA = "osteopenia"
STATUS_OSTEOPOROSIS = "osteoporosis"

_STATUS_RANK = {
    STATUS_UNKNOWN: 0,
    STATUS_NORMAL: 1,
    STATUS_OSTEOPENIA: 2,
    STATUS_OSTEOPOROSIS: 3,
}

YOUNG_BAND_MIN = 20


@dataclass(frozen=True)
class ReferenceGroup:
    sex: str
    age_min: int
    age_max: int
    age_band: str
    n: int
    age_mean: float
    bua_mean: float
    bua_sd: float
    sos_mean: float
    sos_sd: float


@dataclass(frozen=True)
class ReferenceMatch:
    """Grupo del astronauta y grupo joven del mismo sexo (para el T-score)."""

    group: ReferenceGroup
    young: ReferenceGroup
    age: int
    clamped: bool


@dataclass(frozen=True)
class MetricScore:
    mean: float
    sd: float
    z: float | None
    t: float | None
    status: str


@dataclass(frozen=True)
class ReferenceMetadata:
    source: str
    population: str
    bua_unit: str
    sos_unit: str


@lru_cache(maxsize=1)
def _load() -> tuple[list[ReferenceGroup], ReferenceMetadata]:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    groups = [
        ReferenceGroup(
            sex=item["sex"],
            age_min=int(item["age_min"]),
            age_max=int(item["age_max"]),
            age_band=item["age_band"],
            n=int(item["n"]),
            age_mean=float(item["age_mean"]),
            bua_mean=float(item["bua_mean"]),
            bua_sd=float(item["bua_sd"]),
            sos_mean=float(item["sos_mean"]),
            sos_sd=float(item["sos_sd"]),
        )
        for item in payload["groups"]
    ]
    metadata = ReferenceMetadata(
        source=payload.get("source", ""),
        population=payload.get("population", ""),
        bua_unit=payload.get("bua_unit", "dB/MHz"),
        sos_unit=payload.get("sos_unit", "m/s"),
    )
    return groups, metadata


def groups() -> list[ReferenceGroup]:
    return list(_load()[0])


def metadata() -> ReferenceMetadata:
    return _load()[1]


def age_at(birth_date: date | None, on: date) -> int | None:
    """Edad cumplida a la fecha de la medicion (no a hoy)."""
    if birth_date is None:
        return None
    years = on.year - birth_date.year
    if (on.month, on.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def match(sex: str | None, age: int | None) -> ReferenceMatch | None:
    """Grupo de referencia por sexo y edad; clamp en los extremos 20-74."""
    if not sex or age is None:
        return None
    normalized = sex.strip().lower()
    candidates = [group for group in _load()[0] if group.sex == normalized]
    if not candidates:
        return None

    candidates.sort(key=lambda group: group.age_min)
    selected = next(
        (group for group in candidates if group.age_min <= age <= group.age_max),
        None,
    )
    clamped = selected is None
    if selected is None:
        selected = candidates[0] if age < candidates[0].age_min else candidates[-1]

    young = next(
        (group for group in candidates if group.age_min == YOUNG_BAND_MIN),
        candidates[0],
    )
    return ReferenceMatch(group=selected, young=young, age=age, clamped=clamped)


def z_score(value: float, mean: float, sd: float) -> float | None:
    if sd <= 0:
        return None
    return (value - mean) / sd


def t_score(value: float, young_mean: float, young_sd: float) -> float | None:
    return z_score(value, young_mean, young_sd)


def classify(
    t: float | None,
    osteopenia: float = -1.0,
    osteoporosis: float = -2.5,
) -> str:
    """Convencion OMS sobre el T-score."""
    if t is None:
        return STATUS_UNKNOWN
    if t <= osteoporosis:
        return STATUS_OSTEOPOROSIS
    if t < osteopenia:
        return STATUS_OSTEOPENIA
    return STATUS_NORMAL


def worst_status(*statuses: str) -> str:
    return max(statuses, key=lambda status: _STATUS_RANK.get(status, 0), default=STATUS_UNKNOWN)


def evaluate_metric(
    value: float,
    match: ReferenceMatch,
    metric: str,
    osteopenia: float = -1.0,
    osteoporosis: float = -2.5,
) -> MetricScore:
    """Calcula Z y T para BUA o SOS contra el grupo del astronauta."""
    if metric == "bua":
        mean, sd = match.group.bua_mean, match.group.bua_sd
        young_mean, young_sd = match.young.bua_mean, match.young.bua_sd
    elif metric == "sos":
        mean, sd = match.group.sos_mean, match.group.sos_sd
        young_mean, young_sd = match.young.sos_mean, match.young.sos_sd
    else:
        raise ValueError(f"unknown metric: {metric}")

    z = z_score(value, mean, sd)
    t = t_score(value, young_mean, young_sd)
    return MetricScore(mean=mean, sd=sd, z=z, t=t, status=classify(t, osteopenia, osteoporosis))
