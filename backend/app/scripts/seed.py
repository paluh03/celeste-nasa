"""Datos de ejemplo (perfil + serie osea + cortisol) para demos.

Uso:  uv run python -m app.scripts.seed [--force]
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta

from sqlmodel import Session

from app.domain.schemas import (
    CortisolSampleCreate,
    MentalDayIn,
    MoodIn,
    RadiationReadingCreate,
    TlxTaskIn,
)
from app.infrastructure import repositories
from app.infrastructure.database import get_engine, init_db
from app.modules.astronauts import service as astronauts_service
from app.modules.cortisol import service as cortisol_service
from app.modules.measurements import service as measurements_service
from app.modules.mental import service as mental_service
from app.modules.radiation import service as radiation_service

# (offset en dias desde la linea base, BUA dB/MHz, UV m/s, ATT dB/cm)
DEMO = {
    "AST-01": {
        "name": "Astronaut One",
        "sex": "male",
        "birth_date": date(1985, 4, 12),
        "rows": [
            (0, 118.0, 1552.0, 52.0),
            (15, 117.9, 1551.0, 52.0),
            (30, 117.3, 1548.0, 51.6),
            (60, 115.9, 1542.0, 50.9),
            (90, 114.2, 1536.0, 50.1),
        ],
    },
    "AST-02": {
        "name": "Astronaut Two",
        "sex": "female",
        "birth_date": date(1990, 9, 23),
        "rows": [
            (0, 113.8, 1550.0, 50.0),
            (30, 113.5, 1549.0, 49.8),
        ],
    },
}

# (momento ISO, valor, unidad, hora de despertar)
CORTISOL = {
    "AST-01": [
        ("2026-07-01T07:00:00", 0.52, "ug_dl", "06:00"),
        ("2026-07-01T12:00:00", 0.34, "ug_dl", "06:00"),
        ("2026-07-01T15:30:00", 0.24, "ug_dl", "06:00"),
        ("2026-07-01T21:00:00", 0.15, "ug_dl", "06:00"),
        ("2026-07-02T07:00:00", 0.58, "ug_dl", "06:10"),
        ("2026-07-02T21:00:00", 0.36, "ug_dl", "06:10"),
    ],
    "AST-02": [
        ("2026-07-01T07:00:00", 0.55, "ug_dl", "05:50"),
        ("2026-07-01T15:30:00", 0.28, "ug_dl", "05:50"),
        ("2026-07-01T21:00:00", 0.18, "ug_dl", "05:50"),
    ],
}

# (momento UTC, tasa eq uSv/min, region, dia de mision, dosis previa)
RADIATION = {
    "AST-01": [
        ("2018-04-11T08:00:00", 0.45, "unknown", 20, None),
        ("2018-04-11T10:00:00", 0.60, "unknown", 20, None),
        ("2018-04-11T12:00:00", 1.10, "unknown", 20, None),
        ("2018-04-11T12:05:00", 2.20, "unknown", 20, None),
    ]
}

# (dia, dia de mision, animo, carga de la tarea)
MENTAL = {
    "AST-01": [
        ("2026-11-01", 20, (8, 8, 8, 8, 2, 2, 2, 2), 45.0),
        ("2026-11-02", 21, (8, 7, 8, 8, 3, 2, 2, 3), 55.0),
        ("2026-11-03", 22, (6, 6, 6, 6, 4, 3, 3, 4), 70.0),
        ("2026-11-04", 23, (4, 4, 4, 4, 6, 6, 6, 6), 80.0),
        ("2026-11-05", 24, (2, 2, 2, 2, 8, 8, 8, 8), 90.0),
    ],
    "AST-02": [
        ("2026-11-02", 15, (7, 7, 7, 7, 3, 3, 3, 3), 50.0),
        ("2026-11-03", 16, (7, 6, 7, 7, 3, 3, 4, 3), 60.0),
    ],
}


def _mental_payload(mission_day: int, mood: tuple[int, ...], workload: float) -> MentalDayIn:
    return MentalDayIn(
        mission_day=mission_day,
        mood=MoodIn(
            m1_sleep=mood[0],
            m2_vigor=mood[1],
            m3_calm=mood[2],
            m4_cohesion=mood[3],
            m5_tension=mood[4],
            m6_irrit=mood[5],
            m7_dysphoria=mood[6],
            m8_somatic=mood[7],
        ),
        tasks=[
            TlxTaskIn(
                name="Tarea de ejemplo",
                duration_min=120,
                eval_mode="RAW_FAST",
                ratings={
                    "MD": int(workload),
                    "PD": int(workload - 5),
                    "TD": int(workload - 10),
                    "OP": int(workload),
                    "EF": int(workload - 5),
                    "FR": int(workload - 10),
                },
            )
        ],
    )


def main() -> int:
    init_db()
    base = date(2026, 7, 1)
    force = "--force" in sys.argv

    with Session(get_engine()) as session:
        for code, profile in DEMO.items():
            astronaut = astronauts_service.ensure(
                session,
                code,
                profile["name"],
                sex=profile["sex"],
                birth_date=profile["birth_date"],
            )

            existing = measurements_service.list_for(session, astronaut.code, site="calcaneus")
            if existing and not force:
                print(f"{code}: ya tiene {len(existing)} mediciones, se omite")
            else:
                for offset, bua, uv, att in profile["rows"]:
                    measurements_service.record(
                        session=session,
                        code=astronaut.code,
                        measured_on=base + timedelta(days=offset),
                        site="calcaneus",
                        bua=bua,
                        uv=uv,
                        att=att,
                        lang="es",
                        source="seed",
                    )
                print(f"{code}: {len(profile['rows'])} mediciones cargadas")

            existing_cortisol = repositories.list_cortisol_samples(session, astronaut.id or 0)
            if existing_cortisol and not force:
                print(f"{code}: ya tiene {len(existing_cortisol)} muestras de cortisol")
            else:
                rows = CORTISOL.get(code, [])
                for moment, value, unit, wake in rows:
                    cortisol_service.record(
                        session=session,
                        code=astronaut.code,
                        payload=CortisolSampleCreate(
                            measured_at=datetime.fromisoformat(moment),
                            value=value,
                            unit=unit,
                            wake_time=time.fromisoformat(wake),
                            mission_phase="analog",
                        ),
                        lang="es",
                        source="seed",
                    )
                print(f"{code}: {len(rows)} muestras de cortisol cargadas")

            existing_radiation = repositories.list_radiation_readings(session, astronaut.id or 0)
            if existing_radiation and not force:
                print(f"{code}: ya tiene {len(existing_radiation)} lecturas de radiacion")
            else:
                rows = RADIATION.get(code, [])
                for moment, eq, region, mission_day, prior in rows:
                    radiation_service.record(
                        session=session,
                        code=astronaut.code,
                        payload=RadiationReadingCreate(
                            measured_at=datetime.fromisoformat(moment),
                            eq_rate=eq,
                            region=region,  # type: ignore[arg-type]
                            mission_day=mission_day,
                            prior_career_msv=prior,
                        ),
                        lang="es",
                        source="seed",
                    )
                print(f"{code}: {len(rows)} lecturas de radiacion cargadas")

            existing_mental = repositories.list_mental_days(session, astronaut.id or 0)
            if existing_mental and not force:
                print(f"{code}: ya tiene {len(existing_mental)} dias de salud mental")
            else:
                rows = MENTAL.get(code, [])
                for day_str, mission_day, mood, workload in rows:
                    mental_service.upsert(
                        session=session,
                        code=astronaut.code,
                        day=date.fromisoformat(day_str),
                        payload=_mental_payload(mission_day, mood, workload),
                        lang="es",
                    )
                print(f"{code}: {len(rows)} dias de salud mental cargados")

    print("listo: backend/data/nasa_space.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
