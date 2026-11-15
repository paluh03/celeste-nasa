"""Importacion de muestras de cortisol desde CSV, XLSX o JSON."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.i18n import t
from app.domain.errors import DomainError, NotFoundError, ValidationError
from app.domain.schemas import CortisolSampleCreate, ImportReport, ImportRowError
from app.modules.cortisol import service as cortisol_service

COLUMN_ALIASES = {
    "measured_at": "measured_at",
    "date": "measured_at",
    "fecha": "measured_at",
    "datetime": "measured_at",
    "fecha_hora": "measured_at",
    "value": "value",
    "cortisol": "value",
    "cortisol_ug_dl": "value",
    "unit": "unit",
    "unidad": "unit",
    "wake_time": "wake_time",
    "hora_despertar": "wake_time",
    "mission_phase": "mission_phase",
    "fase": "mission_phase",
    "notes": "notes",
    "notas": "notes",
}

UNITS = {
    "ug_dl": "ug_dl",
    "ug/dl": "ug_dl",
    "µg/dl": "ug_dl",
    "μg/dl": "ug_dl",
    "ugdl": "ug_dl",
    "nmol_l": "nmol_l",
    "nmol/l": "nmol_l",
    "nmoll": "nmol_l",
    "nmol": "nmol_l",
}

PHASES = {"preflight", "inflight", "postflight", "analog"}
SUPPORTED_SUFFIXES = (".csv", ".xlsx", ".json")

DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
)


@dataclass
class RawRow:
    line: int
    values: dict[str, Any]


def _normalize(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid datetime: {text}") from exc
    if parsed.hour == 0 and parsed.minute == 0 and len(text) <= 12:
        raise ValueError("measured_at must include the sample time (hh:mm)")
    return parsed


def _parse_time(value: Any) -> time | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"invalid wake_time: {text}")


def _parse_phase(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    phase = str(value).strip().lower()
    if phase not in PHASES:
        raise ValueError(f"invalid mission phase: {phase}")
    return phase


def _rows_from_csv(content: bytes) -> list[RawRow]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if not reader.fieldnames:
        return []
    rows: list[RawRow] = []
    for index, row in enumerate(reader, start=2):
        values = {
            COLUMN_ALIASES[_normalize(key)]: value
            for key, value in row.items()
            if key and _normalize(key) in COLUMN_ALIASES
        }
        if any(str(value).strip() for value in values.values()):
            rows.append(RawRow(line=index, values=values))
    return rows


def _rows_from_xlsx(content: bytes) -> list[RawRow]:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    iterator = sheet.iter_rows(values_only=True)
    header = next(iterator, None)
    if header is None:
        return []
    keys = [_normalize(cell) if cell is not None else "" for cell in header]
    rows: list[RawRow] = []
    for index, cells in enumerate(iterator, start=2):
        values = {
            COLUMN_ALIASES[key]: cell
            for key, cell in zip(keys, cells, strict=False)
            if key in COLUMN_ALIASES
        }
        if any(str(value).strip() for value in values.values() if value is not None):
            rows.append(RawRow(line=index, values=values))
    workbook.close()
    return rows


def _rows_from_json(content: bytes) -> list[RawRow]:
    payload = json.loads(content.decode("utf-8-sig"))
    if isinstance(payload, dict):
        payload = payload.get("samples", payload.get("measurements", []))
    rows: list[RawRow] = []
    for index, item in enumerate(payload, start=2):
        if not isinstance(item, dict):
            continue
        values = {
            COLUMN_ALIASES[_normalize(key)]: value
            for key, value in item.items()
            if _normalize(key) in COLUMN_ALIASES
        }
        rows.append(RawRow(line=index, values=values))
    return rows


def parse_file(filename: str, content: bytes) -> list[RawRow]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValidationError("error.import_format")
    if suffix == ".csv":
        return _rows_from_csv(content)
    if suffix == ".xlsx":
        return _rows_from_xlsx(content)
    return _rows_from_json(content)


def import_samples(
    session: Session,
    code: str,
    filename: str,
    content: bytes,
    lang: str,
) -> ImportReport:
    try:
        rows = parse_file(filename, content)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("error.import_format") from exc

    if not rows:
        raise ValidationError("error.import_empty")

    parsed: list[tuple[datetime, CortisolSampleCreate]] = []
    errors: list[ImportRowError] = []

    for row in rows:
        try:
            measured_at = _parse_datetime(row.values.get("measured_at"))
            raw_value = row.values.get("value")
            if raw_value is None or str(raw_value).strip() == "":
                raise ValueError("value is empty")
            value = float(str(raw_value).replace(",", "."))
            unit_raw = _normalize(row.values.get("unit") or "ug_dl")
            unit = UNITS.get(unit_raw)
            if unit is None:
                raise ValueError(f"invalid unit: {row.values.get('unit')}")
            parsed.append(
                (
                    measured_at,
                    CortisolSampleCreate(
                        measured_at=measured_at,
                        value=value,
                        unit=unit,
                        wake_time=_parse_time(row.values.get("wake_time")),
                        mission_phase=_parse_phase(row.values.get("mission_phase")),
                        notes=(
                            str(row.values.get("notes")).strip()
                            if row.values.get("notes")
                            else None
                        ),
                    ),
                )
            )
        except Exception as exc:
            errors.append(ImportRowError(line=row.line, message=str(exc)))

    parsed.sort(key=lambda item: item[0])

    created = 0
    for _, payload in parsed:
        try:
            cortisol_service.record(session, code, payload, lang, source="import")
            created += 1
        except NotFoundError:
            raise
        except DomainError as exc:
            errors.append(ImportRowError(line=0, message=t(lang, exc.key, **exc.params)))
        except Exception as exc:
            errors.append(ImportRowError(line=0, message=str(exc)))

    return ImportReport(created=created, skipped=len(errors), errors=errors)
