"""Dependencias compartidas de la capa HTTP."""

from __future__ import annotations

from fastapi import Query, Request

from app.core.i18n import normalize_lang


def get_lang(
    request: Request,
    lang: str | None = Query(default=None, description="es | en"),
) -> str:
    """Prioridad: ?lang= > Accept-Language > default."""
    return normalize_lang(lang or request.headers.get("accept-language"))
