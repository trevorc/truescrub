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
    (float('-inf'), 'Scrub'),
    (0, 'Paper I'),
    (150, 'Paper II'),
    (300, 'Paper III'),
    (450, 'Paper IV'),
    (600, 'Plastic I'),
    (750, 'Plastic II'),
    (900, 'Plastic III'),
    (1050, 'Plastic IV'),
    (1200, 'Wood I'),
    (1350, 'Wood II'),
    (1500, 'Wood III'),
    (1650, 'Wood IV'),
    (1800, 'Bronze'),
    (1950, 'Bronze Master'),
    (2100, 'Pistols Only'),
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


def skill_group_name(mmr: float) -> str:
    group_ranks = [group[0] for group in SKILL_GROUPS]
    index = bisect.bisect(group_ranks, mmr)
    return SKILL_GROUPS[index - 1][1]


@app.route('/leaderboard', methods={'GET'})
def leaderboard():
    players = get_all_players()
    return flask.render_template('leaderboard.html', leaderboard=players)


def get_all_players():
    player_rows = execute('''
    SELECT player_id
         , steam_name
         , skill_mean - 2 * skill_stdev AS mmr
         , skill_mean
         , skill_stdev
    FROM players
    ORDER BY skill_mean - 2 * skill_stdev DESC
    ''')

    return [{
        'player_id': int(player[0]),
        'steam_name': player[1],
        'mmr': int(player[2]),
        'skill_group': skill_group_name(player[2]),
        'skill_mean': player[3],
        'skill_stdev': player[4],
    } for player in player_rows]


def make_player(team_row):
    return {'player_id': team_row[1], 'steam_name': team_row[2]}


def get_player_teams(player_id):
    team_rows = execute('''
    SELECT participants.team_id
         , players.player_id
         , players.steam_name
    FROM ( SELECT winners.player_id
                , rounds.winner AS team_id
           FROM   rounds
           JOIN   team_membership winners
           ON     rounds.winner = winners.team_id
           UNION
           SELECT losers.player_id
                , rounds.winner AS team_id
           FROM   rounds
           JOIN   team_membership losers
           ON     rounds.loser = losers.team_id
         ) m
    JOIN team_membership participants
    ON   participants.team_id = m.team_id
    JOIN players
    ON   players.player_id = participants.player_id
    WHERE m.player_id = ?
    ORDER BY participants.team_id
    ''', (player_id,))

    return {team_id: list(make_player(val) for val in group)
            for team_id, group in itertools.groupby(team_rows, operator.itemgetter(0))}


@app.route('/profiles/<player_id>', methods={'GET'})
def profile(player_id):
    [(steam_name, mmr, rounds_won, rounds_lost)] = execute('''
    SELECT p.steam_name
         , p.skill_mean - 2 * skill_stdev AS mmr
         , rounds_won.num_rounds
         , rounds_lost.num_rounds
    FROM players p
    LEFT JOIN ( SELECT m.player_id, COUNT(*) AS num_rounds
                FROM rounds r
                JOIN team_membership m ON r.winner = m.team_id
                GROUP BY m.player_id
              ) rounds_won
    ON p.player_id = rounds_won.player_id
    LEFT JOIN ( SELECT m.player_id, COUNT(*) AS num_rounds
                FROM rounds r
                JOIN team_membership m ON r.loser = m.team_id
                GROUP BY m.player_id
              ) rounds_lost
    ON p.player_id = rounds_lost.player_id
    WHERE p.player_id = ?
    ''', (player_id,))

    skill_group = skill_group_name(mmr)

    teams = get_player_teams(player_id)

    team_record_rows = execute('''
    SELECT m.team_id
         , rounds_won.num_rounds
         , rounds_lost.num_rounds
    FROM team_membership m
    LEFT JOIN ( SELECT r.winner AS team_id, COUNT(*) AS num_rounds
                FROM rounds r
                GROUP BY r.winner
              ) rounds_won
    ON m.team_id = rounds_won.team_id
    LEFT JOIN ( SELECT r.loser AS team_id, COUNT(*) AS num_rounds
                FROM rounds r
                GROUP BY r.loser
              ) rounds_lost
    ON m.team_id = rounds_lost.team_id
    WHERE m.player_id = ?
    ''', (player_id,))

    team_records = [{
        'team_id': row[0],
        'team': teams[row[0]],
        'rounds_won': row[1],
        'rounds_lost': row[2],
    } for row in team_record_rows]

    return flask.render_template(
        'profile.html',
        player_id=player_id, steam_name=steam_name,
        skill_group=skill_group,
        rounds_won=rounds_won, rounds_lost=rounds_lost,
        team_records=team_records)


def round_quality(player_skills, team1, team2):
    teams = (
        [player_skills[player['player_id']] for player in team1],
        [player_skills[player['player_id']] for player in team2],
    )
    return trueskill.quality(teams)


