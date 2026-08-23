import pytest

from tools import rank


def test_untested_theory_gets_the_probation_floor():
    assert rank.credibility(0) == pytest.approx(0.25)
    assert rank.credibility(9) == pytest.approx(0.25)


def test_new_theory_edge_is_shrunk_but_visible():
    # 12 claimed points at the 0.25 floor -> 3.0
    assert rank.ranked_edge(12.0, n=0) == pytest.approx(3.0)


def test_proven_theory_that_delivers_gets_high_credibility():
    # n=40, realized exactly what it claimed -> 40/60 * 1.0
    cred = rank.credibility(40, calibration_edge=6.0, mean_claimed_edge=6.0)
    assert cred == pytest.approx(40 / 60)


def test_proven_theory_ranks_a_six_point_claim_near_four():
    ranked = rank.ranked_edge(
        6.0, n=40, calibration_edge=6.0, mean_claimed_edge=6.0
    )
    assert ranked == pytest.approx(4.0, abs=0.01)


def test_disproven_theory_sinks_below_the_floor():
    # This is the case the floor must NOT protect: measured and found wanting.
    cred = rank.credibility(40, calibration_edge=0.0, mean_claimed_edge=8.0)
    assert cred == pytest.approx(0.0)
    assert rank.ranked_edge(
        10.0, n=40, calibration_edge=0.0, mean_claimed_edge=8.0
    ) == pytest.approx(0.0)


def test_negative_calibration_clamps_to_zero_not_negative():
    cred = rank.credibility(40, calibration_edge=-5.0, mean_claimed_edge=8.0)
    assert cred == pytest.approx(0.0)


def test_overdelivering_theory_is_boosted_but_bounded():
    # Realized 3x its claim, but realization clamps at 1.5
    assert rank.realization(24.0, 8.0) == pytest.approx(1.5)


def test_realization_defaults_to_one_without_measurement():
    assert rank.realization(None, None) == pytest.approx(1.0)
    assert rank.realization(5.0, None) == pytest.approx(1.0)


def test_realization_handles_zero_or_negative_claimed_edge():
    # Avoid divide-by-zero; an unclaimed edge cannot be under- or over-realized.
    assert rank.realization(3.0, 0.0) == pytest.approx(1.0)
    assert rank.realization(3.0, -2.0) == pytest.approx(1.0)


def test_new_theory_can_beat_a_weak_proven_suggestion():
    new = rank.ranked_edge(12.0, n=0)
    proven_weak = rank.ranked_edge(
        2.0, n=40, calibration_edge=6.0, mean_claimed_edge=6.0
    )
    assert new > proven_weak


def test_new_theory_cannot_beat_a_strong_proven_suggestion():
    new = rank.ranked_edge(12.0, n=0)
    proven_strong = rank.ranked_edge(
        8.0, n=40, calibration_edge=8.0, mean_claimed_edge=8.0
    )
    assert proven_strong > new


def test_credibility_grows_with_sample_size():
    small = rank.credibility(10, calibration_edge=5.0, mean_claimed_edge=5.0)
    large = rank.credibility(100, calibration_edge=5.0, mean_claimed_edge=5.0)
    assert large > small
