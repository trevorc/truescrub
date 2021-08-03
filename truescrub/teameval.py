import argparse
import itertools
import math
import operator
import random
from typing import List, Iterable, Set, Dict

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


def run_match(team_a, team_b):
  if random.random() <= win_probability(trueskill.global_env(), team_a, team_b):
    return team_a
  return team_b


TRIAL_COUNT = 3


def tournament_simulator():
  matches = 0
  raw_quality = 0.0
  quality = None

  while True:
    team1, team2 = yield quality
    raw_quality += math.log(trueskill.quality((team1, team2)))
    matches += 1
    quality = math.pow(math.exp(raw_quality), 1.0 / matches)


def three_team_single_elimination(tournament, teams):
  if len(teams) != 3:
    raise ValueError('must supply 3 teams')

  quality = next(tournament)
  for x in range(TRIAL_COUNT):
    # Semifinals
    tournament.send((teams[1], teams[2]))
    sf_winner = run_match(teams[1], teams[2])

    # Grand Finals
    quality = tournament.send((teams[0], sf_winner))
  return quality


def four_team_single_elimination(tournament, teams):
  if len(teams) != 4:
    raise ValueError('must supply 4 teams')

  quality = next(tournament)
  for x in range(TRIAL_COUNT):
    # Semifinals
    tournament.send((teams[0], teams[3]))
    sf1_winner = run_match(teams[0], teams[3])
    tournament.send((teams[1], teams[2]))
    sf2_winner = run_match(teams[1], teams[2])

    # Grand Finals
    quality = tournament.send((sf1_winner, sf2_winner))
  return quality


def five_team_single_elimination(tournament, teams):
  if len(teams) != 5:
    raise ValueError('must supply 5 teams')

  quality = next(tournament)
  for x in range(TRIAL_COUNT):
    tournament.send((teams[3], teams[4]))
    qf_winner = run_match(teams[3], teams[4])

    # Semifinals
    tournament.send((teams[0], qf_winner))
    sf1_winner = run_match(teams[0], qf_winner)
    tournament.send((teams[1], teams[2]))
    sf2_winner = run_match(teams[1], teams[2])

    # Grand Finals
    quality = tournament.send((sf1_winner, sf2_winner))
  return quality


def tournament_eval(teams: List[List[trueskill.Rating]]) -> float:
  """Sorts teams in place"""
  teams.sort(key=mmr_sum, reverse=True)
  tournament = tournament_simulator()
  if len(teams) == 3:
    return three_team_single_elimination(tournament, teams)
  if len(teams) == 4:
    return four_team_single_elimination(tournament, teams)
  if len(teams) == 5:
    return five_team_single_elimination(tournament, teams)
  raise ValueError(f'unsupported team count {len(teams)}')


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
  arg_parser.add_argument('-e', '--seed', type=int, default=1337,
                          help='set random seed')
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
