import statistics
import itertools

import pytest
from trueskill import Gaussian

import truescrub.matchmaking as mm
from truescrub.models import Match, Player

PLAYER1 = Player(1, 'Player 1', 1000, 250, 0.5)
PLAYER2 = Player(2, 'Player 2', 1500, 250, 1.0)
PLAYER3 = Player(3, 'Player 3', 1500, 250, 1.337)
PLAYER4 = Player(4, 'Player 4', 1200, 200, 0.8)
PLAYER5 = Player(5, 'Player 5', 1100, 180, 0.75)
PLAYER6 = Player(6, 'Player 6', 1300, 220, 0.9)


def test_confidence_interval_z():
  assert mm.confidence_interval_z(0.5) == pytest.approx(0.674, rel=1e-3)
  assert mm.confidence_interval_z(0.8) == pytest.approx(1.282, rel=1e-3)
  assert mm.confidence_interval_z(0.9) == pytest.approx(1.645, rel=1e-3)
  assert mm.confidence_interval_z(0.99) == pytest.approx(2.576, rel=1e-3)

  assert mm.confidence_interval_z(mm.CONFIDENCE_LEVEL) == \
         pytest.approx(1.960, rel=1e-3)

  with pytest.raises(ValueError):
    mm.confidence_interval_z(0.0)

  with pytest.raises(ValueError):
    mm.confidence_interval_z(1.0)


def test_standard_normal_percentile_range():
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


def test_estimated_skill_range():
  # Test with a player that has mean at SKILL_MEAN and stdev at SKILL_STDEV
  skill = Gaussian(mm.SKILL_MEAN, mm.SKILL_STDEV)
  lb, ub = mm.estimated_skill_range(skill)

  # The resulting normal should have mu=0, sigma=1
  standard_normal_dist = statistics.NormalDist(0, 1)
  z_star = mm.confidence_interval_z(mm.CONFIDENCE_LEVEL)
  expected_lb = standard_normal_dist.cdf(-z_star)
  expected_ub = standard_normal_dist.cdf(z_star)

  assert lb == pytest.approx(expected_lb, rel=1e-3)
  assert ub == pytest.approx(expected_ub, rel=1e-3)


def test_skill_group_ranges():
  # Validate that skill_group_ranges returns expected ranges
  ranges = list(mm.skill_group_ranges())

  # Verify the structure: (group_name, lower_bound, upper_bound)
  assert len(ranges) > 0
  for group_name, lower_bound, upper_bound in ranges:
    assert isinstance(group_name, str)
    assert isinstance(lower_bound, (int, float))
    assert isinstance(upper_bound, (int, float))
    assert lower_bound <= upper_bound

  # Verify the last range has upper_bound = infinity
  assert ranges[-1][2] == float('inf')

  # Verify ranges are contiguous
  for i in range(1, len(ranges)):
    assert ranges[i][1] == ranges[i - 1][2]


def test_win_probability():
  # Simple test with equal teams
  team1 = [Gaussian(1000, 100), Gaussian(1000, 100)]
  team2 = [Gaussian(1000, 100), Gaussian(1000, 100)]
  env = mm.trueskill.global_env()

  prob = mm.win_probability(env, team1, team2)
  assert prob == pytest.approx(0.5, rel=1e-3)

  # Test with team1 having higher skill
  team1 = [Gaussian(1200, 100), Gaussian(1200, 100)]
  team2 = [Gaussian(1000, 100), Gaussian(1000, 100)]

  prob = mm.win_probability(env, team1, team2)
  assert prob > 0.5

  # Test with team2 having higher skill
  team1 = [Gaussian(1000, 100), Gaussian(1000, 100)]
  team2 = [Gaussian(1200, 100), Gaussian(1200, 100)]

  prob = mm.win_probability(env, team1, team2)
  assert prob < 0.5


