"""Traduccion de mensajes del backend (solo es/en).

El frontend traduce su propia interfaz; el backend traduce lo que el cliente
no puede saber por si mismo: errores de validacion de dominio y el texto
clinico de cada nivel de alerta.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from app.core.config import settings

I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"


@cache
def _catalog(lang: str) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        path = I18N_DIR / "en.json"
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_lang(raw: str | None) -> str:
    """Acepta 'en-US,en;q=0.9' y devuelve un idioma soportado."""
    if not raw:
        return settings.default_lang
    first = raw.split(",")[0].split(";")[0].strip().lower()
    short = first.split("-")[0]
    for candidate in (first, short):
        if candidate in settings.supported_langs:
            return candidate
    return settings.default_lang


def t(lang: str, key: str, **kwargs: Any) -> str:
    catalog = _catalog(normalize_lang(lang))
    template = catalog.get(key) or _catalog("en").get(key) or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def level_text(lang: str, level: int) -> dict[str, str]:
    return {
        "name": t(lang, f"level.{level}.name"),
        "tip": t(lang, f"level.{level}.tip"),
    }
