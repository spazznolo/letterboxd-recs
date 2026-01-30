from letterboxd_recs.models.social_simple import _time_weight


def test_time_weight_exponential() -> None:
    current_year = 2025
    assert _time_weight(2025, current_year, 0.25, 25) == 1.0
    half = _time_weight(2000, current_year, 0.25, 25)
    assert 0.49 < half < 0.51
    assert _time_weight(1900, current_year, 0.25, 25) == 0.25


def test_time_weight_none() -> None:
    assert _time_weight(None, 2025, 0.25, 25) == 0.75
