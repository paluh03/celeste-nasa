from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.domain.models import Astronaut
from app.domain.schemas import AstronautCreate, AstronautOut, AstronautUpdate
from app.infrastructure.database import get_session
from app.modules.astronauts import service

router = APIRouter(prefix="/astronauts", tags=["astronauts"])


def _out(astronaut: Astronaut) -> AstronautOut:
    return service.to_out(astronaut)


@router.get("", response_model=list[AstronautOut])
def list_astronauts(session: Session = Depends(get_session)) -> list[AstronautOut]:
    return [_out(astronaut) for astronaut in service.list_all(session)]


@router.post("", response_model=AstronautOut, status_code=status.HTTP_201_CREATED)
def create_astronaut(
    payload: AstronautCreate,
    session: Session = Depends(get_session),
) -> AstronautOut:
    astronaut = service.create(
        session,
        payload.code,
        payload.name,
        payload.sex,
        payload.birth_date,
    )
    return _out(astronaut)


@router.get("/{code}", response_model=AstronautOut)
def get_astronaut(code: str, session: Session = Depends(get_session)) -> AstronautOut:
    return _out(service.get_one(session, code))


@router.patch("/{code}", response_model=AstronautOut)
def update_astronaut(
    code: str,
    payload: AstronautUpdate,
    session: Session = Depends(get_session),
) -> AstronautOut:
    values = payload.model_dump(exclude_unset=True)
    astronaut = service.update(
        session,
        code,
        name=values.get("name"),
        sex=values.get("sex"),
        birth_date=values.get("birth_date"),
    )
    return _out(astronaut)
