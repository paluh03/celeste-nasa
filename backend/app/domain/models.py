"""Modelos de persistencia (SQLModel)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import Column, Date, DateTime, String, Text, Time, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """UTC naive: SQLite no guarda zona horaria."""
    return datetime.now(UTC).replace(tzinfo=None)


class Astronaut(SQLModel, table=True):
    __tablename__ = "astronaut"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(sa_column=Column(String(32), unique=True, index=True, nullable=False))
    name: str = Field(default="", sa_column=Column(String(120), nullable=False, default=""))
    # Perfil para la referencia poblacional. Nullable para no romper datos previos.
    sex: str | None = Field(default=None, sa_column=Column(String(8), nullable=True))
    birth_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime, nullable=False),
    )


class Measurement(SQLModel, table=True):
    __tablename__ = "measurement"

    id: int | None = Field(default=None, primary_key=True)
    astronaut_id: int = Field(foreign_key="astronaut.id", index=True)
    measured_on: date = Field(sa_column=Column(Date, index=True, nullable=False))
    site: str = Field(sa_column=Column(String(32), index=True, nullable=False))
    bua: float
    uv: float
    att: float | None = None
    source: str = Field(default="manual", sa_column=Column(String(16), nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime, nullable=False),
    )


class CortisolSample(SQLModel, table=True):
    """Muestra de cortisol salival (CLIA/ECLIA). Independiente del modulo oseo."""

    __tablename__ = "cortisol_sample"

    id: int | None = Field(default=None, primary_key=True)
    astronaut_id: int = Field(foreign_key="astronaut.id", index=True)
    measured_at: datetime = Field(sa_column=Column(DateTime, index=True, nullable=False))
    value_ug_dl: float
    input_value: float
    input_unit: str = Field(sa_column=Column(String(8), nullable=False))
    wake_time: time | None = Field(default=None, sa_column=Column(Time, nullable=True))
    mission_phase: str | None = Field(default=None, sa_column=Column(String(16), nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str = Field(default="manual", sa_column=Column(String(16), nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime, nullable=False),
    )


class RadiationReading(SQLModel, table=True):
    """Lectura de radiacion (TEPC). Seccion independiente."""

    __tablename__ = "radiation_reading"

    id: int | None = Field(default=None, primary_key=True)
    astronaut_id: int = Field(foreign_key="astronaut.id", index=True)
    measured_at: datetime = Field(sa_column=Column(DateTime, index=True, nullable=False))
    eq_rate_usv_min: float
    dose_rate_ugy_min: float | None = None
    region: str = Field(default="unknown", sa_column=Column(String(8), nullable=False))
    module: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    mission_day: int | None = None
    planned_days: int | None = None
    prior_career_msv: float | None = None
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str = Field(default="manual", sa_column=Column(String(16), nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime, nullable=False),
    )


class MentalDay(SQLModel, table=True):
    """Registro diario de salud mental (TLX + DMRS)."""

    __tablename__ = "mental_day"
    __table_args__ = (UniqueConstraint("astronaut_id", "day", name="uq_mental_day"),)

    id: int | None = Field(default=None, primary_key=True)
    astronaut_id: int = Field(foreign_key="astronaut.id", index=True)
    day: date = Field(sa_column=Column(Date, index=True, nullable=False))
    mission_day: int | None = None
    m1_sleep: int = 5
    m2_vigor: int = 5
    m3_calm: int = 5
    m4_cohesion: int = 5
    m5_tension: int = 5
    m6_irrit: int = 5
    m7_dysphoria: int = 5
    m8_somatic: int = 5
    acute_24h_dose_mgy: float | None = None
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str = Field(default="manual", sa_column=Column(String(16), nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime, nullable=False),
    )


class MentalTask(SQLModel, table=True):
    __tablename__ = "mental_task"

    id: int | None = Field(default=None, primary_key=True)
    day_id: int = Field(foreign_key="mental_day.id", index=True)
    task_ref: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    category: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    name: str | None = Field(default=None, sa_column=Column(String(200), nullable=True))
    duration_min: float
    eval_mode: str = Field(sa_column=Column(String(16), nullable=False))
    ratings_json: str = Field(sa_column=Column(Text, nullable=False))
    tallies_json: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    overall: float
