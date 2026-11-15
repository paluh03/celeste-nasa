from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_lang
from app.domain.schemas import ImportReport, MeasurementCreate, MeasurementOut, Site
from app.infrastructure.database import get_session
from app.modules.measurements import service
from app.modules.measurements.importer import import_measurements

router = APIRouter(prefix="/astronauts/{code}/measurements", tags=["measurements"])


def _out(measurement) -> MeasurementOut:
    return MeasurementOut(
        id=measurement.id or 0,
        measured_on=measurement.measured_on,
        site=measurement.site,  # type: ignore[arg-type]
        bua=measurement.bua,
        uv=measurement.uv,
        att=measurement.att,
        source=measurement.source,
    )


@router.get("", response_model=list[MeasurementOut])
def list_measurements(
    code: str,
    site: Site | None = None,
    since: date | None = None,
    session: Session = Depends(get_session),
) -> list[MeasurementOut]:
    return [_out(m) for m in service.list_for(session, code, site=site, since=since)]


@router.post("", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
def create_measurement(
    code: str,
    payload: MeasurementCreate,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> MeasurementOut:
    measurement = service.record(
        session=session,
        code=code,
        measured_on=payload.measured_on,
        site=payload.site,
        bua=payload.bua,
        uv=payload.uv,
        att=payload.att,
        lang=lang,
    )
    return _out(measurement)


@router.post("/import", response_model=ImportReport, status_code=status.HTTP_201_CREATED)
async def import_measurements_file(
    code: str,
    file: Annotated[UploadFile, File(description=".csv, .xlsx or .json")],
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
) -> ImportReport:
    content = await file.read()
    return import_measurements(
        session=session,
        code=code,
        filename=file.filename or "upload.csv",
        content=content,
        lang=lang,
    )
