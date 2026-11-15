"""Caso de uso: alta, consulta y perfil de astronautas."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.core import events
from app.domain import reference
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.domain.models import Astronaut
from app.domain.schemas import AstronautOut
from app.infrastructure import repositories

MIN_AGE = 18
MAX_AGE = 100


def list_all(session: Session) -> list[Astronaut]:
    return repositories.list_astronauts(session)


def get_one(session: Session, code: str) -> Astronaut:
    astronaut = repositories.get_astronaut(session, code)
    if astronaut is None:
        raise NotFoundError("error.not_found", code=code)
    return astronaut


def age_today(astronaut: Astronaut) -> int | None:
    return reference.age_at(astronaut.birth_date, date.today())


def to_out(astronaut: Astronaut) -> AstronautOut:
    return AstronautOut(
        code=astronaut.code,
        name=astronaut.name,
        sex=astronaut.sex,  # type: ignore[arg-type]
        birth_date=astronaut.birth_date,
        age=age_today(astronaut),
    )


def create(
    session: Session,
    code: str,
    name: str,
    sex: str,
    birth_date: date,
) -> Astronaut:
    normalized = code.strip().upper()
    if repositories.get_astronaut(session, normalized) is not None:
        raise ConflictError("error.astronaut_exists", code=normalized)
    _validate_profile(sex, birth_date)
    astronaut = repositories.create_astronaut(session, normalized, name.strip(), sex, birth_date)
    events.bus.publish("astronaut.created", {"astronaut_code": astronaut.code})
    return astronaut


def update(
    session: Session,
    code: str,
    *,
    name: str | None = None,
    sex: str | None = None,
    birth_date: date | None = None,
) -> Astronaut:
    astronaut = get_one(session, code)
    if sex is not None or birth_date is not None:
        _validate_profile(
            sex if sex is not None else astronaut.sex or "male",
            birth_date if birth_date is not None else astronaut.birth_date or date(1990, 1, 1),
        )
    if name is not None:
        astronaut.name = name.strip()
    if sex is not None:
        astronaut.sex = sex
    if birth_date is not None:
        astronaut.birth_date = birth_date

    session.add(astronaut)
    session.commit()
    session.refresh(astronaut)
    events.bus.publish("astronaut.updated", {"astronaut_code": astronaut.code})
    return astronaut


def ensure(
    session: Session,
    code: str,
    name: str,
    sex: str | None = None,
    birth_date: date | None = None,
) -> Astronaut:
    """Idempotente: crea el astronauta o completa su perfil si falta."""
    existing = repositories.get_astronaut(session, code)
    if existing is None:
        return repositories.create_astronaut(session, code, name, sex, birth_date)

    changed = False
    if existing.sex is None and sex is not None:
        existing.sex = sex
        changed = True
    if existing.birth_date is None and birth_date is not None:
        existing.birth_date = birth_date
        changed = True
    if changed:
        session.add(existing)
        session.commit()
        session.refresh(existing)
    return existing


def _validate_profile(sex: str, birth_date: date | None) -> None:
    if sex not in ("male", "female"):
        raise ValidationError("error.invalid_sex")
    if birth_date is None or birth_date >= date.today():
        raise ValidationError("error.birth_date_invalid")
    age = reference.age_at(birth_date, date.today())
    if age is None or age < MIN_AGE or age > MAX_AGE:
        raise ValidationError("error.birth_date_invalid")
