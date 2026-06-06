"""
Unit tests for truescrub.updater.recalculate.

Tests the TrueSkill rating pipeline — compute_player_skills and helpers —
without requiring a real database.
"""
import datetime

import pytest
import trueskill

from truescrub.models import RoundRow, SkillHistory, setup_trueskill

setup_trueskill()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round_row(round_id, winner, loser, season_id=1, mvp=None):
  """Build a RoundRow with sensible defaults."""
  return RoundRow(
    round_id=round_id,
    created_at=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
    season_id=season_id,
    winner=winner,
    loser=loser,
    mvp=mvp,
  )


# Team membership lookup: team_id → frozenset of player_ids
TEAMS = {
  1: frozenset({100, 200}),
  2: frozenset({300, 400}),
  3: frozenset({100}),
  4: frozenset({200}),
}


# ---------------------------------------------------------------------------
# compute_player_skills
# ---------------------------------------------------------------------------

from truescrub.updater.recalculate import compute_player_skills


class TestComputePlayerSkills:
  def test_winner_rating_increases(self):
    """After one round, the winning team's ratings should go up."""
    rounds = [_round_row(1, winner=1, loser=2)]
    ratings, history = compute_player_skills(rounds, TEAMS)

    default = trueskill.Rating()
    for player_id in TEAMS[1]:
      assert ratings[player_id].mu > default.mu
    for player_id in TEAMS[2]:
      assert ratings[player_id].mu < default.mu

  def test_history_recorded_per_player_per_round(self):
    rounds = [
      _round_row(1, winner=1, loser=2),
      _round_row(2, winner=2, loser=1),
    ]
    ratings, history = compute_player_skills(rounds, TEAMS)

    # 4 players × 2 rounds = 8 history entries
    assert len(history) == 8
    assert all(isinstance(h, SkillHistory) for h in history)

  def test_ratings_converge_over_many_rounds(self):
    """A team that wins consistently should build a rating advantage."""
    rounds = [_round_row(i, winner=1, loser=2) for i in range(1, 21)]
    ratings, _ = compute_player_skills(rounds, TEAMS)

    winner_mu = min(ratings[pid].mu for pid in TEAMS[1])
    loser_mu = max(ratings[pid].mu for pid in TEAMS[2])
    assert winner_mu > loser_mu

  def test_current_ratings_are_used_as_priors(self):
    """Passing current_ratings seeds the computation."""
    prior = {500: trueskill.Rating(mu=1500, sigma=100)}
    rounds = [_round_row(1, winner=3, loser=4)]
    ratings, _ = compute_player_skills(rounds, TEAMS,
                                       current_ratings=prior)

    # Player 500 wasn't in this round, so their rating should be untouched
    assert ratings[500].mu == pytest.approx(1500)
    assert ratings[500].sigma == pytest.approx(100)

  def test_empty_rounds_returns_empty(self):
    ratings, history = compute_player_skills([], TEAMS)
    assert ratings == {}
    assert history == []

  def test_history_links_to_correct_round(self):
    rounds = [_round_row(42, winner=1, loser=2)]
    _, history = compute_player_skills(rounds, TEAMS)
    assert all(h.round_id == 42 for h in history)

  def test_upset_yields_larger_delta(self):
    # Expected: Favorite (100) beats Underdog (300)
    expected_rounds = [_round_row(1, winner=1, loser=2)]
    # Upset: Underdog (300) beats Favorite (100)
    upset_rounds = [_round_row(1, winner=2, loser=1)]
    
    prior = {
      100: trueskill.Rating(mu=1500, sigma=100),
      200: trueskill.Rating(mu=1500, sigma=100),
      300: trueskill.Rating(mu=500, sigma=100),
      400: trueskill.Rating(mu=500, sigma=100),
    }
    
    expected_ratings, _ = compute_player_skills(expected_rounds, TEAMS, current_ratings=prior)
    expected_delta = expected_ratings[100].mu - prior[100].mu
    
    upset_ratings, _ = compute_player_skills(upset_rounds, TEAMS, current_ratings=prior)
    upset_delta = upset_ratings[300].mu - prior[300].mu
    
    assert upset_delta > expected_delta

  def test_uncertainty_volatility_scaling(self):
    # Team 1 beats Team 2
    prior = {
      100: trueskill.Rating(mu=1000, sigma=10), # Veteran
      200: trueskill.Rating(mu=1000, sigma=250), # Newbie
      300: trueskill.Rating(mu=1000, sigma=100),
      400: trueskill.Rating(mu=1000, sigma=100),
    }
    rounds = [_round_row(1, winner=1, loser=2)]
    ratings, _ = compute_player_skills(rounds, TEAMS, current_ratings=prior)
    
    veteran_delta = ratings[100].mu - prior[100].mu
    newbie_delta = ratings[200].mu - prior[200].mu
    
    assert newbie_delta > veteran_delta

  def test_recalculate_adapter_asymmetric_teams(self):
    # Mock a 2v3 match
    asym_teams = {
      1: frozenset({101, 102}),
      2: frozenset({201, 202, 203}),
    }
    prior = {
      101: trueskill.Rating(mu=1000, sigma=100),
      102: trueskill.Rating(mu=1000, sigma=100),
      201: trueskill.Rating(mu=1000, sigma=100),
      202: trueskill.Rating(mu=1000, sigma=100),
      203: trueskill.Rating(mu=2000, sigma=1), # Distinctly unique
    }
    rounds = [_round_row(1, winner=1, loser=2)]
    ratings, _ = compute_player_skills(rounds, asym_teams, current_ratings=prior)
    
    assert len(ratings) == 5
    # ID 203 should lose a tiny fraction of points because sigma is 1, but its mu should remain ~2000
    assert ratings[203].mu > 1900


