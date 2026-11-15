"""Caso de uso del modulo de cortisol salival."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.core.i18n import t
from app.domain import cortisol
from app.domain.errors import ValidationError
from app.domain.models import Astronaut, CortisolSample
from app.domain.reference import age_at
from app.domain.schemas import (
    CortisolAssessmentOut,
    CortisolBaselineOut,
    CortisolCurvePointOut,
    CortisolRatioOut,
    CortisolReferenceOut,
    CortisolSampleCreate,
    CortisolSampleOut,
)
from app.infrastructure import repositories
from app.modules.astronauts import service as astronauts_service

MAX_UG_DL = 10.0
BONE_CROSS_WINDOW_DAYS = 14


def _to_out(row: CortisolSample, astronaut: Astronaut) -> CortisolSampleOut:
    age = age_at(astronaut.birth_date, row.measured_at.date())
    evaluation = cortisol.evaluate_sample(
        row.value_ug_dl,
        row.measured_at,
        astronaut.sex,
        age,
    )
    return CortisolSampleOut(
        id=row.id or 0,
        measured_at=row.measured_at,
        value_ug_dl=round(evaluation.value_ug_dl, 4),
        value_nmol_l=round(evaluation.value_nmol_l, 2),
        hour=round(evaluation.hour, 3),
        band=evaluation.band,
        z=round(evaluation.z, 3),
        percentile=round(evaluation.percentile, 1),
        color=evaluation.color,
        expected_median_ug_dl=round(evaluation.expected_median_ug_dl, 4),
        expected_median_nmol_l=round(evaluation.expected_median_nmol_l, 2),
        direction=evaluation.direction,
        sex_color=evaluation.sex_color,
        discordant=evaluation.discordant,
        above_manufacturer_p95=evaluation.above_manufacturer_p95,
        flags=list(evaluation.flags),
        wake_time=row.wake_time,
        mission_phase=row.mission_phase,  # type: ignore[arg-type]
        notes=row.notes,
    )


def record(
    session: Session,
    code: str,
    payload: CortisolSampleCreate,
    lang: str,
    source: str = "manual",
) -> CortisolSampleOut:
    astronaut = astronauts_service.get_one(session, code)

    if payload.measured_at > datetime.now() + timedelta(minutes=5):
        raise ValidationError("error.measured_at_future")

    value_ug_dl = cortisol.to_ug_dl(payload.value, payload.unit)
    if not (0 < value_ug_dl <= MAX_UG_DL):
        raise ValidationError("error.cortisol_range", max=MAX_UG_DL)

    row = repositories.add_cortisol_sample(
        session=session,
        astronaut_id=astronaut.id or 0,
        measured_at=payload.measured_at.replace(second=0, microsecond=0),
        value_ug_dl=value_ug_dl,
        input_value=payload.value,
        input_unit=payload.unit,
        wake_time=payload.wake_time,
        mission_phase=payload.mission_phase,
        notes=payload.notes,
        source=source,
    )
    return _to_out(row, astronaut)


def reference_out() -> CortisolReferenceOut:
    ref = cortisol.reference()
    return CortisolReferenceOut(
        method=ref.method,
        source=ref.source,
        sigma_ln=ref.all_sexes.sigma_ln,
        green_z=ref.green_z,
        yellow_z=ref.yellow_z,
        conversion_nmol_per_ug=ref.conversion,
        age_range=[ref.age_min, ref.age_max],
        curve=[
            CortisolCurvePointOut(
                hour=hour,
                median_ug_dl=round(median_value, 4),
                p10_ug_dl=round(low, 4),
                p90_ug_dl=round(high, 4),
            )
            for hour, median_value, low, high in cortisol.reference_curve()
        ],
    )


def build_assessment(
    session: Session,
    code: str,
    lang: str,
    days: int | None = None,
) -> CortisolAssessmentOut:
    astronaut = astronauts_service.get_one(session, code)
    rows = repositories.list_cortisol_samples(session, astronaut.id or 0)

    if days and rows:
        cutoff = rows[-1].measured_at - timedelta(days=days)
        rows = [row for row in rows if row.measured_at >= cutoff]

    samples = [_to_out(row, astronaut) for row in rows]
    pairs = [(row.measured_at, row.value_ug_dl) for row in rows]
    current = samples[-1] if samples else None

    ratio = None
    ratio_data = cortisol.evening_night_ratio(pairs)
    if ratio_data is not None:
        day, value, reading, afternoon, night = ratio_data
        ratio = CortisolRatioOut(
            date=day,
            ratio=round(value, 2),
            reading=reading,
            afternoon_ug_dl=round(afternoon, 4),
            night_ug_dl=round(night, 4),
        )

    baseline = None
    if current is not None:
        baseline_data = cortisol.personal_baseline(
            pairs,
            current.band,  # type: ignore[arg-type]
            current.value_ug_dl,
        )
        if baseline_data is not None:
            count, median_value, delta = baseline_data
            baseline = CortisolBaselineOut(
                band=current.band,
                n=count,
                median_ug_dl=round(median_value, 4),
                delta_pct=None if delta is None else round(delta, 1),
            )

    recent_cutoff = (rows[-1].measured_at if rows else datetime.now()) - timedelta(
        days=BONE_CROSS_WINDOW_DAYS
    )
    recent = [sample for sample in samples if sample.measured_at >= recent_cutoff]
    altered = [sample for sample in recent if sample.color != cortisol.COLOR_GREEN]
    night_altered = any(sample.band == "night" for sample in altered)
    bone_cross_risk = len(altered) >= 2 and (night_altered or len(altered) >= 3)

    warnings: list[str] = []
    ref = cortisol.reference()
    if current is not None:
        if "age_out_of_range" in current.flags:
            warnings.append(t(lang, "cortisol.warning.age", min=ref.age_min, max=ref.age_max))
        if current.discordant:
            warnings.append(t(lang, "cortisol.warning.discordant"))
    if bone_cross_risk:
        warnings.append(
            t(
                lang,
                "cortisol.warning.bone_cross",
                count=len(altered),
                days=BONE_CROSS_WINDOW_DAYS,
            )
        )

    return CortisolAssessmentOut(
        astronaut=astronauts_service.to_out(astronaut),
        samples=samples,
        current=current,
        ratio=ratio,
        personal_baseline=baseline,
        bone_cross_risk=bone_cross_risk,
        warnings=warnings,
        reference=reference_out(),
    )
