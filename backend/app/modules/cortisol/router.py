from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_lang
from app.domain.schemas import (
    CortisolAssessmentOut,
    CortisolSampleCreate,
    CortisolSampleOut,
    ImportReport,
)
from app.infrastructure.database import get_session
from app.modules.cortisol import service
from app.modules.cortisol.importer import import_samples

router = APIRouter(prefix="/astronauts/{code}/cortisol", tags=["cortisol"])


@router.get("", response_model=CortisolAssessmentOut)
def get_cortisol(
    code: str,
    days: int | None = Query(default=None, ge=1, le=365, description="Dias visibles"),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> CortisolAssessmentOut:
    return service.build_assessment(session, code, lang, days)


@router.post("", response_model=CortisolSampleOut, status_code=status.HTTP_201_CREATED)
def create_cortisol_sample(
    code: str,
    payload: CortisolSampleCreate,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> CortisolSampleOut:
    return service.record(session, code, payload, lang)


@router.post("/import", response_model=ImportReport, status_code=status.HTTP_201_CREATED)
async def import_cortisol_file(
    code: str,
    file: Annotated[UploadFile, File(description=".csv, .xlsx or .json")],
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> ImportReport:
    content = await file.read()
    return import_samples(session, code, file.filename or "upload.csv", content, lang)
