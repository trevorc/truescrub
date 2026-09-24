"""Pins SkillTracker's closed form against trueskill.rate.

SkillTracker reimplements the two-team, no-draw TrueSkill update to avoid the
library's factor graph. These tests are the contract that keeps the two in
agreement, so they compare against trueskill.rate rather than against
recorded numbers.
"""
import pytest
import trueskill

from truescrub.models import setup_trueskill
from truescrub.rating import SkillTracker

setup_trueskill()

TOLERANCE = 1e-4


def rate_with_library(matches, initial=None):
  """The factor-graph equivalent of a sequence of SkillTracker.rate_match."""
  ratings = dict(initial or {})
  for winners, losers in matches:
    rating_groups = (
      {player_id: ratings.get(player_id, trueskill.Rating())
       for player_id in winners},
      {player_id: ratings.get(player_id, trueskill.Rating())
       for player_id in losers},
    )
    for group in trueskill.rate(rating_groups):
      ratings.update(group)
  return ratings


def assert_matches_library(matches, initial=None):
  tracker = SkillTracker(initial=initial)
  for winners, losers in matches:
    tracker.rate_match(winners, losers)
  actual = tracker.ratings()
  expected = rate_with_library(matches, initial)

  assert set(actual) == set(expected)
  for player_id, rating in expected.items():
    assert actual[player_id].mu == pytest.approx(rating.mu, abs=TOLERANCE)
    assert actual[player_id].sigma == pytest.approx(
      rating.sigma, abs=TOLERANCE)


class TestAgreesWithLibrary:
  def test_single_match(self):
    assert_matches_library([({1, 2}, {3, 4})])

  def test_repeated_wins_accumulate_identically(self):
    assert_matches_library([({1, 2}, {3, 4})] * 50)

  def test_alternating_winners(self):
    assert_matches_library([
      ({1, 2}, {3, 4}) if i % 2 else ({3, 4}, {1, 2})
      for i in range(40)
    ])

  def test_one_versus_one(self):
    assert_matches_library([({1}, {2})] * 20)

  def test_uneven_team_sizes(self):
    assert_matches_library([({1}, {2, 3, 4, 5})] * 20)

  def test_five_versus_five(self):
    assert_matches_library([({1, 2, 3, 4, 5}, {6, 7, 8, 9, 10})] * 30)

  def test_continues_from_existing_ratings(self):
    assert_matches_library(
      [({1, 2}, {3, 4})] * 10,
      initial={
        1: trueskill.Rating(1200.0, 180.0),
        3: trueskill.Rating(800.0, 90.0),
      })

  def test_players_joining_later(self):
    assert_matches_library([
      ({1, 2}, {3, 4}),
      ({1, 5}, {6, 4}),
      ({5, 6}, {1, 2}),
    ])

  def test_overlapping_rosters(self):
    assert_matches_library([
      ({1, 2, 3}, {4, 5, 6}),
      ({1, 4}, {2, 5}),
      ({3, 6}, {1, 5}),
    ] * 10)


class TestSkillProgression:
  def test_winners_gain_and_losers_lose(self):
    tracker = SkillTracker()
    tracker.rate_match({1}, {2})
    assert tracker.rating(1).mu > tracker.rating(2).mu

  def test_uncertainty_falls_with_more_matches(self):
    tracker = SkillTracker()
    tracker.rate_match({1}, {2})
    after_one = tracker.rating(1).sigma
    for _ in range(20):
      tracker.rate_match({1}, {2})
    assert tracker.rating(1).sigma < after_one

  def test_unrated_player_starts_at_environment_default(self):
    env = trueskill.global_env()
    tracker = SkillTracker()
    tracker.rate_match({1}, {2})
    assert tracker.rating(1).mu != env.mu
    assert 3 not in tracker.ratings()


class TestRejectsUnsupportedInput:
  def test_rejects_nonzero_draw_probability(self, monkeypatch):
    monkeypatch.setattr(
      trueskill, 'global_env',
      lambda: trueskill.TrueSkill(draw_probability=0.1))
    with pytest.raises(ValueError, match='draw_probability'):
      SkillTracker().rate_match({1}, {2})

  def test_rejects_empty_winning_team(self):
    with pytest.raises(ValueError, match='each side'):
      SkillTracker().rate_match(set(), {1})

  def test_rejects_empty_losing_team(self):
    with pytest.raises(ValueError, match='each side'):
      SkillTracker().rate_match({1}, set())


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xv', __file__]))
