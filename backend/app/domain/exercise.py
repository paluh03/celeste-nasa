"""Protocolo de ejercicio segun el nivel de densidad osea.

Solo contiene las claves i18n: el texto vive en los catalogos. La prescripcion
es orientativa; la decision final es del medico de vuelo.
"""

from __future__ import annotations

from app.core.i18n import t
from app.domain.schemas import RecommendationOut

EXERCISE_ITEMS: dict[int, tuple[str, ...]] = {
    1: (
        "exercise.1.item.1",
        "exercise.1.item.2",
        "exercise.1.item.3",
    ),
    2: (
        "exercise.2.item.1",
        "exercise.2.item.2",
        "exercise.2.item.3",
    ),
    3: (
        "exercise.3.item.1",
        "exercise.3.item.2",
        "exercise.3.item.3",
    ),
}


def for_level(level: int, lang: str) -> RecommendationOut:
    items = EXERCISE_ITEMS.get(level, EXERCISE_ITEMS[1])
    return RecommendationOut(
        level=level,
        title=t(lang, f"exercise.{level}.title"),
        items=[t(lang, key) for key in items],
        disclaimer=t(lang, "exercise.disclaimer"),
    )
