"""Caso de uso: importacion de mediciones desde CSV, XLSX o JSON.

Reglas:
- Se parsea el archivo entero antes de escribir, se ordena por fecha y se
  reportan los errores fila a fila (no se pierde el lote completo).
- El formato se detecta por extension; el contenido se valida con el mismo
  dominio que usa el alta manual.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core import events
from app.core.i18n import t
from app.domain.errors import DomainError, NotFoundError, ValidationError
from app.domain.schemas import ImportReport, ImportRowError
from app.modules.measurements import service as measurements_service

COLUMN_ALIASES = {
    "measured_on": "measured_on",
    "date": "measured_on",
    "fecha": "measured_on",
    "fecha_sesion": "measured_on",
    "bua": "bua",
    "uv": "uv",
    "att": "att",
    "site": "site",
    "sitio": "site",
}

SITE_ALIASES = {
    "calcaneus": "calcaneus",
    "calcaneo": "calcaneus",
    "calcaneo (talon)": "calcaneus",
    "talon": "calcaneus",
    "femoral_neck": "femoral_neck",
    "femoral neck": "femoral_neck",
    "cuello femoral": "femoral_neck",
}

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y")

SUPPORTED_SUFFIXES = (".csv", ".xlsx", ".json")


@dataclass
class RawRow:
    line: int
    values: dict[str, Any]


def _normalize_header(value: str) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_site(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return "calcaneus"
    key = str(value).strip().lower()
    return SITE_ALIASES.get(key)


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date: {text}")


def _parse_number(value: Any, field: str) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError(f"{field} is empty")
    text = str(value).strip().replace(",", ".")
    return float(text)


def _rows_from_csv(content: bytes) -> list[RawRow]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    rows: list[RawRow] = []
    for index, row in enumerate(reader, start=2):
        values = {
            COLUMN_ALIASES[_normalize_header(key)]: value
            for key, value in row.items()
            if key and _normalize_header(key) in COLUMN_ALIASES
        }
        if any(str(v).strip() for v in values.values()):
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

    keys = [_normalize_header(cell) if cell is not None else "" for cell in header]
    rows: list[RawRow] = []
    for index, cells in enumerate(iterator, start=2):
        values: dict[str, Any] = {}
        for key, cell in zip(keys, cells, strict=False):
            canonical = COLUMN_ALIASES.get(key)
            if canonical:
                values[canonical] = cell
        if any(str(v).strip() for v in values.values() if v is not None):
            rows.append(RawRow(line=index, values=values))
    workbook.close()
    return rows


def _rows_from_json(content: bytes) -> list[RawRow]:
    payload = json.loads(content.decode("utf-8-sig"))
    if isinstance(payload, dict):
        payload = payload.get("measurements", [])
    rows: list[RawRow] = []
    for index, item in enumerate(payload, start=2):
        if not isinstance(item, dict):
            continue
        values = {}
        for key, value in item.items():
            canonical = COLUMN_ALIASES.get(_normalize_header(key))
            if canonical:
                values[canonical] = value
        rows.append(RawRow(line=index, values=values))
    return rows


def parse_file(filename: str, content: bytes, lang: str) -> list[RawRow]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValidationError("error.import_format")
    if suffix == ".csv":
        return _rows_from_csv(content)
    if suffix == ".xlsx":
        return _rows_from_xlsx(content)
    return _rows_from_json(content)


def import_measurements(
    session: Session,
    code: str,
    filename: str,
    content: bytes,
    lang: str,
) -> ImportReport:
    try:
        rows = parse_file(filename, content, lang)
    except ValidationError:
        raise
    except Exception as exc:  # archivo corrupto o formato inesperado
        raise ValidationError("error.import_format") from exc

    if not rows:
        raise ValidationError("error.import_empty")

    parsed: list[tuple[date, dict[str, Any]]] = []
    errors: list[ImportRowError] = []

    for row in rows:
        try:
            measured_on = _parse_date(row.values.get("measured_on"))
            bua = _parse_number(row.values.get("bua"), "bua")
            uv = _parse_number(row.values.get("uv"), "uv")
            att_raw = row.values.get("att")
            att = _parse_number(att_raw, "att") if str(att_raw or "").strip() else None
            site = _normalize_site(row.values.get("site"))
            if site is None:
                raise ValueError(t(lang, "error.invalid_site", site=row.values.get("site")))
            parsed.append(
                (
                    measured_on,
                    {"bua": bua, "uv": uv, "att": att, "site": site, "line": row.line},
                )
            )
        except Exception as exc:
            errors.append(ImportRowError(line=row.line, message=str(exc)))

    parsed.sort(key=lambda item: item[0])

    created = 0
    for measured_on, payload in parsed:
        try:
            measurements_service.record(
                session=session,
                code=code,
                measured_on=measured_on,
                site=payload["site"],
                bua=payload["bua"],
                uv=payload["uv"],
                att=payload["att"],
                lang=lang,
                source="import",
            )
            created += 1
        except NotFoundError as exc:
            # Sin astronauta no tiene sentido seguir con el resto del archivo.
            raise exc
        except DomainError as exc:
            errors.append(
                ImportRowError(
                    line=payload["line"],
                    message=t(lang, exc.key, **exc.params),
                )
            )
        except Exception as exc:
            errors.append(ImportRowError(line=payload["line"], message=str(exc)))

    if created:
        events.bus.publish(
            "measurement.imported",
            {"astronaut_code": code.upper(), "created": created},
        )

    return ImportReport(created=created, skipped=len(errors), errors=errors)