def suggest_teams(player_skills):
    players = frozenset(player_skills.keys())
    for r in range(1, len(players) // 2):
        for team1 in itertools.combinations(players, r):
            team2 = players - set(team1)
            quality = trueskill.quality((
                [player_skills[player_id] for player_id in team1],
                [player_skills[player_id] for player_id in team2]
            ))
            yield team1, team2, quality


@app.route('/matchmaking', methods={'GET'})
def matchmaking():
    players = get_all_players()
    player_skills = {player['player_id']: trueskill.Rating(player['skill_mean'], player['skill_stdev'])
                     for player in players}
    player_names = {player['player_id']: player['steam_name'] for player in players}

    teams = [{
        'team1': [player_names[player_id] for player_id in result[0]],
        'team2': [player_names[player_id] for player_id in result[1]],
        'quality': result[2],
    } for result in suggest_teams(player_skills)]

    teams.sort(key=operator.itemgetter('quality'), reverse=True)

    return '<pre>' + json.dumps(teams, indent=2) + '</pre>'


@app.route('/profiles/<player_id>/matches', methods={'GET'})
def matches(player_id):
    teams = get_player_teams(player_id)

    (steam_name,) = execute_one('''
    SELECT steam_name
    FROM players
    WHERE player_id = ?
    ''', (player_id,))

    player_skill_rows = execute('''
    SELECT player_id
         , skill_mean
         , skill_stdev
    FROM players
    ''')
    player_skills = {int(row[0]): trueskill.Rating(row[1], row[2])
                     for row in player_skill_rows}

    round_rows = execute('''
    SELECT created_at, winner, loser
    FROM rounds
    JOIN team_membership m
    ON m.team_id = rounds.winner OR m.team_id = rounds.loser
    WHERE m.player_id = ?
    ORDER BY created_at DESC
    ''', (player_id,))

    rounds = [{
        'created_at': row[0],
        'winner': teams[row[1]],
        'loser': teams[row[2]],
        'quality': '%.2f' % (
            round_quality(player_skills, teams[row[1]], teams[row[2]])),
    } for row in round_rows]

    return flask.render_template('matches.html', steam_name=steam_name, rounds=rounds)


@app.route('/teams/<team_id>', methods={'GET'})
def team_details(team_id):
    member_rows = execute('''
    SELECT players.player_id
         , steam_name
         , skill_mean - 2 * skill_stdev AS mmr
         , skill_mean
         , skill_stdev
    FROM players
    JOIN team_membership m
    ON   players.player_id = m.player_id
    WHERE m.team_id = ?
    ''', (team_id,))

    members = [{
        'player_id': row[0],
        'steam_name': row[1],
        'skill_group': skill_group_name(row[2]),
    } for row in member_rows]

    member_names = str.join(', ', [member['steam_name'] for member in members])

    opponent_rows = execute('''
    SELECT m.team_id
         , m.player_id
         , p.steam_name
    FROM team_membership m
    JOIN ( SELECT winner AS team_id
                , loser AS opponent
           FROM   rounds
           UNION
           SELECT loser AS team_id
                , winner AS opponent
           FROM   rounds
         ) matches
    ON   m.team_id = matches.opponent
    JOIN players p
    ON   m.player_id = p.player_id
    WHERE matches.team_id = ?
    ORDER BY m.team_id
    ''', (team_id,))

    opponents = {
        int(team_id): [{
            'player_id': row[1],
            'steam_name': row[2],
        } for row in group]
        for team_id, group in itertools.groupby(
                opponent_rows, operator.itemgetter(0))
    }

    opponent_record_rows = execute('''
    SELECT t.team_id
         , opponent.team_id AS opponent_team_id
         , IFNULL(rounds_won.num_rounds, 0) AS rounds_won
         , IFNULL(rounds_lost.num_rounds, 0) AS rounds_lost
    FROM teams t
    CROSS JOIN teams opponent
    LEFT JOIN ( SELECT winner
                     , loser
                     , COUNT(*) AS num_rounds
                FROM rounds r
                GROUP BY winner, loser
              ) rounds_won
    ON t.team_id = rounds_won.winner
    AND opponent.team_id = rounds_won.loser
    LEFT JOIN ( SELECT winner
                     , loser
                     , COUNT(*) AS num_rounds
                FROM rounds r
                GROUP BY winner, loser
              ) rounds_lost
    ON t.team_id = rounds_lost.loser
    AND opponent.team_id = rounds_lost.winner
    WHERE t.team_id = ?
    AND   (rounds_won.num_rounds IS NOT NULL
           OR rounds_lost.num_rounds IS NOT NULL)
    ''', (team_id,))

    opponent_records = [{
        'opponent_team_id': row[1],
        'opponent_team': opponents[row[1]],
        'rounds_won': row[2],
        'rounds_lost': row[3],
    } for row in opponent_record_rows]

    rounds_won = 0
    rounds_lost = 0
    for record in opponent_records:
        rounds_won += record['rounds_won']
        rounds_lost += record['rounds_lost']

    return flask.render_template(
        'team_details.html',
        member_names=member_names, members=members,
        rounds_won=rounds_won, rounds_lost=rounds_lost,
        opponent_records=opponent_records)


def initialize(db):
    cursor = db.cursor()
    cursor.execute('PRAGMA foreign_keys = 1')
    create_tables(cursor)


def drop_tables(db):
    cursor = db.cursor()
    cursor.execute('DROP TABLE IF EXISTS team_membership')
    cursor.execute('DROP TABLE IF EXISTS rounds')
    cursor.execute('DROP TABLE IF EXISTS players')
    cursor.execute('DROP TABLE IF EXISTS teams')


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

        created_at = datetime.datetime.fromtimestamp(state['provider']['timestamp'])

        rounds.append({
            'created_at': created_at,
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
    params = [value for rnd in fixed_rounds for value in (rnd['created_at'], rnd['winner'], rnd['loser'])]
    cursor.execute('INSERT INTO rounds (created_at, winner, loser) VALUES ' +
                   str.join(',', ['(?, ?, ?)'] * len(fixed_rounds)),
                   params)


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
        drop_tables(db)
        initialize(db)
        compute_rounds(db)
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
    with get_db() as db:
        initialize(db)
        db.commit()
    app.run(args.addr, args.port, app, use_reloader=args.use_reloader)

if __name__ == '__main__':
    main()
elif __name__.startswith('_mod_wsgi_'):
    application = app
