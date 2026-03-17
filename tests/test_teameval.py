import math

import pytest
import trueskill
from truescrub.tools.teameval import (
  general_expected_quality,
  generate_bracket,
  build_bracket_tree,
  evaluate_bracket_tree,
)


class TestGenerateBracket:
  @pytest.mark.parametrize('n', range(2, 6))
  def test_length_is_power_of_two(self, n):
    bracket = generate_bracket(n)
    assert len(bracket) == 2 ** math.ceil(math.log2(n))

  @pytest.mark.parametrize('n', range(2, 6))
  def test_is_permutation(self, n):
    bracket = generate_bracket(n)
    assert sorted(bracket) == list(range(1, len(bracket) + 1))

  @pytest.mark.parametrize('n', range(2, 6))
  def test_top_seeds_in_opposite_halves(self, n):
    bracket = generate_bracket(n)
    half = len(bracket) // 2
    left_half = set(bracket[:half])
    right_half = set(bracket[half:])
    assert (1 in left_half) != (1 in right_half)
    assert (2 in left_half) != (2 in right_half)
    assert not ({1, 2} <= left_half or {1, 2} <= right_half)


# -- build_bracket_tree ------------------------------------------------------

def collect_leaves(tree):
  """Collect all integer leaves from a bracket tree."""
  if isinstance(tree, int):
    return [tree]
  if tree == 'Bye':
    return []
  left, right = tree
  return collect_leaves(left) + collect_leaves(right)


class TestBuildBracketTree:
  @pytest.mark.parametrize('n', range(2, 6))
  def test_all_teams_present(self, n):
    bracket = generate_bracket(n)
    tree = build_bracket_tree(bracket, n)
    leaves = collect_leaves(tree)
    assert sorted(leaves) == list(range(n))

  @pytest.mark.parametrize('n', range(2, 6))
  def test_no_byes_remain(self, n):
    """After collapsing, no 'Bye' should remain in the tree."""
    bracket = generate_bracket(n)
    tree = build_bracket_tree(bracket, n)

    def has_bye(t):
      if t == 'Bye':
        return True
      if isinstance(t, int):
        return False
      return has_bye(t[0]) or has_bye(t[1])

    assert not has_bye(tree)

  def test_two_teams_is_simple_pair(self):
    tree = build_bracket_tree(generate_bracket(2), 2)
    # Should be a tuple of two leaf ints
    assert isinstance(tree, tuple)
    assert sorted(tree) == [0, 1]

  def test_power_of_two_is_full_tree(self):
    """4 teams should produce a complete binary tree with no collapsed byes."""
    tree = build_bracket_tree(generate_bracket(4), 4)
    # ((a, b), (c, d))
    assert isinstance(tree, tuple)
    assert isinstance(tree[0], tuple)
    assert isinstance(tree[1], tuple)


# -- evaluate_bracket_tree ---------------------------------------------------

def make_teams(*mus):
  """Create single-player teams with given mus and sigma=1."""
  return [[trueskill.Rating(mu, 1)] for mu in mus]


class TestEvaluateBracketTree:
  def test_leaf_returns_certain_winner(self):
    teams = make_teams(25)
    total_qual, probs = evaluate_bracket_tree(0, teams)
    assert total_qual == 0.0
    assert probs == {0: 1.0}

  def test_winner_probs_sum_to_one(self):
    teams = make_teams(30, 25, 20)
    bracket = generate_bracket(3)
    tree = build_bracket_tree(bracket, 3)
    _, probs = evaluate_bracket_tree(tree, teams)
    assert sum(probs.values()) == pytest.approx(1.0)

  @pytest.mark.parametrize('n', range(2, 7))
  def test_winner_probs_sum_to_one_various_sizes(self, n):
    teams = make_teams(*range(30, 30 - 5 * n, -5))
    bracket = generate_bracket(n)
    tree = build_bracket_tree(bracket, n)
    _, probs = evaluate_bracket_tree(tree, teams)
    assert sum(probs.values()) == pytest.approx(1.0)

  def test_equal_teams_equal_probs(self):
    teams = make_teams(25, 25)
    tree = build_bracket_tree(generate_bracket(2), 2)
    _, probs = evaluate_bracket_tree(tree, teams)
    assert probs[0] == pytest.approx(0.5)
    assert probs[1] == pytest.approx(0.5)

  def test_stronger_team_has_higher_prob(self):
    teams = make_teams(30, 20)
    tree = build_bracket_tree(generate_bracket(2), 2)
    _, probs = evaluate_bracket_tree(tree, teams)
    assert probs[0] > probs[1]

  def test_total_quality_is_non_positive(self):
    teams = make_teams(30, 25, 20)
    bracket = generate_bracket(3)
    tree = build_bracket_tree(bracket, 3)
    total_qual, _ = evaluate_bracket_tree(tree, teams)
    assert total_qual <= 0.0

  def test_two_identical_teams_quality_matches_pairwise(self):
    """For 2 identical teams, total_log_quality should equal log(quality)."""
    r = trueskill.Rating(25, 3)
    teams = [[r], [r]]
    tree = build_bracket_tree(generate_bracket(2), 2)
    total_qual, _ = evaluate_bracket_tree(tree, teams)
    expected = math.log(trueskill.quality((teams[0], teams[1])))
    assert total_qual == pytest.approx(expected)


# -- general_expected_quality ------------------------------------------------

class TestGeneralExpectedQuality:
  def test_output_in_valid_range(self):
    teams = make_teams(30, 25, 20)
    quality = general_expected_quality(teams)
    assert 0.0 < quality <= 1.0

  @pytest.mark.parametrize('n', range(2, 7))
  def test_output_in_valid_range_various_sizes(self, n):
    teams = make_teams(*range(30, 30 - 5 * n, -5))
    quality = general_expected_quality(teams)
    assert 0.0 < quality <= 1.0

  def test_two_identical_teams_equals_pairwise_quality(self):
    """For 2 identical teams, result should equal trueskill.quality()."""
    r = trueskill.Rating(25, 3)
    teams = [[r], [r]]
    expected = trueskill.quality((teams[0], teams[1]))
    assert general_expected_quality(teams) == pytest.approx(expected)

  def test_balanced_better_than_imbalanced(self):
    """A more balanced tournament should produce higher quality."""
    balanced = make_teams(25, 25, 25)
    imbalanced = make_teams(40, 25, 10)
    assert general_expected_quality(balanced) > general_expected_quality(
      imbalanced)

  def test_rejects_fewer_than_two_teams(self):
    with pytest.raises(ValueError):
      general_expected_quality(make_teams(25))

  def test_identical_teams_maximizes_quality(self):
    """All-identical teams should produce the maximum possible quality."""
    identical = make_teams(25, 25, 25, 25)
    varied = make_teams(30, 25, 20, 15)
    assert general_expected_quality(identical) >= general_expected_quality(
      varied)


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
