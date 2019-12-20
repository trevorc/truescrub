import os
import sqlite3
import logging
import datetime
import operator
import itertools

import trueskill

from .matchmaking import SKILL_MEAN, SKILL_STDEV, \
    skill_group_name, match_quality


DATA_DIR = os.environ.get('TRUESCRUB_DATA_DIR', 'data')
GAME_DB_NAME = 'games.db'
SKILL_DB_NAME = 'skill.db'

logger = logging.getLogger(__name__)


class Player(object):
    __slots__ = ('player_id', 'steam_name', 'rating', 'mmr', 'skill_group')

    def __init__(self, player_id, steam_name, skill_mean, skill_stdev):
        self.player_id = int(player_id)
        self.steam_name = steam_name
        self.rating = trueskill.Rating(skill_mean, skill_stdev)
        self.mmr = self.rating.mu - self.rating.sigma * 2
        self.skill_group = skill_group_name(self.mmr)


#################
### Utilities ###
#################

def enumerate_rows(cursor: sqlite3.Cursor):
    while True:
        row = cursor.fetchone()
        if row is None:
            return
        yield row


def execute(connection: sqlite3.Connection, query: str, params=()):
    cursor = connection.cursor()
    cursor.execute(query, params)
    return enumerate_rows(cursor)


def execute_one(connection: sqlite3.Connection, query: str, params=()):
    return next(execute(connection, query, params))


def make_placeholder(columns, rows):
    row = '({})'.format(str.join(', ', ['?'] * columns))
    return str.join(', ', [row] * rows)


##########################
### Game DB Operations ###
##########################

def get_game_db():
    db_path = os.path.join(DATA_DIR, GAME_DB_NAME)
    return sqlite3.connect(db_path)


def insert_game_state(game_db, state):
    cursor = game_db.cursor()
    cursor.execute('INSERT INTO game_state (game_state) VALUES (?)',
                   (state,))
    return cursor.lastrowid


def get_season_rows(game_db):
    return list(execute(game_db, '''
    SELECT *
    FROM seasons
    '''))


def get_seasons_by_start_date(game_db) -> {datetime.datetime: int}:
    season_rows = execute(game_db, '''
    SELECT season_id, start_date
    FROM seasons
    ''')

    return {
        datetime.datetime.fromisoformat(start_date): season_id
        for season_id, start_date in season_rows
    }


def get_game_states(game_db, game_state_range):
    if game_state_range is None:
        where_clause = ''
        params = ()
    else:
        where_clause = 'WHERE game_state_id BETWEEN ? AND ?'
        params = game_state_range

    return execute(game_db, '''
    SELECT game_state_id, created_at, game_state
    FROM game_state
    {}
    '''.format(where_clause), params)


def initialize_game_db(game_db):
    logger.debug('Initializing game_db')
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


###########################
### Skill DB Operations ###
###########################

def get_skill_db(name: str = SKILL_DB_NAME):
    return sqlite3.connect(os.path.join(DATA_DIR, name))


def replace_skill_db(new_db_name: str):
    os.rename(os.path.join(DATA_DIR, new_db_name),
              os.path.join(DATA_DIR, SKILL_DB_NAME))


def replace_seasons(skill_db, season_rows):
    placeholder = make_placeholder(2, len(season_rows))
    params = [
        param
        for season in season_rows
        for param in season
    ]

    skill_db_cursor = skill_db.cursor()
    skill_db_cursor.execute('''
    REPLACE INTO seasons (season_id, start_date)
    VALUES {}
    '''.format(placeholder), params)


def upsert_player_names(skill_db, players: {int: str}):
    cursor = skill_db.cursor()
    placeholder = make_placeholder(2, len(players))
    params = [value
              for player in players.items()
              for value in player]

    cursor.execute('''
    INSERT INTO players (player_id, steam_name)
    VALUES {}
    ON CONFLICT (player_id)
    DO UPDATE SET steam_name = excluded.steam_name
    '''.format(placeholder), params)


def insert_rounds(skill_db, rounds: [dict]) -> (int, int):
    if len(rounds) == 0:
        raise ValueError

    cursor = skill_db.cursor()
    for batch in [rounds[i:i + 128]
                  for i in range(0, len(rounds), 128)]:
        params = [
            value
            for rnd in batch
            for value in (
                rnd['season_id'],
                rnd['created_at'],
                rnd['winner'],
                rnd['loser'],
                rnd['mvp'],
            )
        ]
        placeholder = make_placeholder(5, len(batch))
        cursor.execute('''
        INSERT INTO rounds (season_id, created_at, winner, loser, mvp)
        VALUES {}
        '''.format(placeholder), params)

    max_round_id = cursor.lastrowid
    return max_round_id - len(rounds) + 1, max_round_id