def test_suggest_teams():
  # Create player skills dictionary with 4 players
  player_skills = {
    1: Gaussian(1000, 200),
    2: Gaussian(1500, 150),
    3: Gaussian(1200, 180),
    4: Gaussian(1300, 160)
  }

  # Get the team suggestions
  suggestions = list(mm.suggest_teams(player_skills))

  # Verify structure of suggestions: (team1, team2, quality, p_win)
  assert len(suggestions) > 0
  for team1, team2, quality, p_win in suggestions:
    assert len(team1) > 0
    assert len(team2) > 0
    assert 0 <= quality <= 1
    assert 0 <= p_win <= 1

    # Verify team compositions are valid
    assert set(team1).isdisjoint(set(team2))
    assert set(team1).union(set(team2)) == {1, 2, 3, 4}


def test_make_match():
  players_by_id = {1: PLAYER1, 2: PLAYER2, 3: PLAYER3}
  team1 = {1}
  team2 = {2}
  quality = 0.9
  p_win = 0.6

  match = mm.make_match(
    players_by_id, team1=team1, team2=team2, quality=quality, p_win=p_win)

  assert match == Match(
    team1=[PLAYER1],
    team2=[PLAYER2],
    quality=quality,
    p_win=p_win,
  )

  # Test case when team2 is stronger (p_win < 0.5)
  # Teams should be swapped so team1 is always the favorite
  match = mm.make_match(
    players_by_id, team1=team1, team2=team2, quality=quality, p_win=0.3)

  assert match.team1 == [PLAYER2]
  assert match.team2 == [PLAYER1]
  assert match.quality == quality
  assert match.team1_win_probability == 0.7  # 1.0 - 0.3


def test_make_team():
  players_by_id = {
    1: PLAYER1,
    2: PLAYER2,
    3: PLAYER3,
    4: PLAYER4,
    5: PLAYER5
  }

  # Test with multiple players to check sorting by MMR
  team = mm.make_team(players_by_id, [1, 3, 5])

  # Should be sorted by MMR in descending order
  assert team == [PLAYER3, PLAYER5, PLAYER1]


def test_uniquify():
  players_by_id = {1: PLAYER1, 2: PLAYER2, 3: PLAYER3}
  match1 = mm.make_match(players_by_id, {1}, {2}, 1.0, 0.5)
  match2 = mm.make_match(players_by_id, {1}, {3}, 0.8, 0.5)
  matches = [
    match1, match2, match1, match1
  ]

  assert list(mm.uniquify(matches)) == [
    match1, match2, match1
  ]

  # Test when teams are swapped (should be considered duplicate)
  match3 = mm.make_match(players_by_id, {2}, {1}, 1.0, 0.5)
  matches = [match1, match3, match2]

  uniquified = list(mm.uniquify(matches))
  # Since match1 and match3 have same teams (just swapped), only one should appear
  assert len(uniquified) == 2
  assert match1 in uniquified
  assert match2 in uniquified


def test_compute_matches():
  # Test with 3 players
  players = [PLAYER1, PLAYER2, PLAYER3]
  matches = list(mm.compute_matches(players))

  assert len(matches) > 0
  for i in range(1, len(matches)):
    assert matches[i - 1].quality >= matches[i].quality

  # Verify each match contains valid teams
  for match in matches:
    assert isinstance(match, Match)
    assert len(match.team1) + len(match.team2) == 3

    # Check that all players are included
    all_players = match.team1 + match.team2
    assert len(all_players) == 3
    assert set(p.player_id for p in all_players) == {1, 2, 3}

  # Test with more players to verify uniqueness
  players = [PLAYER1, PLAYER2, PLAYER3, PLAYER4, PLAYER5, PLAYER6]
  matches = list(mm.compute_matches(players))

  # Should have uniquified matches
  match_signatures = []
  for match in matches:
    team1_ids = frozenset(p.player_id for p in match.team1)
    team2_ids = frozenset(p.player_id for p in match.team2)
    signature = (team1_ids, team2_ids) if team1_ids < team2_ids else (
    team2_ids, team1_ids)

    # This match signature should not appear multiple times in adjacent positions
    if match_signatures and match_signatures[-1] == signature:
      assert False, "Duplicate match found"
    match_signatures.append(signature)


if __name__ == '__main__':
  raise SystemExit(pytest.main([__file__]))
