"""Caso de uso del modulo de radiacion (TEPC)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.core.i18n import t
from app.domain import radiation
from app.domain.errors import ValidationError
from app.domain.models import RadiationReading
from app.domain.schemas import (
    RadiationAssessmentOut,
    RadiationCumulativeOut,
    RadiationLayerOut,
    RadiationReadingCreate,
    RadiationReadingOut,
    RadiationReferenceOut,
    RadiationStratumOut,
)
from app.infrastructure import repositories
from app.modules.astronauts import service as astronauts_service


def _to_out(row: RadiationReading) -> RadiationReadingOut:
    return RadiationReadingOut(
        id=row.id or 0,
        measured_at=row.measured_at,
        eq_rate_usv_min=row.eq_rate_usv_min,
        dose_rate_ugy_min=row.dose_rate_ugy_min,
        region=row.region,  # type: ignore[arg-type]
        module=row.module,
        mission_day=row.mission_day,
        planned_days=row.planned_days,
        prior_career_msv=row.prior_career_msv,
        notes=row.notes,
        source=row.source,
        q_factor=radiation.q_factor(row.eq_rate_usv_min, row.dose_rate_ugy_min),
    )


def reference_out(
    stratum: radiation.Stratum | None = None,
    used_fallback: bool = False,
) -> RadiationReferenceOut:
    ref = radiation.reference()
    daily = ref.daily.get("eq")
    return RadiationReferenceOut(
        source=ref.source,
        product=ref.product,
        period=ref.period,
        metric="eq",
        unit="uSv/min",
        stratum=(
            RadiationStratumOut(
                region=stratum.region,
                hour=stratum.hour,
                module=stratum.module,
                epoch=stratum.epoch,
            )
            if stratum is not None
            else None
        ),
        used_fallback=used_fallback,
        daily_available=bool(daily and not daily.insufficient and daily.p95 is not None),
        min_cell_n=ref.min_cell_n,
        limits=ref.limits,
        thresholds=ref.thresholds,
        notes=ref.notes,
    )


def _layer_out(layer: radiation.Layer, digits: int = 3) -> RadiationLayerOut:
    def rounded(value: float | None) -> float | None:
        return None if value is None else round(value, digits)

    return RadiationLayerOut(
        color=layer.color,
        status=layer.status,
        value=rounded(layer.value),
        p95=rounded(layer.p95),
        p99=rounded(layer.p99),
        fraction=None if layer.fraction is None else round(layer.fraction, 3),
        detail=layer.detail,
    )


def record(
    session: Session,
    code: str,
    payload: RadiationReadingCreate,
    lang: str,
    source: str = "manual",
) -> RadiationReadingOut:
    astronaut = astronauts_service.get_one(session, code)

    if payload.measured_at > datetime.now() + timedelta(minutes=5):
        raise ValidationError("error.measured_at_future")
    if not (radiation.EQ_MIN <= payload.eq_rate <= radiation.EQ_MAX):
        raise ValidationError("error.eq_range", min=radiation.EQ_MIN, max=radiation.EQ_MAX)
    if payload.dose_rate is not None and not (
        radiation.DOSE_MIN <= payload.dose_rate <= radiation.DOSE_MAX
    ):
        raise ValidationError("error.dose_range", min=radiation.DOSE_MIN, max=radiation.DOSE_MAX)

    row = repositories.add_radiation_reading(
        session=session,
        astronaut_id=astronaut.id or 0,
        measured_at=payload.measured_at.replace(second=0, microsecond=0),
        eq_rate_usv_min=payload.eq_rate,
        dose_rate_ugy_min=payload.dose_rate,
        region=payload.region,
        module=payload.module,
        mission_day=payload.mission_day,
        planned_days=payload.planned_days,
        prior_career_msv=payload.prior_career_msv,
        notes=payload.notes,
        source=source,
    )
    return _to_out(row)


def build_assessment(session: Session, code: str, lang: str) -> RadiationAssessmentOut:
    astronaut = astronauts_service.get_one(session, code)
    rows = repositories.list_radiation_readings(session, astronaut.id or 0)
    ref = radiation.reference()
    readings = [_to_out(row) for row in rows]
    current = rows[-1] if rows else None

    empty = RadiationLayerOut(
        color=None,
        status=radiation.STATUS_INSUFFICIENT,
        detail="no_data",
    )
    if current is None:
        return RadiationAssessmentOut(
            astronaut=astronauts_service.to_out(astronaut),
            readings=readings,
            current=None,
            layers={"a": empty, "b": empty, "c": empty},
            color=None,
            cumulative=RadiationCumulativeOut(
                h_30d_msv=None,
                f30=None,
                h_total_msv=None,
                projection_msv=None,
                f_career=None,
            ),
            reference=reference_out(),
            warnings=[],
        )

    stratum, used_fallback = radiation.select_stratum(
        current.region,
        current.measured_at.hour,
        "eq",
        current.module,
        str(current.measured_at.year),
    )

    recent = [
        row.eq_rate_usv_min
        for row in rows[:-1]
        if row.region == current.region
        and (current.measured_at - row.measured_at) <= timedelta(minutes=60)
    ][-2:]
    layer_a = radiation.classify_instant(
        current.eq_rate_usv_min,
        stratum.eq if stratum is not None else None,
        recent,
        persistence=int(ref.thresholds.get("persistence", 3)),
    )

    pairs = [(row.measured_at, row.eq_rate_usv_min) for row in rows]
    day_total, coverage = radiation.daily_window(pairs, current.measured_at.date())
    layer_b = radiation.classify_daily(day_total, coverage, ref.daily.get("eq"))

    h_30d = radiation.integrate_msv(pairs, start=current.measured_at - timedelta(days=30))
    h_total = radiation.integrate_msv(pairs)

    projection = 0.0
    if current.mission_day and current.planned_days and current.mission_day > 0:
        mean_daily = h_total / current.mission_day
        projection = mean_daily * max(0, current.planned_days - current.mission_day)

    f30 = None
    if len(pairs) >= 2:
        span_hours = (pairs[-1][0] - pairs[0][0]).total_seconds() / 3600.0
        if span_hours >= 24.0 and h_30d > 0:
            f30 = h_30d / ref.limits["window_30d_msv"]
    f_career = (
        (current.prior_career_msv + h_total + projection) / ref.limits["career_msv"]
        if current.prior_career_msv is not None
        else None
    )
    layer_c = radiation.classify_cumulative(f30, f_career)
    color = radiation.worst_color(layer_a.color, layer_b.color, layer_c.color)

    warnings: list[str] = []
    if used_fallback or ref.period.get("days", 0) <= 1:
        warnings.append(t(lang, "radiation.warning.fallback", days=ref.period.get("days", 0)))
    if layer_b.status == radiation.STATUS_INSUFFICIENT:
        warnings.append(t(lang, "radiation.warning.daily"))
    q = radiation.q_factor(current.eq_rate_usv_min, current.dose_rate_ugy_min)
    if q is not None and not (radiation.Q_RANGE[0] <= q <= radiation.Q_RANGE[1]):
        warnings.append(t(lang, "radiation.warning.q", value=round(q, 2)))

    return RadiationAssessmentOut(
        astronaut=astronauts_service.to_out(astronaut),
        readings=readings,
        current=_to_out(current),
        layers={
            "a": _layer_out(layer_a),
            "b": _layer_out(layer_b),
            "c": _layer_out(layer_c),
        },
        color=color,
        cumulative=RadiationCumulativeOut(
            h_30d_msv=round(h_30d, 3),
            f30=None if f30 is None else round(f30, 3),
            h_total_msv=round(h_total, 3),
            projection_msv=round(projection, 3),
            f_career=None if f_career is None else round(f_career, 3),
        ),
        reference=reference_out(stratum, used_fallback),
        warnings=warnings,
    )
