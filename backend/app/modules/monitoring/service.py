"""Caso de uso: evaluacion, referencia poblacional y estado por astronauta."""

from __future__ import annotations

import threading
import time
from datetime import date

from sqlmodel import Session

from app.core.config import settings
from app.core.i18n import level_text, t
from app.domain import bone, exercise, reference
from app.domain.models import Astronaut, Measurement
from app.domain.schemas import (
    AssessmentOut,
    AstronautOut,
    ModelInfo,
    PointOut,
    ReferenceMetricOut,
    ReferenceOut,
)
from app.infrastructure import repositories
from app.modules.astronauts.service import age_today
from app.modules.measurements.service import ensure_astronaut, thresholds

MODEL_REFERENCES = [
    "https://doi.org/10.1117/12.810048",
    "https://doi.org/10.1016/j.actaastro.2012.08.032",
    "https://doi.org/10.1121/1.4784949",
]
MODEL_FORMULA = "BV/TV = 3.89e-4 * UV - 9e-4 * BUA - 0.456"

_cache: dict[tuple[str, str, str, int | None], tuple[float, AssessmentOut]] = {}
_lock = threading.Lock()


def model_info() -> ModelInfo:
    return ModelInfo(
        version=settings.model_version,
        formula=MODEL_FORMULA,
        references=MODEL_REFERENCES,
    )


def invalidate_cache(*_args, **_kwargs) -> None:
    with _lock:
        _cache.clear()


def _classify_thresholds() -> tuple[float, float]:
    return settings.bone_t_osteopenia, settings.bone_t_osteoporosis


def _match_for(astronaut: Astronaut, on: date) -> reference.ReferenceMatch | None:
    age = reference.age_at(astronaut.birth_date, on)
    return reference.match(astronaut.sex, age)


def _to_point(
    evaluation: bone.PointEvaluation,
    lang: str,
    match: reference.ReferenceMatch | None,
) -> PointOut:
    labels = level_text(lang, evaluation.level)
    osteopenia, osteoporosis = _classify_thresholds()

    bua_z = bua_t = sos_z = sos_t = None
    status = reference.STATUS_UNKNOWN
    if match is not None:
        bua = reference.evaluate_metric(evaluation.bua, match, "bua", osteopenia, osteoporosis)
        sos = reference.evaluate_metric(evaluation.uv, match, "sos", osteopenia, osteoporosis)
        bua_z, bua_t = bua.z, bua.t
        sos_z, sos_t = sos.z, sos.t
        status = reference.worst_status(bua.status, sos.status)

    def rounded(value: float | None) -> float | None:
        return None if value is None else round(value, 3)

    return PointOut(
        measured_on=evaluation.measured_on,
        day=evaluation.day,
        month=round(evaluation.day / bone.DAYS_PER_MONTH, 2),
        bua=evaluation.bua,
        uv=evaluation.uv,
        att=evaluation.att,
        bv_tv=round(evaluation.bv_tv, 6),
        cumulative_loss_pct=round(evaluation.cumulative_loss_pct, 4),
        rate_pct_month=(
            rounded(evaluation.rate_pct_month) if evaluation.rate_pct_month is not None else None
        ),
        bv_tv_cumulative_loss_pct=round(evaluation.bv_tv_cumulative_loss_pct, 4),
        level=evaluation.level,
        level_name=labels["name"],
        level_tip=labels["tip"],
        bua_z=rounded(bua_z),
        sos_z=rounded(sos_z),
        bua_t=rounded(bua_t),
        sos_t=rounded(sos_t),
        bone_status=status,  # type: ignore[arg-type]
    )


def _reference_out(
    match: reference.ReferenceMatch,
    value_bua: float,
    value_sos: float,
) -> ReferenceOut:
    osteopenia, osteoporosis = _classify_thresholds()
    bua = reference.evaluate_metric(value_bua, match, "bua", osteopenia, osteoporosis)
    sos = reference.evaluate_metric(value_sos, match, "sos", osteopenia, osteoporosis)
    meta = reference.metadata()

    def metric(score: reference.MetricScore) -> ReferenceMetricOut:
        return ReferenceMetricOut(
            mean=score.mean,
            sd=score.sd,
            z=None if score.z is None else round(score.z, 3),
            t=None if score.t is None else round(score.t, 3),
            status=score.status,  # type: ignore[arg-type]
        )

    return ReferenceOut(
        sex=match.group.sex,  # type: ignore[arg-type]
        age=match.age,
        age_band=match.group.age_band,
        n=match.group.n,
        clamped=match.clamped,
        source=meta.source,
        population=meta.population,
        bua=metric(bua),
        sos=metric(sos),
        status=reference.worst_status(bua.status, sos.status),  # type: ignore[arg-type]
    )


