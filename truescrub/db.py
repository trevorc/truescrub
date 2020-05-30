import os
import sqlite3
import logging
import datetime
import operator
import itertools
from typing import FrozenSet, Iterator, Optional

import trueskill

from .models import Player, RoundRow, SkillHistory, GameStateRow
from truescrub.models import SKILL_MEAN, SKILL_STDEV


DATA_DIR = os.environ.get('TRUESCRUB_DATA_DIR', 'data')
GAME_DB_NAME = 'games.db'
SKILL_DB_NAME = 'skill.db'

KILL_COEFF = 0.2778
DEATH_COEFF = 0.2559
DAMAGE_COEFF = 0.00651
KAS_COEFF = 0.00633
INTERCEPT = 0.18377
COEFFICIENTS = KILL_COEFF, DEATH_COEFF, DAMAGE_COEFF, KAS_COEFF, INTERCEPT

logger = logging.getLogger(__name__)


#################
### Utilities ###
#################

def enumerate_rows(cursor: sqlite3.Cursor):
    while True:
        row = cursor.fetchone()
        if row is None:
            return
        yield row


def execute(connection: sqlite3.Connection, query: str, params=()) \
        -> Iterator[tuple]:
    cursor = connection.cursor()
    cursor.execute(query, params)
    return enumerate_rows(cursor)


def execute_one(connection: sqlite3.Connection, query: str, params=()) \
        -> tuple:
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


def get_game_states(game_db, game_state_range) -> Iterator[GameStateRow]:
    if game_state_range is None:
        where_clause = ''
        params = ()
    else:
        where_clause = 'AND game_state_id BETWEEN ? AND ?'
        params = game_state_range

    return itertools.starmap(GameStateRow, execute(game_db, '''
    SELECT game_state_id
         , json_extract(game_state, '$.round.phase') AS round_phase
         , json_extract(game_state, '$.map.name') AS map_name
         , json_extract(game_state, '$.map.phase') AS map_phase
         , json_extract(game_state, '$.round.win_team') AS win_team
         , json_extract(game_state, '$.provider.timestamp') AS timestamp
         , json_extract(game_state, '$.allplayers') AS allplayers
         , json_extract(game_state, '$.previously.allplayers') AS previous_allplayers
    FROM game_state
    WHERE json_type(allplayers) = 'object'
      AND win_team IS NOT NULL
      AND json_extract(game_state, '$.round.phase') = 'over'
      AND json_extract(game_state, '$.previously.round.phase') = 'live'
      {}
    '''.format(where_clause), params))