def get_team_records(skill_db, player_id):
    teams = get_player_teams(skill_db, player_id)

    team_record_rows = execute(skill_db, '''
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

    return [
        {
            'team_id': team_id,
            'team': teams[team_id],
            'rounds_won': rounds_won,
            'rounds_lost': rounds_lost,
        }
        for team_id, rounds_won, rounds_lost in team_record_rows
    ]


def get_overall_player_rows(skill_db):
    return execute(skill_db, '''
    SELECT player_id
         , steam_name
         , skill_mean - 2 * skill_stdev AS mmr
         , skill_mean
         , skill_stdev
    FROM players
    ORDER BY mmr DESC
    ''')


def get_overall_ratings(skill_db) -> {int: trueskill.Rating}:
    return {
        int(player_row[0]): trueskill.Rating(player_row[3], player_row[4])
        for player_row in get_overall_player_rows(skill_db)
    }


def get_all_players(skill_db):
    return [
        {
            'player_id': int(player_id),
            'steam_name': steam_name,
            'mmr': int(mmr),
            'skill_group': skill_group_name(mmr),
            'rating': trueskill.Rating(skill_mean, skill_stdev),
        }
        for player_id, steam_name, mmr, skill_mean, skill_stdev
        in get_overall_player_rows(skill_db)
    ]


def get_player_rows_by_season(skill_db, seasons):
    if seasons is None:
        where_clause = ''
        params = ()
    else:
        where_clause = 'WHERE skills.season_id IN {}'.format(
                make_placeholder(len(seasons), 1))
        params = seasons

    player_rows = execute(skill_db, '''
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
           , mmr DESC
    '''.format(where_clause), params)

    return itertools.groupby(player_rows, operator.itemgetter(0))


def get_ratings_by_season(skill_db, seasons: [int]) \
        -> {int: {int: trueskill.Rating}}:
    return {
        season_id: {
            player_row[1]: trueskill.Rating(player_row[4], player_row[5])
            for player_row in season_players
        }
        for season_id, season_players
        in get_player_rows_by_season(skill_db, seasons)
    }


def get_season_players(skill_db, season: int):
    return [
        {
            'player_id': int(player_id),
            'steam_name': steam_name,
            'mmr': int(mmr),
            'skill_group': skill_group_name(mmr),
            'rating': trueskill.Rating(skill_mean, skill_stdev),
        }
        for season_id, player_rows
        in get_player_rows_by_season(skill_db, [season])
        for season_id_, player_id, steam_name, mmr, skill_mean, skill_stdev
        in player_rows
    ]


def make_player(team_row):
    return {'player_id': team_row[1], 'steam_name': team_row[2]}


def get_player_teams(skill_db, player_id: int):
    team_rows = execute(skill_db, '''
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


def get_all_teams_from_player_rounds(skill_db, player_id: int) -> {int: [dict]}:
    team_rows = execute(skill_db, '''
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


def get_player_profile(skill_db, player_id: int):
    steam_name, mmr, rounds_won, rounds_lost = execute_one(skill_db, '''
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


def get_player_rounds(skill_db, player_skills, player_id):
    teams = get_all_teams_from_player_rounds(skill_db, player_id)

    round_rows = execute(skill_db, '''
    SELECT season_id, created_at, winner, loser, mvp
    FROM rounds
    JOIN team_membership m
    ON m.team_id = rounds.winner OR m.team_id = rounds.loser
    WHERE m.player_id = ?
    ORDER BY season_id DESC, created_at DESC
    ''', (player_id,))

    for season_id, created_at, winner, loser, mvp in round_rows:
        yield {
            'season_id': season_id,
            'created_at': created_at,
            'winner': teams[winner],
            'loser': teams[loser],
            'mvp': mvp,
            'quality': 100 * match_quality(
                    player_skills, teams[winner], teams[loser]),
        }


def get_players_in_last_round(skill_db) -> {int}:
    player_ids = execute(skill_db, '''
    SELECT m.player_id
    FROM rounds r
    JOIN ( SELECT w.round_id
                , w.winner AS team_id
           FROM rounds w
           UNION ALL
           SELECT l.round_id
                , l.loser AS team_id
           FROM rounds l
         ) teams
    ON    r.round_id = teams.round_id
    JOIN  team_membership m
    ON    teams.team_id = m.team_id
    WHERE r.round_id =
          ( SELECT MAX(round_id)
            FROM rounds )
    ''')
    return {row[0] for row in player_ids}


def get_team_members(skill_db, team_id: int):
    member_rows = execute(skill_db, '''
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


def get_opponent_records(skill_db, team_id: int):
    opponent_rows = execute(skill_db, '''
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

    opponent_record_rows = execute(skill_db, '''
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

    return [
        {
            'opponent_team_id': opponent_team_id,
            'opponent_team': opponents[opponent_team_id],
            'rounds_won': rounds_won,
            'rounds_lost': rounds_lost,
        }
        for team_id, opponent_team_id, rounds_won, rounds_lost
        in opponent_record_rows
    ]


def get_all_rounds(skill_db, round_range: (int, int)):
    if round_range is not None:
        where_clause = 'WHERE round_id BETWEEN ? AND ?'
        params = round_range
    else:
        where_clause = ''
        params = []

    rounds = execute(skill_db, '''
    SELECT season_id, winner, loser, mvp
    FROM rounds
    {}
    '''.format(where_clause), params)
    return [
        {
            'season_id': season_id,
            'winner': winner,
            'loser': loser,
            'mvp': mvp,
        }
        for season_id, winner, loser, mvp in rounds
    ]


def get_all_teams(skill_db) -> {int: frozenset}:
    memberships = execute(skill_db, '''
    SELECT team_id, player_id
    FROM team_membership
    ORDER BY team_id
    ''')
    return {
        team_id: frozenset(team[1] for team in teams)
        for team_id, teams
        in itertools.groupby(memberships, operator.itemgetter(0))
    }


def get_game_state_progress(skill_db) -> int:
    try:
        return execute_one(skill_db, '''
        SELECT last_processed_game_state
        FROM game_state_progress
        ''')[0]
    except StopIteration:
        return 0


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


def get_season_range(skill_db) -> [int]:
    [season_count] = execute_one(skill_db, 'SELECT COUNT(*) FROM seasons')
    return list(range(1, season_count + 1))


def initialize_skill_db(skill_db):
    logger.debug('Initializing skill_db')
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
    , mvp         INTEGER
    , FOREIGN KEY (season_id) REFERENCES seasons (season_id)
    , FOREIGN KEY (winner) REFERENCES teams (team_id)
    , FOREIGN KEY (loser) REFERENCES teams (team_id)
    , FOREIGN KEY (mvp) REFERENCES players (player_id)
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
