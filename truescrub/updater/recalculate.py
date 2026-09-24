import itertools
import logging
import operator
import time

from typing import Iterator, List, Dict, Tuple

import trueskill

from truescrub import db
from truescrub.models import (
  RoundRow, SkillHistory, setup_trueskill, EvaluatedRound, PlayerRoundStats
)
from truescrub.rating import SkillTracker
from truescrub.seasoncfg import get_all_seasons
from truescrub.updater.remapper import remap_rounds, apply_player_configurations
from truescrub.updater.state_loader import StateLoader

logger = logging.getLogger(__name__)
setup_trueskill()


class NoRounds(Exception):
  pass


# Rating2 = 0.2778*Kills - 0.2559*Deaths + 0.00651*ADR + 0.00633*KAST + 0.18377


def load_seasons(skill_db):
  db.replace_seasons(skill_db, get_all_seasons())


def replace_teams(skill_db, round_teams):
  cursor = skill_db.cursor()
  memberships = {
    tuple(sorted(members)): team_id
    for team_id, members in db.get_all_teams(skill_db).items()
  }
  missing_teams = set()

  for team in round_teams:
    if team not in memberships:
      missing_teams.add(team)

  for team in missing_teams:
    cursor.execute('INSERT INTO teams DEFAULT VALUES')
    team_id = cursor.lastrowid

    cursor.executemany(
      '''
      INSERT INTO team_membership (team_id, player_id)
      VALUES (?, ?)
      ''', [(team_id, player_id) for player_id in team])
    memberships[team] = team_id

  return memberships


def insert_players(skill_db, player_states):
  if len(player_states) == 0:
    return

  players = {int(state['steam_id']): state['steam_name']
             for state in player_states}

  db.upsert_player_names(skill_db, players)


def evaluate_rounds(raw_rounds) -> Iterator[EvaluatedRound]:
  last_assists = {}

  for rnd in raw_rounds:
    player_stats = {}
    for player_id, raw_stats in rnd['stats'].items():
      assists = raw_stats['match_assists'] - last_assists.get(player_id, 0)
      last_assists[player_id] = raw_stats['match_assists']
      player_stats[player_id] = PlayerRoundStats(
        kills=raw_stats['kills'],
        headshots=raw_stats['headshots'],
        damage=raw_stats['damage'],
        survived=raw_stats['survived'],
        assists=assists
      )

    if rnd['last_round']:
      last_assists = {}

    yield EvaluatedRound(
      game_state_id=rnd['game_state_id'],
      season_id=rnd['season_id'],
      created_at=rnd['created_at'],
      map_name=rnd['map_name'],
      winner_team=frozenset(rnd['winner']),
      loser_team=frozenset(rnd['loser']),
      mvp=rnd['mvp'],
      stats=player_stats
    )


def compute_rounds(skill_db, raw_rounds, player_states):
  insert_players(skill_db, player_states)
  evaluated_rounds = list(evaluate_rounds(raw_rounds))

  all_teams = (
      {rnd.winner_team for rnd in evaluated_rounds} |
      {rnd.loser_team for rnd in evaluated_rounds}
  )
  teams_to_ids = replace_teams(skill_db, all_teams)

  db.replace_maps(skill_db, {rnd.map_name for rnd in evaluated_rounds})

  fixed_rounds = [
    {
      'created_at': rnd.created_at,
      'season_id': rnd.season_id,
      'game_state_id': rnd.game_state_id,
      'winner': teams_to_ids[rnd.winner_team],
      'loser': teams_to_ids[rnd.loser_team],
      'mvp': rnd.mvp,
      'map_name': rnd.map_name,
    }
    for rnd in evaluated_rounds
  ]
  round_range = db.insert_rounds(skill_db, fixed_rounds)

  round_stats = {
    rnd.game_state_id: rnd.stats
    for rnd in evaluated_rounds
  }
  db.insert_round_stats(skill_db, round_stats)

  return round_range


