from __future__ import annotations

from datetime import date, datetime, time

import pytest

from app.domain import cortisol


def dt(hour: int, minute: int = 0, day: int = 14) -> datetime:
    return datetime(2026, 11, day, hour, minute)


def test_unit_conversion_roundtrip() -> None:
    assert cortisol.to_ug_dl(27.59, "nmol_l") == pytest.approx(1.0)
    assert cortisol.to_ug_dl(0.474, "ug_dl") == pytest.approx(0.474)
    assert cortisol.to_nmol_l(0.474) == pytest.approx(13.077, abs=1e-3)


@pytest.mark.parametrize(
    ("moment", "band"),
    [
        (dt(5, 59), "predawn"),
        (dt(6, 0), "morning"),
        (dt(9, 59), "morning"),
        (dt(10, 0), "midday"),
        (dt(13, 59), "midday"),
        (dt(14, 0), "afternoon"),
        (dt(18, 59), "afternoon"),
        (dt(19, 0), "night"),
        (dt(23, 59), "night"),
        (dt(0, 0), "predawn"),
    ],
)
def test_time_bands(moment, band) -> None:
    assert cortisol.band_for(moment) == band


def test_expected_median_matches_document_table() -> None:
    all_ref = cortisol.reference().all_sexes
    assert cortisol.expected_median(7.0, all_ref.median) == pytest.approx(0.474, abs=1e-3)
    assert cortisol.expected_median(12.0, all_ref.median) == pytest.approx(0.331, abs=1e-2)
    assert cortisol.expected_median(21.5, all_ref.median) == pytest.approx(0.155, abs=1e-3)
    assert cortisol.expected_median(3.0, all_ref.median) == pytest.approx(0.155, abs=1e-3)
    assert cortisol.expected_median(0.0, all_ref.median) == pytest.approx(0.155, abs=1e-3)


def test_expected_median_is_continuous_between_anchors() -> None:
    all_ref = cortisol.reference().all_sexes
    down = cortisol.expected_median(10.0, all_ref.median)
    later = cortisol.expected_median(15.5, all_ref.median)
    night = cortisol.expected_median(21.0, all_ref.median)
    assert all_ref.median > down > later > night


def test_reference_morning_values() -> None:
    ref = cortisol.reference()
    assert ref.all_sexes.n == 56
    assert ref.all_sexes.median == pytest.approx(0.474, abs=1e-3)
    assert ref.all_sexes.sigma_ln == pytest.approx(0.511, abs=1e-3)
    assert ref.male.median == pytest.approx(0.446, abs=1e-3)
    assert ref.female.median == pytest.approx(0.536, abs=1e-3)


def test_color_thresholds_match_table() -> None:
    all_ref = cortisol.reference().all_sexes
    hour = 7.0

    def color(value: float) -> int:
        expected = cortisol.expected_median(hour, all_ref.median)
        return cortisol.color_for(cortisol.z_score(value, expected, all_ref.sigma_ln))

    assert color(0.47) == cortisol.COLOR_GREEN
    assert color(0.25) == cortisol.COLOR_GREEN  # limite verde bajo
    assert color(0.20) == cortisol.COLOR_YELLOW  # 0,17-0,25
    assert color(0.16) == cortisol.COLOR_RED
    assert color(0.91) == cortisol.COLOR_GREEN  # limite verde alto
    assert color(1.10) == cortisol.COLOR_YELLOW
    assert color(1.30) == cortisol.COLOR_RED


def test_night_cutoffs_match_table() -> None:
    all_ref = cortisol.reference().all_sexes
    expected = cortisol.expected_median(21.0, all_ref.median)

    def color(value: float) -> int:
        return cortisol.color_for(cortisol.z_score(value, expected, all_ref.sigma_ln))

    assert color(0.16) == cortisol.COLOR_GREEN
    assert color(0.30) == cortisol.COLOR_GREEN
    assert color(0.35) == cortisol.COLOR_YELLOW
    assert color(0.45) == cortisol.COLOR_RED


def test_evaluation_percentile_and_direction() -> None:
    evaluation = cortisol.evaluate_sample(0.474, dt(7), "male", 40)
    assert evaluation.z == pytest.approx(0.0, abs=1e-2)
    assert evaluation.percentile == pytest.approx(50.0, abs=1.0)
    assert evaluation.color == cortisol.COLOR_GREEN
    assert evaluation.band == "morning"
    assert cortisol.evaluate_sample(0.90, dt(7), "male", 40).direction == "high"
    assert cortisol.evaluate_sample(0.30, dt(7), "male", 40).direction == "low"


def test_assay_floor_after_eleven() -> None:
    evaluation = cortisol.evaluate_sample(0.10, dt(14), "male", 40)
    assert evaluation.color == cortisol.COLOR_GREEN
    assert "assay_floor" in evaluation.flags


def test_manufacturer_p95_flag() -> None:
    evaluation = cortisol.evaluate_sample(1.0, dt(7), "male", 40)
    assert evaluation.above_manufacturer_p95 is True
    assert "above_manufacturer_p95" in evaluation.flags


def test_sex_discordant_reference() -> None:
    evaluation = cortisol.evaluate_sample(0.30, dt(7), "female", 40)
    assert evaluation.color == cortisol.COLOR_GREEN
    assert evaluation.sex_color == cortisol.COLOR_YELLOW
    assert evaluation.discordant is True
    assert "sex_discordant" in evaluation.flags


def test_age_outside_reference_range_is_flagged() -> None:
    evaluation = cortisol.evaluate_sample(0.474, dt(7), "male", 60)
    assert "age_out_of_range" in evaluation.flags


@pytest.mark.parametrize(
    ("ratio", "reading"),
    [
        (1.0, "flat"),
        (1.5, "normal"),
        (2.0, "normal"),
        (2.5, "watch"),
        (4.0, "watch"),
        (4.3, "elevated"),
    ],
)
def test_ratio_reading(ratio, reading) -> None:
    assert cortisol.ratio_reading(ratio) == reading


def test_evening_night_ratio_uses_closest_samples() -> None:
    samples = [
        (dt(14, 10, day=13), 0.30),
        (dt(15, 25, day=13), 0.32),
        (dt(21, 5, day=13), 0.20),
        (dt(15, 30, day=14), 0.40),
        (dt(21, 0, day=14), 0.10),
    ]
    result = cortisol.evening_night_ratio(samples)
    assert result is not None
    day, ratio, reading, afternoon, night = result
    assert day == date(2026, 11, 14)
    assert afternoon == pytest.approx(0.40)
    assert night == pytest.approx(0.10)
    assert ratio == pytest.approx(4.0)
    assert reading == "watch"


def test_personal_baseline_needs_three_samples() -> None:
    two = [(dt(7, day=1), 0.4), (dt(7, day=2), 0.5)]
    three = [*two, (dt(7, day=3), 0.6)]
    assert cortisol.personal_baseline(two, "morning") is None
    result = cortisol.personal_baseline(three, "morning", current_value=0.6)
    assert result is not None
    n, median_value, delta = result
    assert n == 3
    assert median_value == pytest.approx(0.5)
    assert delta == pytest.approx(20.0)


def test_curve_has_49_points() -> None:
    curve = cortisol.reference_curve()
    assert len(curve) == 49
    assert curve[0][0] == 0.0
    assert curve[-1][0] == 24.0
    assert curve[0][1] == pytest.approx(0.155, abs=1e-3)


def test_wake_time_is_a_time_object() -> None:
    assert isinstance(time(7, 0), time)
