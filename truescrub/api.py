#!/usr/bin/env python3

import os
import json
import bisect
import datetime
import argparse
import operator
import itertools

import flask
import sqlite3
import werkzeug
import trueskill
from flask import g, request


DATABASE = os.environ.get('TRUESCRUB_DB', 'skill.db')
SKILL_GROUPS = [
    (float('-inf'), 'Silver I'),
    (200, 'Silver II'),
    (400, 'Silver III'),
    (600, 'Gold I'),
    (800, 'Gold II'),
    (1000, 'Gold III'),
    (1200, 'Platinum I'),
    (1400, 'Platinum II'),
    (1600, 'Platinum III'),
    (1800, 'Elite'),
    (2000, 'Elite Master'),
]
SKILL_MEAN = 1000
SKILL_STDEV = 200
BETA = SKILL_STDEV / 2.0
TAU = SKILL_STDEV / 100.0

trueskill.setup(mu=SKILL_MEAN, sigma=SKILL_STDEV, beta=BETA, tau=TAU)


def create_tables(cursor):
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players(
      player_id    INTEGER PRIMARY KEY
    , steam_name   TEXT    NOT NULL
    , skill_mean   DOUBLE  NOT NULL DEFAULT {skill_mean}
    , skill_stdev  DOUBLE  NOT NULL DEFAULT {skill_stdev}
    );
    '''.format(skill_mean=SKILL_MEAN, skill_stdev=SKILL_STDEV))

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ratings_1v1(
      rating_1v1 INTEGER  PRIMARY KEY
    , created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    , winner     INTEGER  NOT NULL
    , loser      INTEGER  NOT NULL
    , FOREIGN KEY (winner) REFERENCES players (player_id)
    , FOREIGN KEY (loser)  REFERENCES players (player_d)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teams(
      team_id    INTEGER PRIMARY KEY
    , created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_membership(
      player_id INTEGER NOT NULL
    , team_id   INTEGER NOT NULL
    , PRIMARY KEY (player_id, team_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (team_id) REFERENCES teams (team_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rounds(
      round_id    INTEGER PRIMARY KEY
    , created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    , winner      INTEGER NOT NULL
    , loser       INTEGER NOT NULL
    , FOREIGN KEY (winner) REFERENCES teams (team_id)
    , FOREIGN KEY (loser) REFERENCES teams (team_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS game_state(
      game_state_id  INTEGER PRIMARY KEY
    , created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
    , game_state     TEXT
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_state(
      player_state_id INTEGER PRIMARY KEY
    , game_state_id   INTEGER NOT NULL
    , round           INTEGER NOT NULL
    , steam_id        INTEGER NOT NULL
    , steam_name      TEXT NOT NULL
    , team            TEXT NOT NULL
    , won_round       BOOLEAN NOT NULL
    , match_kills     INTEGER NOT NULL
    , match_assists   INTEGER NOT NULL
    , match_deaths    INTEGER NOT NULL
    , match_mvps      INTEGER NOT NULL
    , match_score     INTEGER NOT NULL
    , round_kills     INTEGER NOT NULL
    , round_totaldmg  INTEGER NOT NULL
    , FOREIGN KEY (game_state_id) REFERENCES game_state (game_state_id)
    , UNIQUE (game_state_id, round, steam_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_contribution(
      contribution_id INTEGER PRIMARY KEY
    , player_state_id INTEGER NOT NULL
    , player_id       INTEGER NOT NULL
    , team_id         INTEGER NOT NULL
    , round           INTEGER NOT NULL
    , won_round       BOOLEAN NOT NULL
    , round_kills     INTEGER NOT NULL
    , round_assists   INTEGER NOT NULL
    , round_mvps      INTEGER NOT NULL
    , round_score     INTEGER NOT NULL
    , round_totaldmg  INTEGER NOT NULL
    , FOREIGN KEY (player_state_id) REFERENCES player_state (player_state_id)
    , FOREIGN KEY (team_id, player_id) REFERENCES team_membership (team_id, player_id)
    );
    ''')


app = flask.Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


def get_db():
    return sqlite3.connect(DATABASE)


def enumerate_rows(cursor):
    while True:
        row = cursor.fetchone()
        if row is None:
            return
        yield row


def execute(query, params=()):
    cursor = g.conn.cursor()
    cursor.execute(query, params)
    return enumerate_rows(cursor)


def execute_one(query, params):
    return next(execute(query, params))


@app.before_request
def db_connect():
    g.conn = sqlite3.connect(DATABASE)


@app.after_request
def db_commit(response):
    g.conn.commit()
    return response


@app.teardown_request
def db_close(exc):
    g.conn.close()


@app.route('/api/game_state', methods={'POST'})
def game_state():
    state = json.dumps(request.get_json(force=True))
    cursor = g.conn.cursor()
    cursor.execute('INSERT INTO game_state (game_state) VALUES (?)', (state,))
    return '<h1>OK</h1>\n'


def rank_name(mmr: float) -> str:
    group_ranks = [group[0] for group in SKILL_GROUPS]
    index = bisect.bisect(group_ranks, mmr)
    return SKILL_GROUPS[index - 1][1]


