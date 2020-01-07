import json
import bisect
import logging
import operator
import datetime
import itertools
import collections
from typing import Optional

import trueskill

from .. import db


logger = logging.getLogger(__name__)


class NoRounds(Exception):
    pass


def load_seasons(game_db, skill_db):
    db.replace_seasons(skill_db, db.get_season_rows(game_db))


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

        placeholders = str.join(',', ['(?, ?)'] * len(team))
        params = [param
                  for player_id in team
                  for param in (team_id, player_id)]
        cursor.execute('''
        INSERT INTO team_membership (team_id, player_id)
        VALUES {}
        '''.format(placeholders), params)
        memberships[team] = team_id

    return memberships


def insert_players(skill_db, player_states):
    if len(player_states) == 0:
        return

    players = {}
    for state in player_states:
        if state['steam_name'] != 'unconnected':
            players[int(state['steam_id'])] = state['steam_name']

    db.upsert_player_names(skill_db, players)


def compute_mvp(state: dict) -> Optional[int]:
    previous_allplayers = state['previously'].get('allplayers', {})

    mvp_counts = {
        steam_id: player['match_stats']['mvps']
        for steam_id, player in state['allplayers'].items()
    }

    previous_mvps = {
        steam_id: player['match_stats']['mvps']
        for steam_id, player in previous_allplayers.items()
        if 'mvps' in previous_allplayers.get(steam_id, {}).get('match_stats', {})
    }

    try:
        mvp = next(
                int(steam_id)
                for steam_id in mvp_counts
                if steam_id in previous_mvps
                and mvp_counts[steam_id] - previous_mvps[steam_id] > 0)
    except StopIteration:
        # Not sure why, but sometimes there is no MVP data in
        # the state's previously.allplayers
        mvp = None

    return mvp


def parse_game_state(
        season_starts: [datetime.datetime],
        season_ids: {datetime.datetime: int},
        game_state_json: str):
    state = json.loads(game_state_json)
    if not (state.get('round', {}).get('phase') == 'over' and
            state.get('previously', {}).get('round', {}).get('phase') == 'live'):
        return
    if 'allplayers' not in state or 'win_team' not in state['round']:
        return
    win_team = state['round']['win_team']
    team_steamids = [(player['team'], int(steamid))
                     for steamid, player in state['allplayers'].items()]
    team_steamids.sort()
    team_members = {
        team: tuple(sorted(item[1] for item in group))
        for team, group in itertools.groupby(
                team_steamids, operator.itemgetter(0))}
    if len(team_members) != 2:
        return
    lose_team = next(iter(set(team_members.keys()) - {win_team}))

    mvp = compute_mvp(state)

    new_player_states = [
        {
            'teammates': team_members[player['team']],
            'round': state['map']['round'],
            'team': player['team'],
            'steam_id': steamid,
            'steam_name': player['name'],
            'round_won': player['team'] == win_team,
        }
        for steamid, player in state['allplayers'].items()
    ]

    created_at = datetime.datetime.utcfromtimestamp(
            state['provider']['timestamp'])

    season_index = bisect.bisect_left(season_starts, created_at) - 1
    season_id = season_ids[season_starts[season_index]]

    new_round = {
        'created_at': created_at,
        'season_id': season_id,
        'winner': team_members[win_team],
        'loser': team_members[lose_team],
        'mvp': mvp,
    }

    return new_round, new_player_states


def parse_game_states(game_db, game_state_range):
    season_ids = db.get_seasons_by_start_date(game_db)
    season_starts = list(season_ids.keys())

    game_states = db.get_game_states(game_db, game_state_range)

    player_states = []
    rounds = []
    max_game_state_id = 0

    for (game_state_id, created_at, game_state_json) in game_states:
        parsed_game_state = parse_game_state(season_starts, season_ids,
                                             game_state_json)
        if parsed_game_state is not None:
            new_round, new_player_states = parsed_game_state
            rounds.append(new_round)
            player_states.extend(new_player_states)
            max_game_state_id = max(max_game_state_id, game_state_id)

    return rounds, player_states, max_game_state_id


