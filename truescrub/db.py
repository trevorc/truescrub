import os
import sqlite3
import operator
import itertools

import trueskill
from flask import g

from .matchmaking import SKILL_MEAN, SKILL_STDEV, \
    skill_group_name, match_quality

DATA_DIR = os.environ.get('TRUESCRUB_DATA_DIR', 'data')
GAME_DB_NAME = 'games.db'
SKILL_DB_NAME = 'skill.db'


def get_game_db():
    db_path = os.path.join(DATA_DIR, GAME_DB_NAME)
    return sqlite3.connect(db_path)


def get_skill_db(name: str = SKILL_DB_NAME):
    return sqlite3.connect(os.path.join(DATA_DIR, name))


def replace_skill_db(new_db_name: str):
    os.rename(os.path.join(DATA_DIR, new_db_name),
              os.path.join(DATA_DIR, SKILL_DB_NAME))


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


def execute_one(query, params=()):
    return next(execute(query, params))


def insert_game_state(state):
    with get_game_db() as game_db:
        cursor = game_db.cursor()
        cursor.execute('INSERT INTO game_state (game_state) VALUES (?)',
                       (state,))
        return cursor.lastrowid


def get_team_records(player_id):
    teams = get_player_teams(player_id)

    team_record_rows = execute('''
    SELECT m.team_id
         , IFNULL(rounds_won.num_rounds, 0)
         , IFNULL(rounds_lost.num_rounds, 0)
    FROM team_membership m
    LEFT JOIN ( SELECT r.winner AS team_id
                     , COUNT(*) AS num_rounds
                FROM rounds r
                GROUP BY r.winner
              ) rounds_won
    ON m.team_id = rounds_won.team_id
    LEFT JOIN ( SELECT r.loser AS team_id
                     , COUNT(*) AS num_rounds
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


def get_player_overall_skills(skill_db):
    cursor = skill_db.cursor()
    cursor.execute('''
    SELECT player_id
         , steam_name
         , skill_mean - 2 * skill_stdev AS mmr
         , skill_mean
         , skill_stdev
    FROM players
    ORDER BY skill_mean - 2 * skill_stdev DESC
    ''')

    for player_id, steam_name, mmr, skill_mean, skill_stdev in \
            enumerate_rows(cursor):
        yield {
            'player_id': int(player_id),
            'steam_name': steam_name,
            'mmr': int(mmr),
            'skill_group': skill_group_name(mmr),
            'rating': trueskill.Rating(skill_mean, skill_stdev),
        }


def get_all_players():
    return get_player_overall_skills(g.conn)


def get_player_rows_by_season(skill_db, seasons: [int] = None):
    cursor = skill_db.cursor()

    if seasons is None:
        where_clause = ''
        params = ()
    else:
        where_clause = 'WHERE skills.season_id IN {}'.format(
                make_placeholder(len(seasons), 1))
        params = seasons

    cursor.execute('''
    SELECT skills.season_id
         , players.player_id
         , players.steam_name
         , skills.mean - 2 * skills.stdev AS mmr
         , skills.mean
         , skills.stdev
    FROM players
    JOIN skills
    ON   players.player_id = skills.player_id
    {}
    ORDER BY skills.season_id
           , skills.mean - 2 * skills.stdev DESC
    '''.format(where_clause), params)

    return itertools.groupby(enumerate_rows(cursor), operator.itemgetter(0))


def get_players_by_seasons(skill_db):
    return {
        season_id: [
            {
                'player_id': int(player_id),
                'steam_name': steam_name,
                'mmr': int(mmr),
                'skill_group': skill_group_name(mmr),
                'rating': trueskill.Rating(skill_mean, skill_stdev),
            }
            for season_id_, player_id, steam_name, mmr, skill_mean, skill_stdev
            in season_players
        ]
        for season_id, season_players
        in get_player_rows_by_season(skill_db)
    }


def get_ratings_by_season(skill_db, seasons: [int] = None) \
        -> {int: {int: trueskill.Rating}}:
    return {
        season_id: {
            player_row[1]: trueskill.Rating(player_row[4], player_row[5])
            for player_row in season_players
        }
        for season_id, season_players in get_player_rows_by_season(skill_db)
    }


def get_season_players(season: int):
    return get_players_by_seasons(g.conn, [season])[season]


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
                , rounds.loser AS team_id
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


def get_all_teams_from_player_rounds(player_id: int) -> {int: [dict]}:
    team_rows = execute('''
    SELECT participants.team_id
         , participants.player_id
         , players.steam_name
    FROM   team_membership player_teams
    JOIN   ( SELECT player_id
                  , rounds.loser  AS team_id
             FROM rounds
             JOIN team_membership
             ON team_membership.team_id = rounds.winner
             UNION
             SELECT player_id
                  , winner AS team_id
             FROM rounds
             JOIN team_membership
             ON team_membership.team_id = rounds.loser
             UNION
             SELECT player_id
                  , rounds.winner AS team_id
             FROM rounds
             JOIN team_membership
             ON team_membership.team_id = rounds.winner
             UNION
             SELECT player_id
                  , loser AS team_id
             FROM rounds
             JOIN team_membership
             ON team_membership.team_id = rounds.loser
    ) matches
    ON     player_teams.player_id = matches.player_id
    JOIN   team_membership participants
    ON     participants.team_id = matches.team_id
    JOIN   players
    ON     players.player_id = participants.player_id
    WHERE player_teams.player_id = ?
    GROUP BY participants.team_id, participants.player_id
    ORDER BY participants.team_id, participants.player_id;
    ''', (player_id,))

    return {
        team_id: list(make_player(val) for val in group)
        for team_id, group in itertools.groupby(
            team_rows, operator.itemgetter(0))
    }


def get_player_profile(player_id: int):
    steam_name, mmr, rounds_won, rounds_lost = execute_one('''
    SELECT p.steam_name
         , p.skill_mean - 2 * skill_stdev AS mmr
         , IFNULL(rounds_won.num_rounds, 0)
         , IFNULL(rounds_lost.num_rounds, 0)
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
    teams = get_all_teams_from_player_rounds(player_id)

    round_rows = execute('''
    SELECT season_id, created_at, winner, loser
    FROM rounds
    JOIN team_membership m
    ON m.team_id = rounds.winner OR m.team_id = rounds.loser
    WHERE m.player_id = ?
    ORDER BY season_id DESC, created_at DESC
    ''', (player_id,))

    for season_id, created_at, winner, loser in round_rows:
        yield {
            'season_id': season_id,
            'created_at': created_at,
            'winner': teams[winner],
            'loser': teams[loser],
            'quality': 100 * match_quality(
                    player_skills, teams[winner], teams[loser]),
        }


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
        'rating': trueskill.Rating(row[3], row[4]),
    } for row in member_rows]


