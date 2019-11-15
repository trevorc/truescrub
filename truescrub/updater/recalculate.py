import json
import bisect
import logging
import operator
import datetime
import itertools
import collections

import trueskill

from truescrub.db import enumerate_rows, get_skill_db, get_game_db, \
    initialize_skill_db, SKILL_DB_NAME, replace_skill_db, \
    save_game_state_progress, get_game_states, get_all_rounds, get_all_teams, \
    make_placeholder, update_player_skills, replace_season_skills, \
    get_player_overall_skills, get_ratings_by_season

logger = logging.getLogger(__name__)


def load_seasons(game_db, skill_db):
    game_db_cursor = game_db.cursor()
    game_db_cursor.execute('''
    SELECT *
    FROM seasons
    ''')
    seasons = list(enumerate_rows(game_db_cursor))

    placeholder = make_placeholder(2, len(seasons))
    params = [
        param
        for season in seasons
        for param in season
    ]

    skill_db_cursor = skill_db.cursor()
    skill_db_cursor.execute('''
    REPLACE INTO seasons (season_id, start_date)
    VALUES {}
    '''.format(placeholder), params)


def replace_teams(skill_db, round_teams):
    cursor = skill_db.cursor()
    memberships = {
        tuple(sorted(members)): team_id
        for team_id, members in get_all_teams(skill_db).items()
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


def insert_players(connection, player_states):
    if len(player_states) == 0:
        return

    cursor = connection.cursor()

    players = {}
    for state in player_states:
        if state['steam_name'] != 'unconnected':
            players[int(state['steam_id'])] = state['steam_name']

    placeholder = make_placeholder(2, len(players))
    params = [value
              for player in players.items()
              for value in player]

    cursor.execute('''
    REPLACE INTO players (player_id, steam_name) 
    VALUES {}
    '''.format(placeholder), params)


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

    new_player_states = []

    for steamid, player in state['allplayers'].items():
        new_player_states.append({
            'teammates': team_members[player['team']],
            'round': state['map']['round'],
            'team': player['team'],
            'steam_id': steamid,
            'steam_name': player['name'],
            'round_won': player['team'] == win_team,
        })

    created_at = datetime.datetime.utcfromtimestamp(
            state['provider']['timestamp'])

    season_index = bisect.bisect_left(season_starts, created_at) - 1
    season_id = season_ids[season_starts[season_index]]

    new_round = {
        'created_at': created_at,
        'season_id': season_id,
        'winner': team_members[win_team],
        'loser': team_members[lose_team],
    }

    return new_round, new_player_states


def parse_game_states(game_db, game_state_range):
    cursor = game_db.cursor()

    cursor.execute('''
    SELECT season_id, start_date
    FROM seasons
    ''')

    season_ids = {
        datetime.datetime.fromisoformat(start_date): season_id
        for season_id, start_date in enumerate_rows(cursor)
    }
    season_starts = list(season_ids.keys())

    game_states = get_game_states(game_db, game_state_range)

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


def insert_rounds(skill_db, teams_to_ids, rounds) -> (int, int):
    cursor = skill_db.cursor()
    fixed_rounds = [{
        'created_at': rnd['created_at'],
        'season_id': rnd['season_id'],
        'winner': teams_to_ids[rnd['winner']],
        'loser': teams_to_ids[rnd['loser']]
    } for rnd in rounds]

    for batch in [fixed_rounds[i:i + 100]
                  for i in range(0, len(fixed_rounds), 100)]:
        params = [value for rnd in batch
                  for value in (
                      rnd['season_id'],
                      rnd['created_at'],
                      rnd['winner'],
                      rnd['loser'])
                  ]
        placeholder = make_placeholder(4, len(batch))
        cursor.execute('''
        INSERT INTO rounds (season_id, created_at, winner, loser)
        VALUES {}
        '''.format(placeholder), params)

    max_round_id = cursor.lastrowid
    return max_round_id - len(rounds) + 1, max_round_id


def compute_rounds(skill_db, rounds, player_states):
    insert_players(skill_db, player_states)
    round_teams = {player_state['teammates'] for player_state in player_states}
    teams_to_ids = replace_teams(skill_db, round_teams)
    return insert_rounds(skill_db, teams_to_ids, rounds)


def compute_rounds_and_players(game_db, skill_db, game_state_range=None) \
        -> (int, (int, int)):
    rounds, player_states, max_game_state_id = \
        parse_game_states(game_db, game_state_range)
    new_rounds = compute_rounds(skill_db, rounds, player_states)
    return max_game_state_id, new_rounds


def rate_players(rounds: [dict], teams: [dict],
        current_ratings: {int: trueskill.Rating} = None) \
        -> {int: trueskill.Rating}:
    ratings = collections.defaultdict(
            trueskill.Rating,
            current_ratings.items() if current_ratings else ())
    for round in rounds:
        ranks = (
            {player_id: ratings[player_id]
             for player_id in teams[round['winner']]},
            {player_id: ratings[player_id]
             for player_id in teams[round['loser']]},
        )
        new_ratings = trueskill.rate(ranks)
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

    all_rounds = list(get_all_rounds(skill_db, new_rounds))
    teams = get_all_teams(skill_db)

    player_ratings = {
        player['player_id']: player['rating']
        for player in get_player_overall_skills(skill_db)
    }
    ratings = rate_players(all_rounds, teams, player_ratings)
    update_player_skills(skill_db, ratings)

    rounds_by_season = {
        season_id: list(rounds)
        for season_id, rounds in itertools.groupby(
                all_rounds, operator.itemgetter('season_id'))
    }
    season_ratings = get_ratings_by_season(
            skill_db, seasons=list(rounds_by_season.keys()))
    skills_by_season = rate_players_by_season(
            rounds_by_season, teams, season_ratings)
    replace_season_skills(skill_db, skills_by_season)


def recalculate():
    new_skill_db = SKILL_DB_NAME + '.new'
    with get_game_db() as game_db, \
            get_skill_db(new_skill_db) as skill_db:
        initialize_skill_db(skill_db)
        load_seasons(game_db, skill_db)
        max_game_state_id, new_rounds = \
            compute_rounds_and_players(game_db, skill_db)
        recalculate_ratings(skill_db, new_rounds)
        save_game_state_progress(skill_db, max_game_state_id)
        skill_db.commit()
    replace_skill_db(new_skill_db)
