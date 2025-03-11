import statistics
from typing import Dict, List, Tuple

import pytest
from trueskill import Gaussian

import truescrub.matchmaking as mm
from truescrub.models import Match, Player

PLAYER1 = Player(1, "Player 1", 1000, 250, 0.5)
PLAYER2 = Player(2, "Player 2", 1500, 250, 1.0)
PLAYER3 = Player(3, "Player 3", 1500, 250, 1.337)


def test_confidence_interval_z() -> None:
    """Test the confidence interval Z-score calculation."""
    assert mm.confidence_interval_z(0.5) == pytest.approx(0.674, rel=1e-3)
    assert mm.confidence_interval_z(0.8) == pytest.approx(1.282, rel=1e-3)
    assert mm.confidence_interval_z(0.9) == pytest.approx(1.645, rel=1e-3)
    assert mm.confidence_interval_z(0.99) == pytest.approx(2.576, rel=1e-3)

    assert mm.confidence_interval_z(mm.CONFIDENCE_LEVEL) == pytest.approx(
        1.960, rel=1e-3
    )

    with pytest.raises(ValueError):
        mm.confidence_interval_z(0.0)

    with pytest.raises(ValueError):
        mm.confidence_interval_z(1.0)


def test_standard_normal_percentile_range() -> None:
    """Test percentile range calculation for standard normal distribution."""
    mean = 2.0
    stdev = 0.01
    estimate = Gaussian(mean, stdev)
    z_star = 1.960

    standard_normal_dist = statistics.NormalDist(0, 1)
    expected_lb = standard_normal_dist.cdf(mean - z_star * stdev)
    expected_ub = standard_normal_dist.cdf(mean + z_star * stdev)
    actual_lb, actual_ub = mm.standard_normal_percentile_range(estimate)

    assert actual_lb == pytest.approx(expected_lb, rel=1e-3)
    assert actual_ub == pytest.approx(expected_ub, rel=1e-3)


def test_make_match() -> None:
    """Test match creation functionality."""
    players_by_id: Dict[int, Player] = {1: PLAYER1, 2: PLAYER2, 3: PLAYER3}
    team1: Tuple[int, ...] = (1,)
    team2: Tuple[int, ...] = (2,)
    quality = 0.9
    p_win = 0.6

    match = mm.make_match(
        players_by_id, team1_ids=team1, team2_ids=team2, quality=quality, p_win=p_win
    )

    assert match == Match(
        team1=[PLAYER1],
        team2=[PLAYER2],
        quality=quality,
        p_win=p_win,
    )


def test_uniquify() -> None:
    """Test uniquify functionality to remove consecutive duplicate matches."""
    players_by_id: Dict[int, Player] = {1: PLAYER1, 2: PLAYER2, 3: PLAYER3}
    match1 = mm.make_match(players_by_id, team1_ids=(1,), team2_ids=(2,), quality=1.0, p_win=0.5)
    match2 = mm.make_match(players_by_id, team1_ids=(1,), team2_ids=(3,), quality=0.8, p_win=0.5)
    matches: List[Match] = [match1, match2, match1, match1]

    assert list(mm.uniquify(matches)) == [match1, match2, match1]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