def get_opponent_records(team_id: int):
    opponent_rows = execute('''
    SELECT m.team_id
         , m.player_id
         , p.steam_name
         , p.skill_mean
         , p.skill_stdev
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
            'rating': trueskill.Rating(row[3], row[4]),
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

    for team_id, opponent_team_id, rounds_won, rounds_lost \
            in opponent_record_rows:
        yield {
            'opponent_team_id': opponent_team_id,
            'opponent_team': opponents[opponent_team_id],
            'rounds_won': rounds_won,
            'rounds_lost': rounds_lost,
        }


def get_all_rounds(skill_db, round_range: (int, int)):
    if round_range is not None:
        where_clause = 'WHERE round_id BETWEEN ? AND ?'
        params = round_range
    else:
        where_clause = ''
        params = []

    cursor = skill_db.cursor()
    cursor.execute('''
    SELECT season_id, winner, loser
    FROM rounds
    {}
    '''.format(where_clause), params)
    for season_id, winner, loser in enumerate_rows(cursor):
        yield {
            'season_id': season_id,
            'winner': winner,
            'loser': loser,
        }


def get_all_memberships(skill_db) -> [(int, int)]:
    cursor = skill_db.cursor()
    cursor.execute('''
    SELECT team_id, player_id
    FROM team_membership
    ORDER BY team_id
    ''')
    return list(enumerate_rows(cursor))


def get_all_teams(skill_db) -> {int: frozenset}:
    memberships = get_all_memberships(skill_db)
    return {
        team_id: frozenset(team[1] for team in teams)
        for team_id, teams
        in itertools.groupby(memberships, operator.itemgetter(0))
    }


def get_game_states(game_db, game_state_range):
    cursor = game_db.cursor()

    if game_state_range is None:
        where_clause = ''
        params = ()
    else:
        where_clause = 'WHERE game_state_id BETWEEN ? AND ?'
        params = game_state_range

    cursor.execute('''
    SELECT game_state_id, created_at, game_state
    FROM game_state
    {}
    '''.format(where_clause), params)
    return enumerate_rows(cursor)


def get_game_state_progress(skill_db) -> int:
    cursor = skill_db.cursor()
    cursor.execute('''
    SELECT last_processed_game_state
    FROM game_state_progress
    ''')
    row = cursor.fetchone()
    return 0 if row is None else row[0]


def save_game_state_progress(skill_db, max_game_state_id):
    cursor = skill_db.cursor()
    cursor.execute('''
    REPLACE INTO game_state_progress (
      game_state_progress_id
    , updated_at
    , last_processed_game_state
    ) VALUES (1, CURRENT_TIMESTAMP, ?)
    ''', [max_game_state_id])


def update_player_skills(skill_db, ratings: {int: trueskill.Rating}):
    cursor = skill_db.cursor()
    for player_id, rating in ratings.items():
        cursor.execute('''
        UPDATE players
        SET skill_mean = ?
          , skill_stdev = ?
        WHERE player_id = ?
        ''', (rating.mu, rating.sigma, player_id))


def replace_season_skills(
        skill_db, season_ratings: {(int, int): trueskill.Rating}):
    cursor = skill_db.cursor()
    params = [
        param
        for (player_id, season_id), skill in season_ratings.items()
        for param in (player_id, season_id, skill.mu, skill.sigma)
    ]

    cursor.execute('''
    REPLACE INTO skills (
      player_id
    , season_id
    , mean
    , stdev
    ) VALUES {}
    '''.format(make_placeholder(4, len(season_ratings))), params)


def initialize_game_db(game_db):
    cursor = game_db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS game_state(
      game_state_id  INTEGER PRIMARY KEY
    , created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
    , game_state     TEXT
    );
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seasons(
      season_id  INTEGER PRIMARY KEY
    , start_date DATETIME NOT NULL
    )''')
    cursor.execute('''
    REPLACE INTO seasons (season_id, start_date)
    VALUES (1, '2019-01-01')
    ''')