def initialize_game_db(game_db):
    logger.debug('Initializing game_db')
    cursor = game_db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS game_state(
      game_state_id  INTEGER PRIMARY KEY
    , created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
    , game_state     TEXT NOT NULL
    );
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_game_state_round_phase_transition
    ON game_state (
      json_extract(game_state, '$.round.phase')
    , json_extract(game_state, '$.previously.round.phase')
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
    connection = sqlite3.connect(os.path.join(DATA_DIR, name))
    connection.cursor().execute('PRAGMA foreign_keys = ON')
    return connection


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


def get_map_names_to_ids(skill_db) -> {str: int}:
    return {
        map_name: map_id
        for map_name, map_id
        in execute(skill_db, '''
        SELECT map_name, map_id
        FROM maps
        ''')
    }


def replace_maps(skill_db, map_names: {str}):
    execute(skill_db, '''
    INSERT INTO maps (map_name)
    VALUES {}
    ON CONFLICT (map_name) DO NOTHING
    '''.format(make_placeholder(1, len(map_names))), list(map_names))


def make_batches(items: list, size: int):
    return (
        items[i:i + size]
        for i in range(0, len(items), size)
    )


def insert_rounds(skill_db, rounds: [dict]) -> (int, int):
    if len(rounds) == 0:
        raise ValueError

    map_names_to_id = get_map_names_to_ids(skill_db)

    cursor = skill_db.cursor()
    for batch in make_batches(rounds, 128):
        params = [
            value
            for rnd in batch
            for value in (
                rnd['season_id'],
                rnd['game_state_id'],
                rnd['created_at'],
                map_names_to_id[rnd['map_name']],
                rnd['winner'],
                rnd['loser'],
                rnd['mvp'],
            )
        ]
        placeholder = make_placeholder(7, len(batch))
        cursor.execute('''
        INSERT INTO rounds (
          season_id, game_state_id, created_at, map_id, winner, loser, mvp
        )
        VALUES {}
        '''.format(placeholder), params)

    max_round_id = cursor.lastrowid
    return max_round_id - len(rounds) + 1, max_round_id


def insert_round_stats(skill_db, round_stats_by_game_state_id: {int: dict}):
    min_game_state_id = min(round_stats_by_game_state_id.keys())
    max_game_state_id = max(round_stats_by_game_state_id.keys())

    round_mappings = execute(skill_db, '''
    SELECT game_state_id, round_id
    FROM rounds
    WHERE game_state_id BETWEEN ? AND ?
    ''', (min_game_state_id, max_game_state_id))

    game_state_id_to_round_id = {
        row[0]: row[1]
        for row in round_mappings
        if row[0] in round_stats_by_game_state_id
    }

    round_stats_rows = [
        (
            game_state_id_to_round_id[game_state_id],
            player_id,
            player_stats['kills'],
            player_stats['assists'],
            player_stats['damage'],
            player_stats['survived'],
        )
        for game_state_id, round_stats in round_stats_by_game_state_id.items()
        for player_id, player_stats in round_stats.items()

    ]

    cursor = skill_db.cursor()
    for batch in make_batches(round_stats_rows, 128):
        params = [
            value
            for row in batch
            for value in row
        ]
        placeholder = make_placeholder(6, len(batch))
        cursor.execute('''
        INSERT INTO round_stats (round_id, player_id, kills, assists, damage, survived)
        VALUES {}
        '''.format(placeholder), params)


def get_all_players(skill_db) -> [Player]:
    player_rows = execute(skill_db, '''
    SELECT player_id
         , steam_name
         , skill_mean
         , skill_stdev
         , impact_rating
    FROM players
    ''')

    return [
        Player(int(player_id), steam_name,
               skill_mean, skill_stdev, impact_rating)
        for player_id, steam_name, skill_mean, skill_stdev, impact_rating
        in player_rows
    ]


def get_overall_skills(skill_db) -> {int: trueskill.Rating}:
    return {
        player.player_id: player.skill
        for player in get_all_players(skill_db)
    }


def get_player_round_stat_averages(skill_db, player_id) -> dict:
    (
        average_mvps,
        average_kills,
        average_deaths,
        average_damage,
        average_kas,
    ) = execute_one(skill_db, '''
    SELECT AVG((r.mvp = rs.player_id) * 1.0)
         , AVG(rs.kills)
         , -AVG(rs.survived - 1.0)
         , AVG(rs.damage)
         , AVG((rs.kills OR rs.survived OR rs.assists) * 1.0)
    FROM round_stats rs
    JOIN rounds r
      ON rs.round_id = r.round_id
    WHERE rs.player_id = ?
    GROUP BY rs.player_id
    ''', (player_id,))

    return {
        'average_mvps': average_mvps,
        'average_kills': average_kills,
        'average_deaths': average_deaths,
        'average_damage': average_damage,
        'average_kas': average_kas,
    }


def get_player_round_stat_averages_by_season(
        skill_db, player_id) -> {int: dict}:
    # Call me when SQLite supports WITH ROLLUP
    stat_rows = execute(skill_db, '''
    SELECT r.season_id
         , AVG((r.mvp = rs.player_id) * 1.0)
         , AVG(rs.kills)
         , -AVG(rs.survived - 1.0)
         , AVG(rs.damage)
         , AVG((rs.kills OR rs.survived OR rs.assists) * 1.0)
    FROM round_stats rs
    JOIN rounds r
      ON rs.round_id = r.round_id
    WHERE rs.player_id = ?
    GROUP BY r.season_id
           , rs.player_id
    ORDER BY season_id
    ''', (player_id,))

    return {
        season_id: {
            'average_mvps': average_mvps,
            'average_kills': average_kills,
            'average_deaths': average_deaths,
            'average_damage': average_damage,
            'average_kas': average_kas,
        }
        for (
            season_id,
            average_mvps,
            average_kills,
            average_deaths,
            average_damage,
            average_kas,
        ) in stat_rows
    }


def get_overall_impact_ratings(skill_db) -> {int: float}:
    return dict(execute(skill_db, '''
    SELECT rc.player_id
         , {} * AVG(rc.kill_rating)
         + {} * AVG(rc.death_rating)
         + {} * AVG(rc.damage_rating)
         + {} * AVG(rc.kas_rating)
         + {}
         AS rating
     FROM rating_components rc
     GROUP BY rc.player_id
     '''.format(*COEFFICIENTS)))


def get_impact_ratings_by_season(skill_db) -> {int: {int: float}}:
    rating_rows = execute(skill_db, '''
    SELECT r.season_id
         , rc.player_id
         , {} * AVG(rc.kill_rating)
         + {} * AVG(rc.death_rating)
         + {} * AVG(rc.damage_rating)
         + {} * AVG(rc.kas_rating)
         + {}
         AS rating
     FROM rating_components rc
     JOIN rounds r ON r.round_id = rc.round_id
     GROUP BY r.season_id
            , rc.player_id
     ORDER BY r.season_id
     '''.format(*COEFFICIENTS))

    return {
        season_id: {
            row[1]: row[2]
            for row in season_ratings
        }
        for season_id, season_ratings
        in itertools.groupby(rating_rows, operator.itemgetter(0))
    }


def get_player_skills_by_season(skill_db, player_id: int) -> {int: Player}:
    skill_rows = execute(skill_db, '''
    SELECT skills.season_id
         , skills.player_id
         , players.steam_name
         , skills.mean
         , skills.stdev
         , skills.impact_rating
    FROM players
    JOIN skills
    ON players.player_id = skills.player_id
    WHERE players.player_id = ?
    ''', (player_id,))
    return {
        season_id: Player(int(player_id), steam_name,
                          skill_mean, skill_stdev, impact_rating)
        for (
            season_id,
            player_id,
            steam_name,
            skill_mean,
            skill_stdev,
            impact_rating,
        ) in skill_rows
    }


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
         , skills.mean
         , skills.stdev
         , skills.impact_rating
    FROM players
    JOIN skills
    ON   players.player_id = skills.player_id
    {}
    ORDER BY skills.season_id
    '''.format(where_clause), params)

    return itertools.groupby(player_rows, operator.itemgetter(0))


def get_skills_by_season(skill_db, seasons: [int]) \
        -> {int: {int: trueskill.Rating}}:
    return {
        season_id: {
            player_row[1]: trueskill.Rating(player_row[3], player_row[4])
            for player_row in season_players
        }
        for season_id, season_players
        in get_player_rows_by_season(skill_db, seasons)
    }


def get_season_players(skill_db, season: int):
    return [
        Player(int(player_id), steam_name,
               skill_mean, skill_stdev, impact_rating)
        for season_id, player_rows
        in get_player_rows_by_season(skill_db, [season])
        for season_id_, player_id, steam_name,
            skill_mean, skill_stdev, impact_rating
        in player_rows
    ]


def get_player_profile(skill_db, player_id: int):
    (
        steam_name,
        skill_mean,
        skill_stdev,
        impact_rating,
        rounds_won,
        rounds_lost,
    ) = execute_one(skill_db, '''
    SELECT p.steam_name
         , skill_mean
         , skill_stdev
         , impact_rating
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
    player = Player(player_id, steam_name,
                    skill_mean, skill_stdev, impact_rating)
    overall_record = {
        'rounds_won': rounds_won,
        'rounds_lost': rounds_lost,
    }
    return player, overall_record


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


def get_all_rounds(skill_db, round_range: (int, int)) -> [RoundRow]:
    if round_range is not None:
        where_clause = 'WHERE round_id BETWEEN ? AND ?'
        params = round_range
    else:
        where_clause = ''
        params = []

    rounds = execute(skill_db, '''
    SELECT round_id, created_at, season_id, winner, loser, mvp
    FROM rounds
    {}
    '''.format(where_clause), params)
    return [
        RoundRow(round_id, created_at, season_id, winner, loser, mvp)
        for round_id, created_at, season_id, winner, loser, mvp
        in rounds
    ]


def get_all_teams(skill_db) -> {int: FrozenSet[int]}:
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


def update_player_skills(skill_db, ratings: {int: trueskill.Rating},
                         impact_ratings: {int: float}):
    cursor = skill_db.cursor()
    for player_id, rating in ratings.items():
        cursor.execute('''
        UPDATE players
        SET skill_mean = ?
          , skill_stdev = ?
          , impact_rating = ?
        WHERE player_id = ?
        ''', (rating.mu, rating.sigma, impact_ratings[player_id], player_id))


def replace_overall_skill_history(skill_db, skill_history: [SkillHistory]):
    cursor = skill_db.cursor()
    for batch in make_batches(skill_history, 128):
        params = [
            value
            for history in batch
            for value in (
                history.player_id,
                history.round_id,
                history.skill.mu,
                history.skill.sigma,
            )
        ]
        placeholder = make_placeholder(4, len(batch))
        cursor.execute('''
        REPLACE INTO overall_skill_history (
            player_id
          , round_id
          , skill_mean
          , skill_stdev
        )
        VALUES {}
        '''.format(placeholder), params)


def replace_season_skills(
        skill_db, season_skills: {(int, int): trueskill.Rating},
        season_impact_ratings: {int: {int: float}}):
    cursor = skill_db.cursor()
    params = [
        param
        for (player_id, season_id), skill in season_skills.items()
        for param in (
            player_id,
            season_id,
            skill.mu,
            skill.sigma,
            season_impact_ratings[season_id][player_id],
        )
    ]

    cursor.execute('''
    REPLACE INTO skills (
      player_id
    , season_id
    , mean
    , stdev
    , impact_rating
    ) VALUES {}
    '''.format(make_placeholder(5, len(season_skills))), params)


def _skill_history_sort_key(history: SkillHistory):
    return history.player_id, history.round_id


def replace_season_skill_history(
        skill_db, history_by_season: {int: SkillHistory}):
    skill_history = list(itertools.chain(*history_by_season.values()))

    cursor = skill_db.cursor()
    for batch in make_batches(skill_history, 128):
        params = [
            value
            for history in batch
            for value in (
                history.player_id,
                history.round_id,
                history.skill.mu,
                history.skill.sigma,
            )
        ]
        placeholder = make_placeholder(4, len(batch))
        cursor.execute('''
        REPLACE INTO season_skill_history (
            player_id
          , round_id
          , skill_mean
          , skill_stdev
        )
        VALUES {}
        '''.format(placeholder), params)


def make_skill_history(player_id: int, skill_history):
    return {
        date: Player(player_id, '', skill_mean, skill_stdev, 0.0)
        for date, skill_mean, skill_stdev
        in skill_history
    }


def adapt_timezone(tz: datetime.timezone) -> str:
    utcoffset = tz.utcoffset(None)
    signum = '+' if utcoffset.days == 0 else '-'
    hours = utcoffset.seconds // 3600
    minutes = utcoffset.seconds % 3600 // 60
    return f'{signum}{hours:02}:{minutes:02}'


def get_impact_ratings_by_day(
        skill_db, player_id: int, tz: datetime.timezone,
        season_id: Optional[int] = None) \
        -> {str: float}:
    tz_offset = adapt_timezone(tz)

    format_args = list(COEFFICIENTS)
    params = [tz_offset, player_id]
    if season_id is not None:
        format_args.append('AND r.season_id = ?')
        params.append(season_id)
    else:
        format_args.append('')

    ratings = execute(skill_db, '''
    SELECT date(r.created_at, ?) as round_date
         , {} * AVG(rc.kill_rating)
         + {} * AVG(rc.death_rating)
         + {} * AVG(rc.damage_rating)
         + {} * AVG(rc.kas_rating)
         + {} AS rating
     FROM rating_components rc
     JOIN rounds r on rc.round_id = r.round_id
     WHERE rc.player_id = ?
     {}
     GROUP BY round_date
     '''.format(*format_args), params)
    return {date: rating for date, rating in ratings}


def get_overall_skill_history(skill_db, player_id: int, tz: datetime.timezone) \
        -> {str: Player}:
    tz_offset = adapt_timezone(tz)
    skill_history = execute(skill_db, '''
    SELECT DISTINCT date(created_at, ?) AS skill_date
         , LAST_VALUE(osh.skill_mean) OVER (
             PARTITION BY date(created_at, ?)
             ORDER BY osh.round_id
             RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
         ) AS skill_mean
         , LAST_VALUE(osh.skill_stdev) OVER (
             PARTITION BY date(created_at, ?)
             ORDER BY osh.round_id
             RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        ) AS skill_stdev
    FROM overall_skill_history osh
    JOIN rounds
    ON osh.round_id = rounds.round_id
    WHERE osh.player_id = ?
    ''', (tz_offset, tz_offset, tz_offset, player_id))
    return make_skill_history(player_id, skill_history)


def get_season_skill_history(skill_db, season: int, player_id: int,
                             tz: datetime.timezone) \
        -> {str: Player}:
    tz_offset = adapt_timezone(tz)
    skill_history = execute(skill_db, '''
    SELECT DISTINCT date(created_at, ?) AS skill_date
         , LAST_VALUE(ssh.skill_mean) OVER (
             PARTITION BY date(created_at, ?)
             ORDER BY ssh.round_id
             RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
         ) AS skill_mean
         , LAST_VALUE(ssh.skill_stdev) OVER (
             PARTITION BY date(created_at, ?)
             ORDER BY ssh.round_id
             RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        ) AS skill_stdev
    FROM season_skill_history ssh
    JOIN rounds
    ON ssh.round_id = rounds.round_id
    AND season_id = ?
    WHERE ssh.player_id = ?
    ''', (tz_offset, tz_offset, tz_offset, season, player_id))
    return make_skill_history(player_id, skill_history)


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
      player_id     INTEGER PRIMARY KEY
    , steam_name    TEXT    NOT NULL
    , skill_mean    DOUBLE  NOT NULL DEFAULT {skill_mean}
    , skill_stdev   DOUBLE  NOT NULL DEFAULT {skill_stdev}
    , impact_rating DOUBLE
    );
    '''.format(skill_mean=SKILL_MEAN, skill_stdev=SKILL_STDEV))

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS skills(
      player_id     INTEGER NOT NULL
    , season_id     INTEGER NOT NULL
    , mean          DOUBLE  NOT NULL
    , stdev         DOUBLE  NOT NULL
    , impact_rating DOUBLE  NOT NULL
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
    CREATE TABLE IF NOT EXISTS maps(
      map_id     INTEGER PRIMARY KEY
    , map_name   TEXT NOT NULL UNIQUE
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rounds(
      round_id      INTEGER PRIMARY KEY
    , season_id     INTEGER NOT NULL
    , game_state_id INTEGER NOT NULL
    , created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    , map_id        INTEGER NOT NULL
    , winner        INTEGER NOT NULL
    , loser         INTEGER NOT NULL
    , mvp           INTEGER
    , FOREIGN KEY (season_id) REFERENCES seasons (season_id)
    , FOREIGN KEY (map_id) REFERENCES maps (map_id)
    , FOREIGN KEY (winner) REFERENCES teams (team_id)
    , FOREIGN KEY (loser) REFERENCES teams (team_id)
    , FOREIGN KEY (mvp) REFERENCES players (player_id)
    );
    ''')

    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_rounds_winner ON rounds (winner);
    ''')

    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_rounds_loser ON rounds (loser);
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_weapons(
      player_id        INTEGER NOT NULL
    , round_id         INTEGER NOT NULL
    , primary_weapon   TEXT
    , secondary_weapon TEXT
    , taser            BOOLEAN NOT NULL
    , flashbang        BOOLEAN NOT NULL
    , smokegrenade     BOOLEAN NOT NULL
    , hegrenade        BOOLEAN NOT NULL
    , decoy            BOOLEAN NOT NULL
    , molotov          BOOLEAN NOT NULL
    , PRIMARY KEY (player_id, round_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (round_id) REFERENCES rounds (round_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_roles(
      player_id INTEGER NOT NULL
    , role      TEXT NOT NULL
    , PRIMARY KEY (player_id, role)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS overall_skill_history(
      player_id   INTEGER NOT NULL
    , round_id    INTEGER NOT NULL
    , skill_mean  DOUBLE NOT NULL
    , skill_stdev DOUBLE NOT NULL
    , PRIMARY KEY (player_id, round_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (round_id) REFERENCES rounds (round_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS season_skill_history(
      player_id   INTEGER NOT NULL
    , round_id    INTEGER NOT NULL
    , skill_mean  DOUBLE NOT NULL
    , skill_stdev DOUBLE NOT NULL
    , PRIMARY KEY (player_id, round_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (round_id) REFERENCES rounds (round_id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS round_stats(
      round_id   INTEGER NOT NULL
    , player_id  INTEGER NOT NULL
    , kills      INTEGER NOT NULL
    , assists    INTEGER NOT NULL
    , damage     INTEGER NOT NULL
    , survived   BOOLEAN NOT NULL
    , PRIMARY KEY (round_id, player_id)
    , FOREIGN KEY (round_id) REFERENCES rounds (round_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    );
    ''')

    cursor.execute('''
    CREATE VIEW IF NOT EXISTS rating_components AS
    SELECT rs.round_id
         , rs.player_id
         , ((r.mvp = rs.player_id) * 1.0) AS mvp_rating
         , rs.kills AS kill_rating
         , (rs.survived - 1.0) AS death_rating
         , rs.damage AS damage_rating
         , ((rs.kills OR rs.survived OR rs.assists) * 1.0) AS kas_rating
         , rs.assists AS assists_rating
    FROM round_stats rs
    JOIN rounds r ON rs.round_id = r.round_id;
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