def compute_rounds_and_players(state_loader, skill_db, game_state_range=None) \
    -> Tuple[int, Tuple[int, int]]:
  rap = state_loader.extract_game_states(game_state_range)

  player_states = apply_player_configurations(rap.player_states)

  rounds = remap_rounds(rap.rounds)
  new_rounds = compute_rounds(skill_db, rounds, player_states) \
    if len(rounds) > 0 else None
  return rap.max_game_state_id, new_rounds


# TODO: extract out history tracking for clients that don't need it
def compute_player_skills(
    rounds: List[RoundRow], teams: List[dict],
    current_ratings: Dict[int, trueskill.Rating] | None = None) \
    -> Tuple[Dict[int, trueskill.Rating], List[SkillHistory]]:
  tracker = SkillTracker(initial=current_ratings)
  skill_history = []

  for round in rounds:
    winners = teams[round.winner]
    losers = teams[round.loser]
    tracker.rate_match(winners, losers)
    for player_id in itertools.chain(winners, losers):
      skill_history.append(SkillHistory(
        round_id=round.round_id,
        player_id=player_id,
        skill=tracker.rating(player_id)))

  return tracker.ratings(), skill_history


def rate_players_by_season(
    rounds_by_season: Dict[int, List[RoundRow]], teams: List[dict],
    skills_by_season: Dict[int, Dict[int, trueskill.Rating]] | None = None) \
    -> Tuple[Dict[Tuple[int, int], trueskill.Rating], Dict[int, SkillHistory]]:
  if skills_by_season is None:
    skills_by_season = {}

  skills = {}
  history_by_season = {}
  for season, rounds in rounds_by_season.items():
    new_skills, skill_history = compute_player_skills(
      rounds, teams, skills_by_season.get(season))
    for player_id, rating in new_skills.items():
      skills[(player_id, season)] = rating
    history_by_season[season] = skill_history
  return skills, history_by_season


def recalculate_overall_ratings(skill_db, all_rounds, teams):
  player_ratings = db.get_overall_skills(skill_db)
  skills, skill_history = compute_player_skills(all_rounds, teams,
                                                player_ratings)
  impact_ratings = db.get_overall_impact_ratings(skill_db)
  db.update_player_skills(skill_db, skills, impact_ratings)
  db.replace_overall_skill_history(skill_db, skill_history)


def recalculate_season_ratings(skill_db, all_rounds, teams):
  rounds_by_season = {
    season_id: list(rounds)
    for season_id, rounds in itertools.groupby(
      all_rounds, operator.attrgetter('season_id'))
  }
  current_season_skills = db.get_skills_by_season(
    skill_db, seasons=list(rounds_by_season.keys()))
  new_season_skills, history_by_season = rate_players_by_season(
    rounds_by_season, teams, current_season_skills)
  season_impact_ratings = db.get_impact_ratings_by_season(skill_db)
  db.replace_season_skills(skill_db, new_season_skills, season_impact_ratings)
  db.replace_season_skill_history(skill_db, history_by_season)


def recalculate_ratings(skill_db, new_rounds: (int, int)):
  start = time.perf_counter()
  logger.debug('recalculating for rounds between %d and %d', *new_rounds)

  all_rounds = db.get_all_rounds(skill_db, new_rounds)
  # TODO: limit to teams in all_rounds
  teams = db.get_all_teams(skill_db)

  recalculate_overall_ratings(skill_db, all_rounds, teams)
  recalculate_season_ratings(skill_db, all_rounds, teams)

  end = time.perf_counter()
  logger.debug('recalculation for %d-%d completed in %d ms',
               new_rounds[0], new_rounds[1], (1000 * (end - start)))


def compute_skill_db(state_loader: StateLoader, skill_db):
  load_seasons(skill_db)
  max_game_state_id, new_rounds = \
    compute_rounds_and_players(state_loader, skill_db)
  if new_rounds is not None:
    recalculate_ratings(skill_db, new_rounds)
  db.save_game_state_progress(skill_db, max_game_state_id)


def recalculate(state_loader: StateLoader):
  new_skill_db = db.SKILL_DB_NAME + '.new'
  with db.get_skill_db(new_skill_db) as skill_db:
    db.initialize_skill_db(skill_db)
    compute_skill_db(state_loader, skill_db)
    skill_db.commit()
  db.replace_skill_db(new_skill_db)
