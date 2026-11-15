from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.deps import get_lang
from app.domain.schemas import RadiationAssessmentOut, RadiationReadingCreate, RadiationReadingOut
from app.infrastructure.database import get_session
from app.modules.radiation import service

router = APIRouter(prefix="/astronauts/{code}/radiation", tags=["radiation"])


@router.get("", response_model=RadiationAssessmentOut)
def get_radiation(
    code: str,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> RadiationAssessmentOut:
    return service.build_assessment(session, code, lang)


@router.post("", response_model=RadiationReadingOut, status_code=status.HTTP_201_CREATED)
def create_radiation_reading(
    code: str,
    payload: RadiationReadingCreate,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> RadiationReadingOut:
    return service.record(session, code, payload, lang)
