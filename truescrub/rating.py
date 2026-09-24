"""Two-team TrueSkill rating.

Every match TrueScrub rates is exactly two teams, everyone listed plays, and
the environment sets draw_probability to zero. TrueSkill solves that case in
closed form. trueskill.rate() instead builds a factor graph and runs message
passing per match, which profiling showed to be 95% of a full recalculation
and roughly three million Gaussian allocations over 18570 rounds.

Only that special case lives here. Multiple teams, draws, partial play and the
factor graph remain the library's, and rate_match rejects an environment whose
draw_probability is nonzero. tests/test_rating.py pins this against
trueskill.rate directly.
"""
import math
from typing import Collection, Dict, Iterable, Mapping, Optional

import trueskill


class SkillTracker:
  """Rates two-team matches in sequence, tracking each player's skill.

  Skills are held as mean and variance rather than trueskill.Rating so that a
  match costs a handful of float operations. Ratings are materialized only
  when asked for.
  """

  def __init__(self,
               initial: Optional[Mapping[int, trueskill.Rating]] = None):
    self._env = trueskill.global_env()
    self._beta_sq = self._env.beta ** 2
    self._tau_sq = self._env.tau ** 2
    self._default_mu = self._env.mu
    self._default_variance = self._env.sigma ** 2

    self._means: Dict[int, float] = {}
    self._variances: Dict[int, float] = {}
    if initial is not None:
      for player_id, rating in initial.items():
        self._means[player_id] = rating.mu
        self._variances[player_id] = rating.sigma ** 2

  def rate_match(self, winners: Collection[int],
                 losers: Collection[int]) -> None:
    """Applies one match outcome to the skills of everyone who played."""
    if self._env.draw_probability != 0.0:
      raise ValueError(
        'two-team closed form assumes draw_probability 0, got '
        f'{self._env.draw_probability}')
    if not winners or not losers:
      raise ValueError('a match needs a player on each side')

    means = self._means
    variances = self._variances

    for player_id in self._participants(winners, losers):
      if player_id not in means:
        means[player_id] = self._default_mu
        variances[player_id] = self._default_variance
      # Skill drifts between matches, so TrueSkill widens the prior first.
      variances[player_id] += self._tau_sq

    total_variance = sum(
      variances[player_id]
      for player_id in self._participants(winners, losers))
    c = math.sqrt(
      (len(winners) + len(losers)) * self._beta_sq + total_variance)
    mean_delta = (sum(means[player_id] for player_id in winners) -
                  sum(means[player_id] for player_id in losers)) / c

    # The truncated-Gaussian correction for a win, with no draw margin.
    v = self._env.pdf(mean_delta) / self._env.cdf(mean_delta)
    w = v * (v + mean_delta)
    c_sq = c * c

    for player_id in winners:
      variance = variances[player_id]
      means[player_id] += variance / c * v
      variances[player_id] = variance * (1.0 - variance / c_sq * w)
    for player_id in losers:
      variance = variances[player_id]
      means[player_id] -= variance / c * v
      variances[player_id] = variance * (1.0 - variance / c_sq * w)

  def rating(self, player_id: int) -> trueskill.Rating:
    return trueskill.Rating(self._means[player_id],
                            math.sqrt(self._variances[player_id]))

  def ratings(self) -> Dict[int, trueskill.Rating]:
    return {
      player_id: trueskill.Rating(mean, math.sqrt(self._variances[player_id]))
      for player_id, mean in self._means.items()
    }

  @staticmethod
  def _participants(winners: Collection[int],
                    losers: Collection[int]) -> Iterable[int]:
    yield from winners
    yield from losers