def initialize_skill_db(skill_db):
    cursor = skill_db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seasons(
      season_id  INTEGER PRIMARY KEY
    , start_date DATETIME NOT NULL
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players(
      player_id    INTEGER PRIMARY KEY
    , steam_name   TEXT    NOT NULL
    , skill_mean   DOUBLE  NOT NULL DEFAULT {skill_mean}
    , skill_stdev  DOUBLE  NOT NULL DEFAULT {skill_stdev}
    );
    '''.format(skill_mean=SKILL_MEAN, skill_stdev=SKILL_STDEV))

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS skills(
      player_id   INTEGER NOT NULL
    , season_id   INTEGER NOT NULL
    , mean        DOUBLE  NOT NULL
    , stdev       DOUBLE  NOT NULL
    , PRIMARY KEY (player_id, season_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (season_id) REFERENCES seasons (season_id)
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
    , season_id   INTEGER NOT NULL
    , created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    , winner      INTEGER NOT NULL
    , loser       INTEGER NOT NULL
    , FOREIGN KEY (season_id) REFERENCES seasons (season_id)
    , FOREIGN KEY (winner) REFERENCES teams (team_id)
    , FOREIGN KEY (loser) REFERENCES teams (team_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS game_state_progress(
      game_state_progress_id    INTEGER PRIMARY KEY
    , updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP
    , last_processed_game_state INTEGER NOT NULL
    );
    ''')


def initialize_dbs():
    if not os.path.exists(DATA_DIR):
        os.mkdir(DATA_DIR)
    with get_skill_db() as skill_db, get_game_db() as game_db:
        initialize_skill_db(skill_db)
        initialize_game_db(game_db)
        skill_db.commit()
        game_db.commit()


def get_seasons() -> [int]:
    [season_count] = execute_one('SELECT COUNT(*) FROM seasons')
    return list(range(1, season_count + 1))


def make_placeholder(columns, rows):
    row = '({})'.format(str.join(', ', ['?'] * columns))
    return str.join(', ', [row] * rows)