@app.route('/leaderboard.html', methods={'GET'})
def leaderboard():
    players = list(execute('''
    SELECT player_id, steam_name, skill_mean - 2 * skill_stdev AS mmr
    FROM players
    ORDER BY skill_mean - 2 * skill_stdev DESC
    '''))

    leaders = [{
        'player_id': player[0],
        'steam_name': player[1],
        'mmr': int(player[2]),
        'skill_group': rank_name(player[2]),
    } for player in players]

    return flask.render_template('leaderboard.html', leaderboard=leaders)


def initialize():
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute('PRAGMA foreign_keys = 1')
        create_tables(cursor)


def replace_teams(db, round_teams):
    cursor = db.cursor()
    cursor.execute('''
    SELECT team_id, player_id
    FROM team_membership
    ORDER BY team_id
    ''')

    rows = list(enumerate_rows(cursor))
    memberships = {tuple(sorted(item[1] for item in group)): team
                   for team, group in itertools.groupby(rows, operator.itemgetter(0))}
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


def insert_players(db, player_states):
    cursor = db.cursor()

    players = {}
    for state in player_states:
        players[int(state['steam_id'])] = state['steam_name']

    placeholder = str.join(',', ['(?, ?)'] * len(players))
    params = [value
              for player in players.items()
              for value in player]

    cursor.execute('''
    REPLACE INTO players (player_id, steam_name) 
    VALUES {}
    '''.format(placeholder), params)


def compute_rounds(db):
    cursor = db.cursor()

    cursor.execute('''
    SELECT game_state_id, created_at, game_state
    FROM game_state
    ''')

    player_states = []
    rounds = []

    for (game_state_id, created_at, game_state_json) in enumerate_rows(cursor):
        state = json.loads(game_state_json)
        if not (state.get('round', {}).get('phase') == 'over' and \
                state.get('previously', {}).get('round', {}).get('phase') == 'live'):
            continue
        win_team = state['round']['win_team']
        team_steamids = [(player['team'], int(steamid))
                         for steamid, player in state['allplayers'].items()]
        team_steamids.sort()
        team_members = {team: tuple(sorted(item[1] for item in group))
                        for team, group in itertools.groupby(team_steamids, operator.itemgetter(0))}
        if len(team_members) != 2:
            raise ValueError(team_members)
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

        rounds.append({
            'created_at': datetime.datetime.fromtimestamp(state['provider']['timestamp']),
            'winner': team_members[win_team],
            'loser': team_members[lose_team],
        })

    insert_players(db, player_states)

    round_teams = {player_state['teammates'] for player_state in player_states}
    teams_to_ids = replace_teams(db, round_teams)
    fixed_rounds = [dict(created_at=rnd['created_at'], winner=teams_to_ids[rnd['winner']],
                         loser=teams_to_ids[rnd['loser']])
                    for rnd in rounds]

    cursor = db.cursor()
    cursor.execute('DELETE FROM rounds')

    params = [value for rnd in fixed_rounds for value in (rnd['created_at'], rnd['winner'], rnd['loser'])]
    cursor.execute('INSERT INTO rounds (created_at, winner, loser) VALUES ' +
                   str.join(',', ['(?, ?, ?)'] * len(fixed_rounds)),
                   params)


def recalculate_1v1(db):
    pass


def recalculate_teams(db):
    cursor = db.cursor()

    cursor.execute('''
    SELECT team_id, player_id
    FROM team_membership 
    ORDER BY team_id
    ''')
    memberships = list(enumerate_rows(cursor))

    cursor.execute('''
    SELECT winner, loser
    FROM rounds
    ''')
    rounds = list(enumerate_rows(cursor))

    teams = {team_id: frozenset(team[1] for team in teams)
             for team_id, teams
             in itertools.groupby(memberships, operator.itemgetter(0))}
    ratings = {player_id: trueskill.Rating(SKILL_MEAN, SKILL_STDEV)
               for player_id in frozenset().union(*teams.values())}

    for winner, loser in rounds:
        ranks = (
            {player_id: ratings[player_id] for player_id in teams[winner]},
            {player_id: ratings[player_id] for player_id in teams[loser]},
        )
        new_ratings = trueskill.rate(ranks)
        for rating in new_ratings:
            ratings.update(rating)

    for player_id, rating in ratings.items():
        cursor.execute('''
        UPDATE players
        SET skill_mean = ?
          , skill_stdev = ?
        WHERE player_id = ?
        ''', (rating.mu, rating.sigma, player_id))

def recalculate():
    with get_db() as db:
        compute_rounds(db)
        recalculate_1v1(db)
        recalculate_teams(db)
        db.commit()


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-a', '--addr', metavar='HOST', default='0.0.0.0',
                        help='Bind to this address.')
arg_parser.add_argument('-p', '--port', metavar='PORT', type=int,
                        default=9000, help='Listen on this TCP port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-r', '--use-reloader', action='store_true',
                        help='Use code reloader.')


def main():
    args = arg_parser.parse_args()
    if args.recalculate:
        return recalculate()
    app.wsgi_app = werkzeug.SharedDataMiddleware(app.wsgi_app, {
        '/': (__name__, 'htdocs')
    })
    app.run(args.addr, args.port, app, use_reloader=args.use_reloader)

initialize()
if __name__ == '__main__':
    main()
elif __name__.startswith('_mod_wsgi_'):
    application = app
