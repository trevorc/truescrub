import argparse
import multiprocessing
import optuna
import pathlib
from typing import List, Iterable

from truescrub.db import get_skill_db
from truescrub.models import Player
from truescrub.tools.genetic import parse_players_json, print_eval
from truescrub.tools.teameval import \
  tournament_eval, print_match, get_players_with_overrides


def compute_matches_optuna(
    players: Iterable[Player], seed: int,
    trials: int, results: int, team_size: int) -> List[dict]:
  players_list = list(players)
  num_players = len(players_list)

  def objective(trial):
    remaining = players_list.copy()
    teams = []
    current_team = []
    for i in range(num_players):
      idx = trial.suggest_int(f'p_{i}', 0, len(remaining) - 1)
      player = remaining.pop(idx)
      current_team.append(player)
      if len(current_team) == team_size:
        teams.append(current_team)
        current_team = []
    if current_team:
      teams.append(current_team)

    team_skills = [
      [player.skill for player in team]
      for team in teams
    ]
    return tournament_eval(team_skills)

  # Optuna can be noisy by default
  optuna.logging.set_verbosity(optuna.logging.WARNING)

  sampler = optuna.samplers.TPESampler(seed=seed)
  study = optuna.create_study(direction="maximize", sampler=sampler)

  # Safe for parallel evaluation: objective only reads the shared trueskill
  # global environment (no setup() calls) and never touches the DB.
  study.optimize(objective, n_trials=trials, n_jobs=-1)

  completed_trials = [t for t in study.trials if
                      t.state == optuna.trial.TrialState.COMPLETE]
  completed_trials.sort(key=lambda t: t.value, reverse=True)

  # We want unique parameter combinations in the top results. Let's filter duplicates.
  # (Since permutations with identical team assignments yield the same matching)
  top_trials = []
  seen_qualities = set()
  for t in completed_trials:
    if len(top_trials) >= results:
      break

    # simple deduplication by quality to avoid identical exact matches
    # (team permutations have the precise same quality)
    rounded_q = round(t.value, 6)
    if rounded_q not in seen_qualities:
      seen_qualities.add(rounded_q)
      top_trials.append(t)

  # If deduplication filtered out too many, just pad it back up
  if len(top_trials) < results and len(completed_trials) >= results:
    top_trials = completed_trials[:results]

  matches = []
  for t in top_trials:
    remaining = players_list.copy()
    teams = []
    current_team = []
    for i in range(num_players):
      idx = t.params[f'p_{i}']
      player = remaining.pop(idx)
      current_team.append(player)
      if len(current_team) == team_size:
        teams.append(current_team)
        current_team = []
    if current_team:
      teams.append(current_team)

    matches.append({
      'team_size': team_size,
      'quality': t.value,
      'teams': teams,
    })

  return matches


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('--seed', type=int, default=1337,
                          help='random seed')
  arg_parser.add_argument('--season', type=int,
                          default=4, help='use skills from this season')
  arg_parser.add_argument('--trials', type=int, default=200,
                          help='number of trials to run')
  arg_parser.add_argument('--results', '-n', type=int, default=10,
                          help='show this many results')
  arg_parser.add_argument('--team-size', '-z', type=int, default=3,
                          help='players per team')
  arg_parser.add_argument('--print-eval', action='store_true')
  arg_parser.add_argument('players', type=pathlib.Path,
                          help='path to JSON file specifying players')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()
  player_ids, overrides = parse_players_json(opts.players)

  with get_skill_db() as skill_db:
    season = opts.season
    seed = opts.seed

    players = get_players_with_overrides(
      skill_db, season, player_ids, overrides
    ).values()
    do_print_eval: bool = opts.print_eval

    opts_dict = {key: val for key, val in opts.__dict__.items()
                 if key not in {'season', 'print_eval', 'players'}}

    matches = compute_matches_optuna(players, **opts_dict)

    for match in matches:
      if do_print_eval:
        print_eval(overrides, season=season, seed=seed,
                   **match)
      else:
        print_match(**match)


if __name__ == '__main__':
  main()
