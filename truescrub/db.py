import os
import sqlite3
import operator
import itertools

from flask import g

from .util import SKILL_MEAN, SKILL_STDEV, skill_group_name, round_quality


DATABASE = os.environ.get('TRUESCRUB_DB', 'skill.db')


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


def insert_game_state(state):
    cursor = g.conn.cursor()
    cursor.execute('INSERT INTO game_state (game_state) VALUES (?)', (state,))


def get_team_records(player_id):
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

    for team_id, rounds_won, rounds_lost in team_record_rows:
        yield {
            'team_id': team_id,
            'team': teams[team_id],
            'rounds_won': rounds_won,
            'rounds_lost': rounds_lost,
        }


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

    for player_id, steam_name, mmr, skill_mean, skill_stdev in player_rows:
        yield {
            'player_id': int(player_id),
            'steam_name': steam_name,
            'mmr': int(mmr),
            'skill_group': skill_group_name(mmr),
            'skill_mean': skill_mean,
            'skill_stdev': skill_stdev,
        }


def make_player(team_row):
    return {'player_id': team_row[1], 'steam_name': team_row[2]}


def get_player_teams(player_id: int):
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

    return {
        team_id: list(make_player(val) for val in group)
        for team_id, group in itertools.groupby(
            team_rows, operator.itemgetter(0))
    }


def get_player_profile(player_id: int):
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
    return {
        'player_id': player_id,
        'steam_name': steam_name,
        'mmr': mmr,
        'skill_group': skill_group_name(mmr),
        'rounds_won': rounds_won,
        'rounds_lost': rounds_lost,
    }


def get_player_rounds(player_skills, player_id):
    teams = get_player_teams(player_id)

    round_rows = execute('''
    SELECT created_at, winner, loser
    FROM rounds
    JOIN team_membership m
    ON m.team_id = rounds.winner OR m.team_id = rounds.loser
    WHERE m.player_id = ?
    ORDER BY created_at DESC
    ''', (player_id,))

    return [{
        'created_at': row[0],
        'winner': teams[row[1]],
        'loser': teams[row[2]],
        'quality': '%.2f' % (
            round_quality(player_skills, teams[row[1]], teams[row[2]])),
    } for row in round_rows]


def get_team_members(team_id: int):
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

    return [{
        'player_id': row[0],
        'steam_name': row[1],
        'skill_group': skill_group_name(row[2]),
    } for row in member_rows]


def get_opponent_records(team_id: int):
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

    return [{
        'opponent_team_id': row[1],
        'opponent_team': opponents[row[1]],
        'rounds_won': row[2],
        'rounds_lost': row[3],
    } for row in opponent_record_rows]


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


def initialize(connection):
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys = 1')
    create_tables(cursor)

