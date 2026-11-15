"""Excepciones de dominio (traducibles, sin acoplarse a HTTP)."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Error de negocio con clave i18n y parametros."""

    status_code = 400

    def __init__(self, key: str, **params: Any) -> None:
        self.key = key
        self.params = params
        super().__init__(key)


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ValidationError(DomainError):
    status_code = 422
