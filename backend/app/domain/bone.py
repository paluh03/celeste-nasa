"""Nucleo cientifico del modulo oseo (funciones puras, sin framework).

Aqui y solo aqui vive la formula SCAN y la regla de triage. No importa
FastAPI, SQLModel ni settings: recibe valores y umbrales, devuelve resultados.
Eso permite testear el "cerebro" de forma aislada y reutilizarlo cuando se
agreguen nuevos factores (cortisol, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

DAYS_PER_MONTH = 30.4375
MIN_MONTHS_FOR_RATE = 0.1


@dataclass(frozen=True)
class Thresholds:
    """Umbrales y coeficientes del modelo vigente."""

    uv_coef: float = 3.89e-4
    bua_coef: float = -9e-4
    intercept: float = -0.456
    risk_rate: float = 0.8
    alert_rate: float = 1.5
    alert_cumulative: float = 3.0
    bua_min: float = 0.0
    bua_max: float = 200.0
    uv_min: float = 1200.0
    uv_max: float = 2000.0
    att_min: float = 0.0
    att_max: float = 200.0


@dataclass(frozen=True)
class Sample:
    measured_on: date
    bua: float
    uv: float
    att: float | None = None


@dataclass(frozen=True)
class PointEvaluation:
    measured_on: date
    day: int
    bua: float
    uv: float
    att: float | None
    bv_tv: float
    cumulative_loss_pct: float
    rate_pct_month: float | None
    bv_tv_cumulative_loss_pct: float
    level: int
    trigger: str


def predicted_bv_tv(uv: float, bua: float, thresholds: Thresholds | None = None) -> float:
    """BV/TV = 3.89e-4 * UV - 9e-4 * BUA - 0.456 (regresion publicada)."""
    th = thresholds or Thresholds()
    return th.uv_coef * uv + th.bua_coef * bua + th.intercept


def months_between(start: date, end: date) -> float:
    return (end - start).days / DAYS_PER_MONTH


def cumulative_loss_pct(baseline_value: float, current_value: float) -> float:
    """Perdida porcentual respecto a la linea base (positiva = perdida)."""
    if baseline_value == 0:
        return 0.0
    return (baseline_value - current_value) / baseline_value * 100.0


def validate_sample(
    bua: float | None,
    uv: float | None,
    att: float | None,
    thresholds: Thresholds | None = None,
) -> list[dict[str, object]]:
    """Devuelve errores de dominio como claves i18n (lista vacia = valido).

    No se extrapola: si un valor cae fuera del rango fisico, se rechaza.
    """
    th = thresholds or Thresholds()
    errors: list[dict[str, object]] = []

    if bua is None or not (th.bua_min < bua < th.bua_max):
        errors.append(
            {
                "key": "error.bua_range",
                "params": {"min": th.bua_min, "max": th.bua_max},
            }
        )
    if uv is None or not (th.uv_min <= uv <= th.uv_max):
        errors.append(
            {
                "key": "error.uv_range",
                "params": {"min": th.uv_min, "max": th.uv_max},
            }
        )
    if att is not None and not (th.att_min < att < th.att_max):
        errors.append(
            {
                "key": "error.att_range",
                "params": {"min": th.att_min, "max": th.att_max},
            }
        )
    return errors


def triage(
    cumulative_loss: float,
    rate: float | None,
    thresholds: Thresholds | None = None,
) -> tuple[int, str]:
    """Nivel 1/2/3 segun el documento SCAN. Devuelve (nivel, disparador)."""
    th = thresholds or Thresholds()

    if cumulative_loss > th.alert_cumulative:
        return 3, "cumulative"
    if rate is not None and rate > th.alert_rate:
        return 3, "rate"
    if rate is not None and rate >= th.risk_rate:
        return 2, "rate"
    return 1, "normal"


def evaluate_series(
    samples: list[Sample],
    thresholds: Thresholds | None = None,
) -> list[PointEvaluation]:
    """Evalua una serie cronologica; el primer punto es la linea base."""
    th = thresholds or Thresholds()
    if not samples:
        return []

    ordered = sorted(samples, key=lambda s: s.measured_on)
    baseline = ordered[0]
    baseline_bv_tv = predicted_bv_tv(baseline.uv, baseline.bua, th)

    evaluations: list[PointEvaluation] = []
    for sample in ordered:
        bv = predicted_bv_tv(sample.uv, sample.bua, th)
        days = (sample.measured_on - baseline.measured_on).days
        months = months_between(baseline.measured_on, sample.measured_on)
        loss = cumulative_loss_pct(baseline.bua, sample.bua)
        rate = loss / months if months >= MIN_MONTHS_FOR_RATE else None
        level, trigger = triage(loss, rate, th)

        evaluations.append(
            PointEvaluation(
                measured_on=sample.measured_on,
                day=days,
                bua=sample.bua,
                uv=sample.uv,
                att=sample.att,
                bv_tv=bv,
                cumulative_loss_pct=loss,
                rate_pct_month=rate,
                bv_tv_cumulative_loss_pct=cumulative_loss_pct(baseline_bv_tv, bv),
                level=level,
                trigger=trigger,
            )
        )
    return evaluations
