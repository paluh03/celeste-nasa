from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_lang
from app.core.config import settings
from app.domain import reference
from app.domain.schemas import (
    AssessmentOut,
    MeasurementCreate,
    MetaOut,
    PointOut,
    ReferenceInfoOut,
    Site,
)
from app.infrastructure.database import get_session
from app.modules.cortisol import service as cortisol_service
from app.modules.measurements.service import validate_payload
from app.modules.monitoring import service
from app.modules.radiation import service as radiation_service

router = APIRouter(tags=["monitoring"])


@router.get("/astronauts/{code}/monitoring", response_model=AssessmentOut)
def get_monitoring(
    code: str,
    site: Site = "calcaneus",
    window: int | None = Query(default=None, ge=1, le=60, description="Meses visibles"),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> AssessmentOut:
    return service.build_assessment(session, code, site, lang, window)


@router.post("/astronauts/{code}/preview", response_model=PointOut)
def preview_measurement(
    code: str,
    payload: MeasurementCreate,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> PointOut:
    """Evalua una medicion sin guardarla (paso 3 del asistente)."""
    validate_payload(payload.measured_on, payload.bua, payload.uv, payload.att, lang)
    return service.preview_point(
        session=session,
        code=code,
        site=payload.site,
        measured_on=payload.measured_on,
        bua=payload.bua,
        uv=payload.uv,
        att=payload.att,
        lang=lang,
    )


@router.get("/meta", response_model=MetaOut)
def get_meta() -> MetaOut:
    meta = reference.metadata()
    bands = sorted(
        {group.age_band for group in reference.groups()},
        key=lambda band: int(band.split("-")[0]),
    )
    return MetaOut(
        app_name=settings.app_name,
        model=service.model_info(),
        sites=["calcaneus", "femoral_neck"],
        languages=list(settings.supported_langs),
        thresholds={
            "risk_rate": settings.level_risk_rate,
            "alert_rate": settings.level_alert_rate,
            "alert_cumulative": settings.level_alert_cumulative,
            "bua_min": settings.bua_min,
            "bua_max": settings.bua_max,
            "uv_min": settings.uv_min,
            "uv_max": settings.uv_max,
            "att_min": settings.att_min,
            "att_max": settings.att_max,
        },
        units={"bua": "dB/MHz", "uv": "m/s", "att": "dB/cm"},
        reference=ReferenceInfoOut(
            source=meta.source,
            population=meta.population,
            bua_unit=meta.bua_unit,
            sos_unit=meta.sos_unit,
            age_bands=bands,
            t_thresholds={
                "osteopenia": settings.bone_t_osteopenia,
                "osteoporosis": settings.bone_t_osteoporosis,
            },
        ),
        cortisol=cortisol_service.reference_out(),
        radiation=radiation_service.reference_out(),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": settings.database_url}
