import json
import time
import bisect
import logging
import operator
import datetime
import itertools
from typing import Optional

import trueskill

from .. import db
from ..models import RoundRow, SkillHistory

logger = logging.getLogger(__name__)


class NoRounds(Exception):
    pass


# Rating2 = 0.2778*Kills - 0.2559*Deaths + 0.00651*ADR + 0.00633*KAST + 0.18377


def dump_rounds(game_db, outfile, indent=False):
    game_states = db.get_game_states(game_db, None)
    for game_state_id, created_at, game_state_str in game_states:
        state = json.loads(game_state_str)
        if not is_round_transition(state):
            continue
        json.dump(state, outfile, indent=2 if indent else None)
        outfile.write('\n')


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


def calculate_round_stats(state: dict) -> {int: dict}:
    previous_allplayers = state['previously'].get('allplayers', {})

    assist_counts = {
        steam_id: player['match_stats']['assists']
        for steam_id, player in state['allplayers'].items()
    }

    previous_assists = {
        steam_id: player['match_stats']['assists']
        for steam_id, player in previous_allplayers.items()
        if 'assists' in previous_allplayers.get(
                steam_id, {}).get('match_stats', {})
    }

    return {
        int(steam_id): {
            'kills': player['state']['round_kills'],
            'assists': assist_counts[steam_id] -
                       previous_assists.get(steam_id, 0),
            'survived': player['state']['health'] > 0,
            'damage': player['state']['round_totaldmg'],
        }
        for steam_id, player in state['allplayers'].items()
    }


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


def is_round_transition(state):
    current_phase = state.get('round', {}).get('phase')
    previously = state.get('previously', {})
    return current_phase == 'over' \
           and previously.get('round', {}).get('phase') == 'live' \
           and 'allplayers' in state \
           and 'win_team' in state['round']


def parse_game_state(
        season_starts: [datetime.datetime],
        season_ids: {datetime.datetime: int},
        game_state_id: int,
        game_state_json: str):
    state = json.loads(game_state_json)
    if not is_round_transition(state):
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

    round_stats = calculate_round_stats(state)

    new_round = {
        'game_state_id': game_state_id,
        'created_at': created_at,
        'season_id': season_id,
        'winner': team_members[win_team],
        'loser': team_members[lose_team],
        'mvp': mvp,
        'map_name': state['map']['name'],
        'stats': round_stats,
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
                                             game_state_id, game_state_json)
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

    db.replace_maps(skill_db, {rnd['map_name'] for rnd in rounds})

    fixed_rounds = [
        {
            'created_at': rnd['created_at'],
            'season_id': rnd['season_id'],
            'game_state_id': rnd['game_state_id'],
            'winner': teams_to_ids[rnd['winner']],
            'loser': teams_to_ids[rnd['loser']],
            'mvp': rnd['mvp'],
            'map_name': rnd['map_name'],
        }
        for rnd in rounds
    ]
    round_range = db.insert_rounds(skill_db, fixed_rounds)

    round_stats = {
        rnd['game_state_id']: rnd['stats']
        for rnd in rounds
    }
    db.insert_round_stats(skill_db, round_stats)

    return round_range


def compute_rounds_and_players(game_db, skill_db, game_state_range=None) \
        -> (int, (int, int)):
    rounds, player_states, max_game_state_id = \
        parse_game_states(game_db, game_state_range)
    new_rounds = compute_rounds(skill_db, rounds, player_states) \
        if len(rounds) > 0 \
        else None
    return max_game_state_id, new_rounds


# TODO: extract out history tracking for clients that don't need it
def compute_player_skills(rounds: [RoundRow], teams: [dict],
        current_ratings: {int: trueskill.Rating} = None) \
        -> ({int: trueskill.Rating}, [SkillHistory]):
    ratings = {}
    if current_ratings is not None:
        ratings.update(current_ratings)
    skill_history = []

    for round in rounds:
        rating_groups = (
            {player_id: ratings.get(player_id, trueskill.Rating())
             for player_id in teams[round.winner]},
            {player_id: ratings.get(player_id, trueskill.Rating())
             for player_id in teams[round.loser]},
        )
        new_ratings = trueskill.rate(rating_groups)
        for rating in new_ratings:
            ratings.update(rating)
            for player_id, skill in rating.items():
                skill_history.append(SkillHistory(
                        round_id=round.round_id,
                        player_id=player_id,
                        skill=skill))

    return ratings, skill_history


def rate_players_by_season(
        rounds_by_season: {int: [RoundRow]}, teams: [dict],
        skills_by_season: {int: {int: trueskill.Rating}} = None) \
        -> ({(int, int): trueskill.Rating}, {int: SkillHistory}):
    skills = {}
    if skills_by_season is None:
        skills_by_season = {}
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
    skills, skill_history = compute_player_skills(all_rounds, teams, player_ratings)
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
    start = time.process_time()
    logger.debug('recalculating for rounds between %d and %d', *new_rounds)

    all_rounds = db.get_all_rounds(skill_db, new_rounds)
    # TODO: limit to teams in all_rounds
    teams = db.get_all_teams(skill_db)

    recalculate_overall_ratings(skill_db, all_rounds, teams)
    recalculate_season_ratings(skill_db, all_rounds, teams)

    end = time.process_time()
    logger.debug('recalculation for %d-%d completed in %d ms',
                 new_rounds[0], new_rounds[1], (1000 * (end - start)))


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
