import json
import bisect
import operator
import datetime
import itertools
import collections

import trueskill

from .db import enumerate_rows, get_skill_db, get_game_db, \
    initialize_skill_db, SKILL_DB_NAME, replace_skill_db
from .matchmaking import SKILL_MEAN, SKILL_STDEV, BETA, TAU, win_probability


def make_placeholder(columns, rows):
    row = '({})'.format(str.join(', ', ['?'] * columns))
    return str.join(', ', [row] * rows)


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
    rows = get_all_memberships(skill_db)
    memberships = {
        tuple(sorted(item[1] for item in group)): team
        for team, group in itertools.groupby(
            rows, operator.itemgetter(0))}
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


def parse_game_states(game_db):
    cursor = game_db.cursor()

    cursor.execute('''
    SELECT season_id, start_date
    FROM seasons
    ''')

    season_ids = {
        datetime.datetime.fromisoformat(start_date): season_id
        for season_id, start_date in enumerate_rows(cursor)
    }
    seasons = list(season_ids.keys())

    cursor.execute('''
    SELECT game_state_id, created_at, game_state
    FROM game_state
    ''')

    player_states = []
    rounds = []

    for (game_state_id, created_at, game_state_json) in enumerate_rows(cursor):
        state = json.loads(game_state_json)
        if not (state.get('round', {}).get('phase') == 'over' and
                state.get('previously', {}).get('round', {}).get('phase') == 'live'):
            continue
        if 'allplayers' not in state or 'win_team' not in state['round']:
            continue
        win_team = state['round']['win_team']
        team_steamids = [(player['team'], int(steamid))
                         for steamid, player in state['allplayers'].items()]
        team_steamids.sort()
        team_members = {
            team: tuple(sorted(item[1] for item in group))
            for team, group in itertools.groupby(
                team_steamids, operator.itemgetter(0))}
        if len(team_members) != 2:
            continue
        lose_team = next(iter(set(team_members.keys()) - {win_team}))

        for steamid, player in state['allplayers'].items():
            player_states.append({
                'teammates': team_members[player['team']],
                'round': state['map']['round'],
                'team': player['team'],
                'steam_id': steamid,
                'steam_name': player['name'],
                'round_won': player['team'] == win_team,
                # 'match_kills': state['match_stats']['kills'],
                # 'match_assists': state['match_stats']['assists'],
                # 'match_deaths': state['match_stats']['deaths'],
                # 'match_mvps': state['match_stats']['mvps'],
                # 'match_score': state['match_stats']['score'],
                # 'round_kills': state['state']['round_kills'],
                # 'round_totaldmg': state['state']['round_totaldmg'],
            })

        created_at = datetime.datetime.utcfromtimestamp(
                state['provider']['timestamp'])

        season_index = bisect.bisect_left(seasons, created_at) - 1
        season_id = season_ids[seasons[season_index]]

        rounds.append({
            'created_at': created_at,
            'season_id': season_id,
            'winner': team_members[win_team],
            'loser': team_members[lose_team],
        })

    return rounds, player_states


def get_all_rounds(skill_db):
    cursor = skill_db.cursor()
    cursor.execute('''
    SELECT season_id, winner, loser
    FROM rounds
    ''')
    for season_id, winner, loser in enumerate_rows(cursor):
        yield {
            'season_id': season_id,
            'winner': winner,
            'loser': loser,
        }


def get_all_memberships(skill_db):
    cursor = skill_db.cursor()
    cursor.execute('''
    SELECT team_id, player_id
    FROM team_membership
    ORDER BY team_id
    ''')
    return list(enumerate_rows(cursor))


def insert_rounds(skill_db, teams_to_ids, rounds):
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


def rate_players(rounds: [dict], teams: [dict]) -> dict:
    ratings = collections.defaultdict(trueskill.Rating)
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
    return ratings


def compute_rounds(game_db, skill_db):
    rounds, player_states = parse_game_states(game_db)

    insert_players(skill_db, player_states)

    round_teams = {player_state['teammates'] for player_state in player_states}
    teams_to_ids = replace_teams(skill_db, round_teams)
    insert_rounds(skill_db, teams_to_ids, rounds)


def update_global_ratings(connection, all_rounds, teams):
    cursor = connection.cursor()
    ratings = rate_players(all_rounds, teams)

    for player_id, rating in ratings.items():
        cursor.execute('''
        UPDATE players
        SET skill_mean = ?
          , skill_stdev = ?
        WHERE player_id = ?
        ''', (rating.mu, rating.sigma, player_id))


def insert_season_ratings(connection, rounds_by_season, teams):
    cursor = connection.cursor()

    skills = {}
    for season, rounds in rounds_by_season:
        ratings = rate_players(rounds, teams)
        for player_id, rating in ratings.items():
            skills[(player_id, season)] = rating

    params = [
        param
        for (player_id, season_id), skill in skills.items()
        for param in (player_id, season_id, skill.mu, skill.sigma)
    ]

    cursor.execute('''
    INSERT INTO skills (
      player_id
    , season_id
    , mean
    , stdev
    ) VALUES {}
    '''.format(make_placeholder(4, len(skills))), params)


def recalculate_teams(connection):
    memberships = get_all_memberships(connection)
    all_rounds = list(get_all_rounds(connection))

    teams = {team_id: frozenset(team[1] for team in teams)
             for team_id, teams
             in itertools.groupby(memberships, operator.itemgetter(0))}
    update_global_ratings(connection, all_rounds, teams)

    rounds_by_season = itertools.groupby(
            all_rounds, operator.itemgetter('season_id'))
    insert_season_ratings(connection, rounds_by_season, teams)


def run_evaluation(connection, beta, tau, sample):
    memberships = get_all_memberships(connection)
    rounds = list(get_all_rounds(connection))

    offset = int(len(rounds) * sample)
    training_sample = rounds[:offset]
    testing_sample = rounds[offset:]
    environment = trueskill.TrueSkill(SKILL_MEAN, SKILL_STDEV, beta, tau, 0.0)

    teams = {team_id: frozenset(team[1] for team in teams)
             for team_id, teams
             in itertools.groupby(memberships, operator.itemgetter(0))}
    ratings = rate_players(training_sample, teams)

    total = 1.0

    for round in testing_sample:
        winning_team = [ratings[player_id]
                        for player_id in teams[round['winner']]]
        losing_team = [ratings[player_id]
                       for player_id in teams[round['loser']]]
        total *= win_probability(environment, winning_team, losing_team)

    return total ** (1 / float(len(testing_sample)))


def evaluate_parameters(beta=BETA, tau=TAU, sample=0.5):
    with get_skill_db() as skill_db:
        print(run_evaluation(skill_db, beta, tau, sample))


def recalculate():
    new_skill_db = SKILL_DB_NAME + '.new'
    with get_game_db() as game_db, \
            get_skill_db(new_skill_db) as skill_db:
        initialize_skill_db(skill_db)
        load_seasons(game_db, skill_db)
        compute_rounds(game_db, skill_db)
        recalculate_teams(skill_db)
        skill_db.commit()
    replace_skill_db(new_skill_db)
