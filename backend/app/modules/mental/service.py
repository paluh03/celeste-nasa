"""Caso de uso del modulo de salud mental."""

from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session

from app.domain import mental
from app.domain.errors import ValidationError
from app.domain.models import MentalDay, MentalTask
from app.domain.schemas import (
    MentalAssessmentOut,
    MentalDayIn,
    MentalDayOut,
    MoodIn,
    TlxTaskOut,
)
from app.infrastructure import repositories
from app.modules.astronauts import service as astronauts_service


def _task_out(task: MentalTask) -> TlxTaskOut:
    ratings = json.loads(task.ratings_json)
    tallies = json.loads(task.tallies_json) if task.tallies_json else None
    computed = mental.compute_tlx(ratings, tallies, task.eval_mode)
    return TlxTaskOut(
        id=task.id or 0,
        task_ref=task.task_ref,
        category=task.category,
        name=task.name,
        duration_min=task.duration_min,
        eval_mode=task.eval_mode,  # type: ignore[arg-type]
        ratings=computed.ratings,
        weights={key: round(value, 4) for key, value in computed.weights.items()},
        overall=round(computed.overall, 4),
    )


def _mood_dict(day: MentalDay) -> dict[str, int]:
    return {
        "m1_sleep": day.m1_sleep,
        "m2_vigor": day.m2_vigor,
        "m3_calm": day.m3_calm,
        "m4_cohesion": day.m4_cohesion,
        "m5_tension": day.m5_tension,
        "m6_irrit": day.m6_irrit,
        "m7_dysphoria": day.m7_dysphoria,
        "m8_somatic": day.m8_somatic,
    }


def _day_out(day: MentalDay, result: mental.DayResult, tasks: list[MentalTask]) -> MentalDayOut:
    return MentalDayOut(
        day=result.day,
        mission_day=result.mission_day,
        wl_day=round(result.wl_day, 2),
        dmrs=round(result.dmrs, 2),
        pa=round(result.pa, 2),
        na=round(result.na, 2),
        z_wl=round(result.z_wl, 2),
        z_dmrs=round(result.z_dmrs, 2),
        ewma_wl=round(result.ewma_wl, 2),
        ewma_mood=round(result.ewma_mood, 2),
        ali=round(result.ali, 2),
        sleep_debt=result.sleep_debt,
        burnout=result.burnout,
        acute_radiation=result.acute_radiation,
        zone=result.zone,
        color=result.color,
        reasons=list(result.reasons),
        mood=MoodIn(**_mood_dict(day)),
        tasks=[_task_out(task) for task in tasks],
    )


def upsert(
    session: Session,
    code: str,
    day: date,
    payload: MentalDayIn,
    lang: str,
) -> MentalAssessmentOut:
    astronaut = astronauts_service.get_one(session, code)
    if day > date.today():
        raise ValidationError("error.day_future")

    computed = []
    for task in payload.tasks:
        try:
            result = mental.compute_tlx(task.ratings, task.tallies, task.eval_mode)
        except ValueError as exc:
            raise ValidationError("error.tlx_invalid", detail=str(exc)) from exc
        computed.append((task, result))

    existing = repositories.get_mental_day(session, astronaut.id or 0, day)
    if existing is None:
        record = MentalDay(astronaut_id=astronaut.id or 0, day=day)
    else:
        record = existing

    record.mission_day = payload.mission_day
    record.m1_sleep = payload.mood.m1_sleep
    record.m2_vigor = payload.mood.m2_vigor
    record.m3_calm = payload.mood.m3_calm
    record.m4_cohesion = payload.mood.m4_cohesion
    record.m5_tension = payload.mood.m5_tension
    record.m6_irrit = payload.mood.m6_irrit
    record.m7_dysphoria = payload.mood.m7_dysphoria
    record.m8_somatic = payload.mood.m8_somatic
    record.acute_24h_dose_mgy = payload.acute_24h_dose_mgy
    record.notes = payload.notes
    session.add(record)
    session.commit()
    session.refresh(record)

    repositories.delete_mental_tasks(session, record.id or 0)
    for task, result in computed:
        session.add(
            MentalTask(
                day_id=record.id or 0,
                task_ref=task.task_ref,
                category=task.category,
                name=task.name,
                duration_min=task.duration_min,
                eval_mode=task.eval_mode,
                ratings_json=json.dumps(result.ratings),
                tallies_json=json.dumps(task.tallies) if task.tallies else None,
                overall=result.overall,
            )
        )
    session.commit()

    return build_assessment(session, code, lang)


def build_assessment(
    session: Session,
    code: str,
    lang: str,
    days: int | None = None,
) -> MentalAssessmentOut:
    astronaut = astronauts_service.get_one(session, code)
    records = repositories.list_mental_days(session, astronaut.id or 0)

    inputs: list[mental.DayInput] = []
    tasks_by_day: dict[date, list[MentalTask]] = {}
    for record in records:
        tasks = repositories.list_mental_tasks(session, record.id or 0)
        tasks_by_day[record.day] = tasks
        inputs.append(
            mental.DayInput(
                day=record.day,
                mission_day=record.mission_day,
                mood=_mood_dict(record),
                wl_day=mental.daily_workload([(task.overall, task.duration_min) for task in tasks]),
                acute_24h_dose_mgy=record.acute_24h_dose_mgy,
            )
        )

    results = mental.build_series(inputs)
    by_date = {record.day: record for record in records}
    all_days = [
        _day_out(by_date[result.day], result, tasks_by_day[result.day]) for result in results
    ]

    visible = all_days
    if days and all_days:
        cutoff = all_days[-1].day.toordinal() - days + 1
        visible = [item for item in all_days if item.day.toordinal() >= cutoff]

    return MentalAssessmentOut(
        astronaut=astronauts_service.to_out(astronaut),
        days=visible,
        current=all_days[-1] if all_days else None,
        thresholds={key: float(value) for key, value in mental.THRESHOLDS.items()},
        warnings=[],
    )
