from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_lang
from app.domain.schemas import MentalAssessmentOut, MentalDayIn
from app.infrastructure.database import get_session
from app.modules.mental import service

router = APIRouter(prefix="/astronauts/{code}/mental", tags=["mental"])


@router.get("", response_model=MentalAssessmentOut)
def get_mental(
    code: str,
    days: int | None = Query(default=None, ge=1, le=365, description="Dias visibles"),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> MentalAssessmentOut:
    return service.build_assessment(session, code, lang, days)


@router.put("/{day}", response_model=MentalAssessmentOut)
def upsert_mental_day(
    code: str,
    day: date,
    payload: MentalDayIn,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> MentalAssessmentOut:
    return service.upsert(session, code, day, payload, lang)