def compute_rounds(skill_db, rounds, player_states):
    insert_players(skill_db, player_states)
    round_teams = {player_state['teammates'] for player_state in player_states}
    teams_to_ids = replace_teams(skill_db, round_teams)
    fixed_rounds = [
        {
            'created_at': rnd['created_at'],
            'season_id': rnd['season_id'],
            'winner': teams_to_ids[rnd['winner']],
            'loser': teams_to_ids[rnd['loser']],
            'mvp': rnd['mvp'],
        }
        for rnd in rounds
    ]
    return db.insert_rounds(skill_db, fixed_rounds)


def compute_rounds_and_players(game_db, skill_db, game_state_range=None) \
        -> (int, (int, int)):
    rounds, player_states, max_game_state_id = \
        parse_game_states(game_db, game_state_range)
    new_rounds = compute_rounds(skill_db, rounds, player_states) \
        if len(rounds) > 0 \
        else None
    return max_game_state_id, new_rounds


def rate_players(rounds: [dict], teams: [dict],
        current_ratings: {int: trueskill.Rating} = None) \
        -> {int: trueskill.Rating}:
    ratings = collections.defaultdict(trueskill.Rating)
    if current_ratings is not None:
        ratings.update(current_ratings)

    for round in rounds:
        rating_groups = (
            {player_id: ratings[player_id]
             for player_id in teams[round['winner']]},
            {player_id: ratings[player_id]
             for player_id in teams[round['loser']]},
        )
        new_ratings = trueskill.rate(rating_groups)
        for rating in new_ratings:
            ratings.update(rating)
    ratings.default_factory = None
    return ratings


def rate_players_by_season(
        rounds_by_season: {int: [dict]}, teams: [dict],
        ratings_by_season: {int: {int: trueskill.Rating}} = None) \
        -> {(int, int): trueskill.Rating}:
    skills = {}
    if ratings_by_season is None:
        ratings_by_season = {}
    for season, rounds in rounds_by_season.items():
        new_ratings = rate_players(
                rounds, teams, ratings_by_season.get(season))
        for player_id, rating in new_ratings.items():
            skills[(player_id, season)] = rating
    return skills


def recalculate_ratings(skill_db, new_rounds: (int, int)):
    logger.debug('recalculating for rounds between %d and %d', *new_rounds)

    all_rounds = db.get_all_rounds(skill_db, new_rounds)
    teams = db.get_all_teams(skill_db)

    player_ratings = db.get_overall_ratings(skill_db)
    ratings = rate_players(all_rounds, teams, player_ratings)
    db.update_player_skills(skill_db, ratings)

    rounds_by_season = {
        season_id: list(rounds)
        for season_id, rounds in itertools.groupby(
                all_rounds, operator.itemgetter('season_id'))
    }
    season_ratings = db.get_ratings_by_season(
            skill_db, seasons=list(rounds_by_season.keys()))
    skills_by_season = rate_players_by_season(
            rounds_by_season, teams, season_ratings)
    db.replace_season_skills(skill_db, skills_by_season)

    logger.debug('recalculation for %d-%d completed', *new_rounds)


def compute_skill_db(game_db, skill_db):
    load_seasons(game_db, skill_db)
    max_game_state_id, new_rounds = \
        compute_rounds_and_players(game_db, skill_db)
    if new_rounds is not None:
        recalculate_ratings(skill_db, new_rounds)
    db.save_game_state_progress(skill_db, max_game_state_id)


def recalculate():
    new_skill_db = db.SKILL_DB_NAME + '.new'
    with db.get_game_db() as game_db, \
            db.get_skill_db(new_skill_db) as skill_db:
        db.initialize_skill_db(skill_db)
        compute_skill_db(game_db, skill_db)
        skill_db.commit()
    db.replace_skill_db(new_skill_db)