def _warnings_for(
    points: list[PointOut],
    lang: str,
    current_match: reference.ReferenceMatch | None,
) -> list[str]:
    messages: list[str] = []
    for point in points:
        if not (0.0 <= point.bv_tv <= 1.0):
            messages.append(
                t(
                    lang,
                    "warning.bv_tv_out_of_range",
                    value=round(point.bv_tv, 4),
                    date=point.measured_on.isoformat(),
                )
            )
    if current_match is not None and current_match.clamped:
        messages.append(
            t(
                lang,
                "warning.reference_out_of_range",
                age=current_match.age,
                band=current_match.group.age_band,
            )
        )
    return messages


def build_assessment(
    session: Session,
    code: str,
    site: str,
    lang: str,
    window_months: int | None = None,
) -> AssessmentOut:
    cache_key = (code.upper(), site, lang, window_months)
    if settings.cache_ttl_seconds > 0:
        with _lock:
            cached = _cache.get(cache_key)
        if cached and (time.monotonic() - cached[0]) < settings.cache_ttl_seconds:
            return cached[1]

    astronaut = ensure_astronaut(session, code)
    measurements: list[Measurement] = repositories.list_measurements(
        session, astronaut.id or 0, site=site
    )
    samples = [
        bone.Sample(measured_on=m.measured_on, bua=m.bua, uv=m.uv, att=m.att) for m in measurements
    ]

    evaluations = bone.evaluate_series(samples, thresholds())
    pairs = sorted(
        zip(measurements, evaluations, strict=False), key=lambda pair: pair[0].measured_on
    )
    all_points: list[PointOut] = []
    current_match: reference.ReferenceMatch | None = None
    for index, (measurement, evaluation) in enumerate(pairs):
        match = _match_for(astronaut, measurement.measured_on)
        all_points.append(_to_point(evaluation, lang, match))
        if index == len(pairs) - 1:
            current_match = match

    visible = all_points
    if window_months and all_points:
        last_day = all_points[-1].measured_on
        limit = window_months * bone.DAYS_PER_MONTH
        visible = [p for p in all_points if (last_day - p.measured_on).days <= limit]
        if all_points[0] not in visible:
            visible = [all_points[0], *visible]

    reference_out = None
    if all_points and current_match is not None:
        reference_out = _reference_out(
            current_match,
            value_bua=all_points[-1].bua,
            value_sos=all_points[-1].uv,
        )

    assessment = AssessmentOut(
        astronaut=AstronautOut(
            code=astronaut.code,
            name=astronaut.name,
            sex=astronaut.sex,  # type: ignore[arg-type]
            birth_date=astronaut.birth_date,
            age=age_today(astronaut),
        ),
        site=site,  # type: ignore[arg-type]
        baseline=all_points[0] if all_points else None,
        points=visible,
        current=all_points[-1] if all_points else None,
        reference=reference_out,
        recommendations=exercise.for_level(all_points[-1].level if all_points else 1, lang),
        warnings=_warnings_for(all_points, lang, current_match),
        model=model_info(),
    )

    if settings.cache_ttl_seconds > 0:
        with _lock:
            _cache[cache_key] = (time.monotonic(), assessment)
    return assessment


def latest_measurement_date(session: Session, code: str, site: str) -> date | None:
    astronaut = ensure_astronaut(session, code)
    measurements = repositories.list_measurements(session, astronaut.id or 0, site=site)
    return measurements[-1].measured_on if measurements else None


def preview_point(
    session: Session,
    code: str,
    site: str,
    measured_on: date,
    bua: float,
    uv: float,
    att: float | None,
    lang: str,
) -> PointOut:
    """Evalua una muestra hipotetica contra la serie existente, sin escribir."""
    astronaut = ensure_astronaut(session, code)
    measurements: list[Measurement] = repositories.list_measurements(
        session, astronaut.id or 0, site=site
    )
    samples = [
        bone.Sample(measured_on=m.measured_on, bua=m.bua, uv=m.uv, att=m.att) for m in measurements
    ]
    candidate = bone.Sample(measured_on=measured_on, bua=bua, uv=uv, att=att)
    evaluations = bone.evaluate_series([*samples, candidate], thresholds())
    matches = [item for item in evaluations if item.measured_on == measured_on]
    return _to_point(matches[-1], lang, _match_for(astronaut, measured_on))