# ---------------------------------------------------------------------------
# compute_assists
# ---------------------------------------------------------------------------

from truescrub.updater.recalculate import compute_assists


class TestComputeAssists:
  def test_computes_per_round_assists(self):
    rounds = [
      {'stats': {1: {'match_assists': 3}, 2: {'match_assists': 1}},
       'last_round': False},
      {'stats': {1: {'match_assists': 5}, 2: {'match_assists': 1}},
       'last_round': False},
    ]
    compute_assists(rounds)
    assert rounds[0]['stats'][1]['assists'] == 3
    assert rounds[0]['stats'][2]['assists'] == 1
    assert rounds[1]['stats'][1]['assists'] == 2  # 5 - 3
    assert rounds[1]['stats'][2]['assists'] == 0  # 1 - 1

  def test_resets_on_last_round(self):
    rounds = [
      {'stats': {1: {'match_assists': 3}}, 'last_round': True},
      {'stats': {1: {'match_assists': 2}}, 'last_round': False},
    ]
    compute_assists(rounds)
    # After last_round=True, assists reset
    assert rounds[1]['stats'][1]['assists'] == 2


# ---------------------------------------------------------------------------
# rate_players_by_season
# ---------------------------------------------------------------------------

from truescrub.updater.recalculate import rate_players_by_season


class TestRatePlayersBySeason:
  def test_seasons_computed_independently(self):
    s1_rounds = [_round_row(1, winner=1, loser=2, season_id=1)]
    s2_rounds = [_round_row(2, winner=2, loser=1, season_id=2)]

    rounds_by_season = {1: s1_rounds, 2: s2_rounds}
    skills, history = rate_players_by_season(rounds_by_season, TEAMS)

    # In season 1, team 1 won → player 100 rating goes up
    assert skills[(100, 1)].mu > trueskill.Rating().mu
    # In season 2, team 2 won → player 100 rating goes down
    assert skills[(100, 2)].mu < trueskill.Rating().mu

  def test_returns_history_per_season(self):
    rounds_by_season = {
      1: [_round_row(1, winner=1, loser=2, season_id=1)],
      2: [_round_row(2, winner=1, loser=2, season_id=2)],
    }
    _, history = rate_players_by_season(rounds_by_season, TEAMS)
    assert set(history.keys()) == {1, 2}
    assert all(isinstance(h, SkillHistory) for h in history[1])


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
