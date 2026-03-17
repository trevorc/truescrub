import argparse
import itertools
import math
import operator
from typing import List, Iterable, Set, Dict, Any, Tuple

import trueskill
from truescrub.db import get_skill_db, get_season_players
from truescrub.matchmaking import win_probability
from truescrub.models import Player


def get_assignment_quality(teams: List[List[trueskill.Rating]]):
  if not teams:
    raise ValueError('cannot compute assignment quality for no teams')
  quality = 0.0
  pow = 0
  for team_a, team_b in itertools.combinations(teams, 2):
    quality += math.log(trueskill.quality((team_a, team_b)))
    pow += 1
  return math.pow(math.exp(quality), 1.0 / pow)


def mmr_sum(team: List[trueskill.Rating]) -> float:
  return sum(skill.mu - 2 * skill.sigma for skill in team)


def generate_bracket(teams_count: int) -> List[int]:
  if teams_count < 2:
    return [1]
  slots = 2 ** math.ceil(math.log2(teams_count))
  bracket = [1, 2]
  while len(bracket) < slots:
    next_bracket = []
    for seed in bracket:
      next_bracket.append(seed)
      next_bracket.append(len(bracket) * 2 + 1 - seed)
    bracket = next_bracket
  return bracket


def build_bracket_tree(bracket: List[int], n: int) -> Any:
  leaves: List[Any] = [seed - 1 if seed <= n else 'Bye' for seed in bracket]
  while len(leaves) > 1:
    next_leaves: List[Any] = []
    for i in range(0, len(leaves), 2):
      left = leaves[i]
      right = leaves[i + 1]
      if left == 'Bye' and right == 'Bye':
        next_leaves.append('Bye')
      elif left == 'Bye':
        next_leaves.append(right)
      elif right == 'Bye':
        next_leaves.append(left)
      else:
        next_leaves.append((left, right))
    leaves = next_leaves
  return leaves[0]


def evaluate_bracket_tree(
    tree: Any, teams: List[List[trueskill.Rating]]
) -> Tuple[float, Dict[int, float]]:
  if isinstance(tree, int):
    return 0.0, {tree: 1.0}
  if tree == 'Bye':
    return 0.0, {}

  left, right = tree
  left_sum, left_probs = evaluate_bracket_tree(left, teams)
  right_sum, right_probs = evaluate_bracket_tree(right, teams)

  total_quality = left_sum + right_sum
  expected_match_quality = 0.0
  winner_probs = {}

  for tl, pl in left_probs.items():
    for tr, pr in right_probs.items():
      match_prob = pl * pr
      p_tl_wins = win_probability(trueskill.global_env(), teams[tl], teams[tr])
      winner_probs[tl] = winner_probs.get(tl, 0.0) + match_prob * p_tl_wins
      winner_probs[tr] = winner_probs.get(tr, 0.0) + match_prob * (1.0 - p_tl_wins)
      log_quality = math.log(trueskill.quality((teams[tl], teams[tr])))
      expected_match_quality += match_prob * log_quality

  return total_quality + expected_match_quality, winner_probs


def general_expected_quality(teams: List[List[trueskill.Rating]]) -> float:
  n = len(teams)
  if n < 2:
      raise ValueError('tournament needs at least 2 teams')
  bracket = generate_bracket(n)
  tree = build_bracket_tree(bracket, n)
  total_qual, _ = evaluate_bracket_tree(tree, teams)
  return math.exp(total_qual / (n - 1))


def tournament_eval(teams: List[List[trueskill.Rating]]) -> float:
  """Sorts teams in place"""
  teams.sort(key=mmr_sum, reverse=True)
  return general_expected_quality(teams)


def get_players_with_overrides(
    skill_db, season: int, player_ids: Set[int], overrides: Iterable[Player]
) -> Dict[int, Player]:
  players = {
    player.player_id: player
    for player in get_season_players(skill_db, season)
    if player.player_id in player_ids
  }
  for override in overrides:
    players[override.player_id] = override
  return players


def parse_overrides(overrides_spec: List[str]) -> Dict[int, Player]:
  overrides = {}
  for spec in overrides_spec:
    steamid, name, mu, sigma = spec.split(':', maxsplit=4)
    overrides[int(steamid)] = Player(
        player_id=int(steamid),
        steam_name=name,
        skill_mean=float(mu),
        skill_stdev=float(sigma),
        impact_rating=0.0,
    )
  return overrides


def stdev(xs):
  count = 0
  acc1 = 0
  acc2 = 0
  for x in xs:
    count += 1
    acc1 += x
    acc2 += x ** 2
  if count <= 1:
    return 0.0
  mean = acc1 / count
  variance = (acc2 - acc1 * mean) / count
  return math.sqrt(variance)


def print_match(teams: Iterable[List[Player]], quality: float, team_size: int):
  annotated = [{
    'average_mmr': sum(player.mmr for player in team) / float(team_size),
    'players': list(team),
  } for team in teams]
  annotated.sort(key=operator.itemgetter('average_mmr'), reverse=True)

  skill_var = stdev(team['average_mmr'] for team in annotated)
  print(f'Quality: {100.0 * quality:.2f}%, '
        f'Team Skill Stdev: {skill_var:.2f}')

  for team_no in range(len(annotated)):
    team = annotated[team_no]
    team['players'].sort(key=operator.attrgetter('mmr'), reverse=True)
    print('    Team {} (Avg MMR {}): {}'.format(
        team_no + 1,
        int(team['average_mmr']),
        ', '.join(player.steam_name
                  for player in team['players']),
        ))
  print()


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('-s', '--season', type=int, default=4,
                          help='get ratings from season')
  arg_parser.add_argument('-m', '--method', choices='cs', default='s',
                          help='c = evaluate pairwise combos, '
                               's = simulate tournament')
  arg_parser.add_argument('-o', '--overrides', action='append',
                          default=[], metavar='ID:NAME:MU:SIGMA')
  arg_parser.add_argument('teams', metavar='STEAMID,STEAMID,...', nargs='*',
                          help='teams')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()

  team_configurations = [
    [int(player_id) for player_id in team_spec.split(',')]
    for team_spec in opts.teams
  ]
  overrides = parse_overrides(opts.overrides)

  team_size = min(len(team_cfg) for team_cfg in team_configurations)
  all_player_ids = set(itertools.chain(*team_configurations))

  with get_skill_db() as skill_db:
    players = get_players_with_overrides(
        skill_db, opts.season, all_player_ids, overrides.values())
    teams = [
      [players[player_id] for player_id in team_cfg]
      for team_cfg in team_configurations
    ]

  skills = [[player.skill for player in team] for team in teams]
  if opts.method == 'c':
    quality = get_assignment_quality(skills)
  else:
    quality = tournament_eval(skills)

  print_match(teams=teams, quality=quality, team_size=team_size)


if __name__ == '__main__':
  main()
