import datetime

import pytest

from truescrub.matchmaking import compute_matches
from truescrub.models import RoundRow, Player, setup_trueskill
from truescrub.updater.recalculate import compute_player_skills

setup_trueskill()


def _round_row(round_id, winner, loser):
  return RoundRow(
    round_id=round_id,
    created_at=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
    season_id=1,
    winner=winner,
    loser=loser,
    mvp=None,
  )


def test_matchmaking_integration_checkpoints():
  """
  Simulates a series of matches to verify the entire system integrates correctly.
  Players 1 & 2 are 'Good'. Players 3 & 4 are 'Bad'.
  """
  teams = {
    1: frozenset({1, 2}),
    2: frozenset({3, 4}),
  }

  rounds = []

  for i in range(1, 6):
    rounds.append(_round_row(i, winner=1, loser=2))

  ratings, _ = compute_player_skills(rounds, teams)

  players = [
    Player(pid, f'P{pid}', ratings[pid].mu, ratings[pid].sigma,
           ratings[pid].mu - 2 * ratings[pid].sigma)
    for pid in [1, 2, 3, 4]
  ]

  matches = list(compute_matches(players))

  worst_match = matches[-1]
  worst_t1_ids = {p.player_id for p in worst_match.team1}
  assert worst_t1_ids == {1, 2} or worst_t1_ids == {3, 4}
  assert worst_match.quality < 0.5

  best_match = matches[0]
  best_t1_ids = {p.player_id for p in best_match.team1}
  assert best_t1_ids in [{1, 3}, {1, 4}, {2, 3}, {2, 4}]
  assert best_match.quality > 0.8

  for i in range(6, 21):
    rounds.append(_round_row(i, winner=1, loser=2))

  ratings_polarized, _ = compute_player_skills(rounds, teams)

  players_polarized = [
    Player(pid, f'P{pid}',
           ratings_polarized[pid].mu,
           ratings_polarized[pid].sigma,
           ratings_polarized[pid].mu - 2 * ratings_polarized[pid].sigma)
    for pid in [1, 2, 3, 4]
  ]

  matches_polarized = list(compute_matches(players_polarized))

  best_polarized_match = matches_polarized[0]
  best_pol_t1_ids = {p.player_id for p in best_polarized_match.team1}
  assert best_pol_t1_ids in [{1, 3}, {1, 4}, {2, 3}, {2, 4}]

  worst_polarized_match = matches_polarized[-1]
  assert worst_polarized_match.quality < worst_match.quality

  players_phase3 = [
    Player(1, 'P1', ratings_polarized[1].mu, ratings_polarized[1].sigma,
           ratings_polarized[1].mu - 2 * ratings_polarized[1].sigma),
    Player(3, 'P3', ratings_polarized[3].mu, ratings_polarized[3].sigma,
           ratings_polarized[3].mu - 2 * ratings_polarized[3].sigma),
    Player(5, 'P5', 1000.0, 250.0, 500.0),
    Player(6, 'P6', 1000.0, 250.0, 500.0),
    Player(7, 'P7', 1000.0, 250.0, 500.0),
  ]

  matches_asym = list(compute_matches(players_phase3))
  best_asym_match = matches_asym[0]

  t1_len = len(best_asym_match.team1)
  t2_len = len(best_asym_match.team2)

  assert (t1_len, t2_len) in [(1, 4), (4, 1), (2, 3), (3, 2)]

  balanced_size_matches = [
    m for m in matches_asym
    if (len(m.team1) == 2 and len(m.team2) == 3) or (
        len(m.team1) == 3 and len(m.team2) == 2)
  ]

  if (t1_len, t2_len) in [(1, 4), (4, 1)]:
    best_balanced_match = balanced_size_matches[0]
    assert best_asym_match.quality > best_balanced_match.quality

  for i in range(21, 221):
    rounds.append(_round_row(i, winner=1, loser=2))

  ratings_entrenched, _ = compute_player_skills(rounds, teams)

  entrenched_p3_sigma = ratings_entrenched[3].sigma
  assert entrenched_p3_sigma < 50.0  # Much lower than starting 250.0

  expected_rounds = rounds + [_round_row(221, winner=1, loser=2)]
  ratings_expected, _ = compute_player_skills(expected_rounds, teams)

  expected_delta_good = ratings_expected[1].mu - ratings_entrenched[1].mu

  assert expected_delta_good < 5.0

  upset_rounds = rounds + [_round_row(221, winner=2, loser=1)]
  ratings_upset, _ = compute_player_skills(upset_rounds, teams)

  upset_delta_bad = ratings_upset[3].mu - ratings_entrenched[3].mu

  assert upset_delta_bad > (expected_delta_good * 5)
  assert upset_delta_bad > 15.0
