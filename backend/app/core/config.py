"""Configuracion central del backend.

Todo lo que es "parametro de operacion" vive aqui: rutas, CORS, umbrales
clinicos y version del modelo. El dominio (app/domain) no importa settings
directamente salvo por los valores que se le inyectan, para poder testearlo
aislado.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NASA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NASA SPACE - SCAN"
    api_prefix: str = "/api/v1"

    # Base de datos: archivo .db levantado por la app al arrancar (lifespan).
    database_url: str = f"sqlite:///{(DATA_DIR / 'nasa_space.db').as_posix()}"

    # Solo local: Vite en 5173 y el propio backend.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    default_lang: str = "es"
    supported_langs: tuple[str, ...] = ("es", "en")

    # --- Modelo SCAN (DOI: 10.1117/12.810048 y 10.1016/j.actaastro.2012.08.032) ---
    model_version: str = "scan-2013-v1"
    bv_tv_uv_coef: float = 3.89e-4
    bv_tv_bua_coef: float = -9e-4
    bv_tv_intercept: float = -0.456

    # Umbrales de triage (tasa de perdida de BUA en %/mes).
    level_risk_rate: float = 0.8
    level_alert_rate: float = 1.5
    level_alert_cumulative: float = 3.0

    # Clasificacion por referencia poblacional (convencion OMS sobre T-score).
    bone_t_osteopenia: float = -1.0
    bone_t_osteoporosis: float = -2.5

    # Rangos fisicos aceptados en la captura (no se extrapola fuera de ellos).
    # BUA en dB/MHz (misma unidad que la tabla de referencia Shin et al.).
    bua_min: float = 0.0
    bua_max: float = 200.0
    uv_min: float = 1200.0
    uv_max: float = 2000.0
    att_min: float = 0.0
    att_max: float = 200.0

    # Cache en memoria de evaluaciones; se invalida por eventos.
    cache_ttl_seconds: int = 30


settings = Settings()
