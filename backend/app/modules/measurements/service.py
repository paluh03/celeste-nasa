"""Caso de uso: registrar y listar mediciones."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.core import events
from app.core.config import settings
from app.core.i18n import t
from app.domain import bone
from app.domain.errors import NotFoundError, ValidationError
from app.domain.models import Measurement
from app.infrastructure import repositories


def thresholds() -> bone.Thresholds:
    return bone.Thresholds(
        uv_coef=settings.bv_tv_uv_coef,
        bua_coef=settings.bv_tv_bua_coef,
        intercept=settings.bv_tv_intercept,
        risk_rate=settings.level_risk_rate,
        alert_rate=settings.level_alert_rate,
        alert_cumulative=settings.level_alert_cumulative,
        bua_min=settings.bua_min,
        bua_max=settings.bua_max,
        uv_min=settings.uv_min,
        uv_max=settings.uv_max,
        att_min=settings.att_min,
        att_max=settings.att_max,
    )


def ensure_astronaut(session: Session, code: str):
    astronaut = repositories.get_astronaut(session, code.upper())
    if astronaut is None:
        raise NotFoundError("error.not_found", code=code)
    return astronaut


def validate_payload(
    measured_on: date,
    bua: float,
    uv: float,
    att: float | None,
    lang: str,
) -> None:
    errors = bone.validate_sample(bua, uv, att, thresholds())
    if errors:
        first = errors[0]
        raise ValidationError(str(first["key"]), **dict(first["params"]))  # type: ignore[arg-type]


def record(
    session: Session,
    code: str,
    measured_on: date,
    site: str,
    bua: float,
    uv: float,
    att: float | None,
    lang: str,
    source: str = "manual",
) -> Measurement:
    astronaut = ensure_astronaut(session, code)
    validate_payload(measured_on, bua, uv, att, lang)

    existing = repositories.list_measurements(session, astronaut.id or 0, site=site)
    if existing:
        baseline_day = existing[0].measured_on
        if measured_on <= baseline_day:
            raise ValidationError("error.date_before_baseline", baseline=baseline_day.isoformat())

    measurement = repositories.add_measurement(
        session=session,
        astronaut_id=astronaut.id or 0,
        measured_on=measured_on,
        site=site,
        bua=bua,
        uv=uv,
        att=att,
        source=source,
    )
    events.bus.publish(
        "measurement.created",
        {"astronaut_code": astronaut.code, "site": site},
    )
    return measurement


def list_for(
    session: Session,
    code: str,
    site: str | None = None,
    since: date | None = None,
) -> list[Measurement]:
    astronaut = ensure_astronaut(session, code)
    return repositories.list_measurements(session, astronaut.id or 0, site=site, since=since)


def translate_validation_error(lang: str, key: str, **params) -> str:
    return t(lang, key, **params)
