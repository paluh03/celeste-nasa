"""Punto de entrada: uvicorn levanta la app, la app levanta la base .db."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.api.v1.router import api_router
from app.core import events
from app.core.config import BACKEND_DIR, settings
from app.core.i18n import normalize_lang, t
from app.domain.errors import DomainError
from app.infrastructure.database import dispose_db, get_engine, init_db
from app.modules.astronauts import service as astronauts_service
from app.modules.monitoring import service as monitoring_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nasa-space")

FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    logger.info("database ready: %s", settings.database_url)

    # Astronautas por defecto del prototipo (idempotente, completa el perfil).
    with Session(get_engine()) as session:
        astronauts_service.ensure(
            session,
            "AST-01",
            "Astronaut One",
            sex="male",
            birth_date=date(1985, 4, 12),
        )
        astronauts_service.ensure(
            session,
            "AST-02",
            "Astronaut Two",
            sex="female",
            birth_date=date(1990, 9, 23),
        )

    # Event-driven: la cache de evaluaciones se invalida al escribir.
    events.bus.subscribe("measurement.created", monitoring_service.invalidate_cache)
    events.bus.subscribe("measurement.imported", monitoring_service.invalidate_cache)
    events.bus.subscribe("astronaut.created", monitoring_service.invalidate_cache)
    events.bus.subscribe("astronaut.updated", monitoring_service.invalidate_cache)

    yield

    events.bus.clear()
    dispose_db()


app = FastAPI(
    title="NASA SPACE - SCAN API",
    version="0.1.0",
    description=(
        "Nucleo de monitoreo oseo (SCAN) para vuelos de larga duracion. "
        "Formula BV/TV, tendencia y triage por niveles."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    lang = normalize_lang(
        request.query_params.get("lang") or request.headers.get("accept-language")
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": t(lang, exc.key, **exc.params), "code": exc.key},
    )


app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "database": settings.database_url}


# Produccion local: si existe el build del frontend, se sirve desde el mismo
# servidor (un solo puerto). En desarrollo, Vite hace de proxy hacia la API.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=Path(FRONTEND_DIST), html=True), name="frontend")
