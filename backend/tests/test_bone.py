from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain import bone


def _sample(day_offset: int, bua: float, uv: float = 1560.0, att: float = 52.0) -> bone.Sample:
    return bone.Sample(
        measured_on=date(2026, 7, 1) + timedelta(days=day_offset),
        bua=bua,
        uv=uv,
        att=att,
    )


def test_predicted_bv_tv_matches_published_regression() -> None:
    assert bone.predicted_bv_tv(1560.0, 78.0) == pytest.approx(0.08064, abs=1e-9)


def test_validate_sample_accepts_physical_values() -> None:
    assert bone.validate_sample(78.0, 1560.0, 52.0) == []


@pytest.mark.parametrize(
    ("bua", "uv", "att", "expected_key"),
    [
        (0.0, 1560.0, 52.0, "error.bua_range"),
        (250.0, 1560.0, 52.0, "error.bua_range"),
        (None, 1560.0, 52.0, "error.bua_range"),
        (78.0, 1.5, 52.0, "error.uv_range"),  # UV en km/s: el error tipico
        (78.0, 2500.0, 52.0, "error.uv_range"),
        (78.0, 1560.0, -3.0, "error.att_range"),
    ],
)
def test_validate_sample_rejects_out_of_domain(bua, uv, att, expected_key) -> None:
    keys = [error["key"] for error in bone.validate_sample(bua, uv, att)]
    assert expected_key in keys


@pytest.mark.parametrize(
    ("cumulative", "rate", "level", "trigger"),
    [
        (0.0, 0.4, 1, "normal"),
        (0.0, None, 1, "normal"),
        (1.2, 0.79, 1, "normal"),
        (1.2, 0.8, 2, "rate"),
        (2.0, 1.5, 2, "rate"),
        (2.0, 1.51, 3, "rate"),
        (3.01, 0.2, 3, "cumulative"),
    ],
)
def test_triage_levels(cumulative, rate, level, trigger) -> None:
    assert bone.triage(cumulative, rate) == (level, trigger)


def test_evaluate_series_uses_first_point_as_baseline() -> None:
    series = [_sample(0, 78.0), _sample(30, 77.5)]
    points = bone.evaluate_series(series)

    assert points[0].day == 0
    assert points[0].rate_pct_month is None
    assert points[0].level == 1
    assert points[1].day == 30
    assert points[1].cumulative_loss_pct == pytest.approx(0.6410, abs=1e-3)
    assert points[1].rate_pct_month == pytest.approx(0.6504, abs=1e-3)


def test_evaluate_series_sorts_unordered_input() -> None:
    series = [_sample(90, 75.5), _sample(0, 78.0), _sample(30, 77.5)]
    points = bone.evaluate_series(series)
    assert [point.day for point in points] == [0, 30, 90]


def test_evaluate_series_flags_accumulated_loss() -> None:
    points = bone.evaluate_series([_sample(0, 78.0), _sample(90, 75.5)])
    assert points[-1].level == 3
    assert points[-1].trigger == "cumulative"


def test_empty_series_is_empty() -> None:
    assert bone.evaluate_series([]) == []
