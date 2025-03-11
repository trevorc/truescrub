import datetime
import itertools
import json
import logging
import operator
import os
import sqlite3
from typing import (
    Any,
    Dict,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    TypeVar,
    cast,
)

from trueskill import Rating

from truescrub.models import (
    SKILL_MEAN,
    SKILL_STDEV,
    GameStateRow,
    Player,
    RoundRow,
    SkillHistory,
)

# Type variables
T = TypeVar('T')

# Type definitions for database results
SqliteRow = Tuple[Any, ...]
DbConnection = sqlite3.Connection
DbCursor = sqlite3.Cursor

# Type definitions for structured data
class RoundStats(TypedDict):
    """Round statistics for a player."""
    average_mvps: float
    average_kills: float
    average_deaths: float
    average_damage: float
    average_kas: float

class PlayerRecord(TypedDict):
    """Player's overall win/loss record."""
    rounds_won: int
    rounds_lost: int

class PlayerStats(TypedDict):
    """Player's per-round statistics."""
    kills: int
    assists: int
    damage: int
    survived: bool

DATA_DIR = os.environ.get("TRUESCRUB_DATA_DIR", "data")
SQLITE_TIMEOUT = float(os.environ.get("SQLITE_TIMEOUT", "30"))
GAME_DB_NAME = "games.db"
SKILL_DB_NAME = "skill.db"

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


def enumerate_rows(cursor: DbCursor) -> Iterator[SqliteRow]:
    """
    Iterate over rows returned by a cursor.

    Args:
        cursor: A SQLite cursor with executed query

    Returns:
        Iterator over rows from the query result
    """
    while True:
        row = cursor.fetchone()
        if row is None:
            return
        yield row


def execute(
    connection: DbConnection, query: str, params: Any = ()
) -> Iterator[SqliteRow]:
    """
    Execute a SQL query and iterate over the results.

    Args:
        connection: SQLite database connection
        query: SQL query string to execute
        params: Parameters for the SQL query

    Returns:
        Iterator over rows from the query result
    """
    cursor = connection.cursor()
    cursor.execute(query, params)
    return enumerate_rows(cursor)


def execute_one(
    connection: DbConnection, query: str, params: Any = ()
) -> SqliteRow:
    """
    Execute a SQL query and return the first result row.

    Args:
        connection: SQLite database connection
        query: SQL query string to execute
        params: Parameters for the SQL query

    Returns:
        First row from the query result

    Raises:
        StopIteration: If the query returns no rows
    """
    return next(execute(connection, query, params))


def make_placeholder(columns: int, rows: int) -> str:
    """
    Create a SQL placeholder string for a multi-row insert.

    Args:
        columns: Number of columns in each row
        rows: Number of rows to insert

    Returns:
        SQL placeholder string like "(?,?,?),(?,?,?)" for multiple rows
    """
    row = "({})".format(", ".join(["?"] * columns))
    return ", ".join([row] * rows)


##########################
### Game DB Operations ###
##########################


def get_game_db() -> DbConnection:
    """
    Get a connection to the game database.

    Returns:
        SQLite connection to the game database
    """
    db_path = os.path.join(DATA_DIR, GAME_DB_NAME)
    return sqlite3.connect(db_path, timeout=SQLITE_TIMEOUT)


def insert_game_state(game_db: DbConnection, state: str) -> int:
    """
    Insert a new game state into the database.

    Args:
        game_db: Game database connection
        state: JSON string containing game state

    Returns:
        ID of the newly inserted game state
    """
    cursor = game_db.cursor()
    cursor.execute("INSERT INTO game_state (game_state) VALUES (?)", (state,))
    return cast(int, cursor.lastrowid)


def get_season_rows(game_db: DbConnection) -> List[SqliteRow]:
    """
    Get all season rows from the database.

    Args:
        game_db: Game database connection

    Returns:
        List of season rows
    """
    return list(
        execute(
            game_db,
            """
    SELECT *
    FROM seasons
    """,
        )
    )


def get_seasons_by_start_date(game_db: DbConnection) -> Dict[datetime.datetime, int]:
    """
    Get mapping of season start dates to season IDs.

    Args:
        game_db: Game database connection

    Returns:
        Dictionary mapping datetime objects to season IDs
    """
    season_rows = execute(
        game_db,
        """
    SELECT season_id, start_date
    FROM seasons
    """,
    )

    return {
        datetime.datetime.strptime(cast(str, start_date), "%Y-%m-%d"): cast(int, season_id)
        for season_id, start_date in season_rows
    }


def get_game_state_count(game_db: DbConnection) -> int:
    """
    Get the count of game states in the database.

    Args:
        game_db: Game database connection

    Returns:
        Count of game state rows
    """
    result = execute_one(
        game_db,
        """
    SELECT COUNT(*) FROM game_state
    """,
    )
    return int(result[0])


def get_raw_game_states(game_db: DbConnection) -> Iterator[Tuple[int, int, Dict[str, Any]]]:
    """
    Get raw game states from the database.

    Args:
        game_db: Game database connection

    Returns:
        Iterator of (game_state_id, created_at_timestamp, game_state_dict) tuples
    """
    for game_state_id, created_at, game_state in execute(
        game_db,
        """
    SELECT game_state_id
         , CAST(strftime('%s', created_at) AS INTEGER) AS created_at_unixtime
         , game_state
    FROM game_state
    """,
    ):
        yield (
            cast(int, game_state_id),
            cast(int, created_at),
            cast(Dict[str, Any], json.loads(cast(str, game_state)))
        )


def get_game_states(
    game_db: DbConnection,
    game_state_range: Optional[Tuple[int, int]]
) -> Iterator[GameStateRow]:
    """
    Get processed game state rows from the database.

    Args:
        game_db: Game database connection
        game_state_range: Optional tuple of (min_id, max_id) to filter by

    Returns:
        Iterator of GameStateRow objects
    """
    if game_state_range is None:
        where_clause = ""
        params: Tuple[Any, ...] = ()
    else:
        where_clause = "AND game_state_id BETWEEN ? AND ?"
        params = game_state_range

    return itertools.starmap(
        GameStateRow,
        execute(
            game_db,
            f"""
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
      {where_clause}
    """,
            params,
        ),
    )


def initialize_game_db(game_db: DbConnection) -> None:
    """
    Initialize the game database schema if it doesn't exist.

    This creates the necessary tables and indices for storing game state data.

    Args:
        game_db: Game database connection
    """
    logger.debug("Initializing game_db")
    cursor = game_db.cursor()
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS game_state(
      game_state_id  INTEGER PRIMARY KEY
    , created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
    , game_state     TEXT NOT NULL
    );
    """
    )
    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS ix_game_state_round_phase_transition
    ON game_state (
      json_extract(game_state, '$.round.phase')
    , json_extract(game_state, '$.previously.round.phase')
    );
    """
    )
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS seasons(
      season_id  INTEGER PRIMARY KEY
    , start_date DATETIME NOT NULL
    )"""
    )
    cursor.execute(
        """
    REPLACE INTO seasons (season_id, start_date)
    VALUES (1, '2019-01-01')
    """
    )


###########################
### Skill DB Operations ###
###########################


def get_skill_db(name: str = SKILL_DB_NAME) -> DbConnection:
    """
    Get a connection to the skill database.

    Args:
        name: Name of the database file (defaults to SKILL_DB_NAME)

    Returns:
        SQLite connection to the skill database
    """
    connection = sqlite3.connect(os.path.join(DATA_DIR, name), timeout=SQLITE_TIMEOUT)
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA defer_foreign_keys = ON")
    return connection


def replace_skill_db(new_db_name: str) -> None:
    """
    Replace the current skill database with a new one.

    Args:
        new_db_name: Name of the new database file to use
    """
    os.rename(
        os.path.join(DATA_DIR, new_db_name), os.path.join(DATA_DIR, SKILL_DB_NAME)
    )


def replace_seasons(skill_db: DbConnection, season_rows: List[Tuple[int, str]]) -> None:
    """
    Replace all season records in the database.

    Args:
        skill_db: Skill database connection
        season_rows: List of (season_id, start_date) tuples
    """
    placeholder = make_placeholder(2, len(season_rows))
    params = [param for season in season_rows for param in season]

    skill_db_cursor = skill_db.cursor()
    skill_db_cursor.execute(
        f"""
    REPLACE INTO seasons (season_id, start_date)
    VALUES {placeholder}
    """,
        params,
    )


def upsert_player_names(skill_db: DbConnection, players: Dict[int, str]) -> None:
    """
    Insert or update player names in the database.

    Args:
        skill_db: Skill database connection
        players: Dictionary mapping player IDs to steam names
    """
    cursor = skill_db.cursor()
    placeholder = make_placeholder(2, len(players))
    params = [value for player in players.items() for value in player]

    cursor.execute(
        f"""
    INSERT INTO players (player_id, steam_name)
    VALUES {placeholder}
    ON CONFLICT (player_id)
    DO UPDATE SET steam_name = excluded.steam_name
    """,
        params,
    )


def get_map_names_to_ids(skill_db: DbConnection) -> Dict[str, int]:
    """
    Get mapping of map names to their database IDs.

    Args:
        skill_db: Skill database connection

    Returns:
        Dictionary mapping map names to map IDs
    """
    return {
        cast(str, row[0]): cast(int, row[1])
        for row in execute(
            skill_db,
            """
        SELECT map_name, map_id
        FROM maps
        """,
        )
    }


def replace_maps(skill_db: DbConnection, map_names: Set[str]) -> None:
    """
    Insert new maps into the database, ignoring duplicates.

    Args:
        skill_db: Skill database connection
        map_names: Set of map names to insert
    """
    execute(
        skill_db,
        f"""
    INSERT INTO maps (map_name)
    VALUES {make_placeholder(1, len(map_names))}
    ON CONFLICT (map_name) DO NOTHING
    """,
        list(map_names),
    )


def make_batches(items: List[T], size: int) -> Iterable[List[T]]:
    """
    Split a list into batches of a specified size.

    Args:
        items: List of items to batch
        size: Maximum size of each batch

    Returns:
        Iterator of sublists, each with at most 'size' items
    """
    return (items[i : i + size] for i in range(0, len(items), size))


class RoundData(TypedDict):
    """Round data for database insertion."""
    season_id: int
    game_state_id: int
    created_at: str
    map_name: str
    winner: int
    loser: int
    mvp: Optional[int]


def insert_rounds(skill_db: DbConnection, rounds: List[RoundData]) -> Tuple[int, int]:
    """
    Insert round data into the database.

    Args:
        skill_db: Skill database connection
        rounds: List of round data dictionaries

    Returns:
        Tuple of (min_round_id, max_round_id) for the inserted rounds

    Raises:
        ValueError: If rounds list is empty
    """
    if len(rounds) == 0:
        raise ValueError("Cannot insert empty rounds list")

    map_names_to_id = get_map_names_to_ids(skill_db)

    cursor = skill_db.cursor()
    for batch in make_batches(rounds, 128):
        params = [
            value
            for rnd in batch
            for value in (
                rnd["season_id"],
                rnd["game_state_id"],
                rnd["created_at"],
                map_names_to_id[rnd["map_name"]],
                rnd["winner"],
                rnd["loser"],
                rnd["mvp"],
            )
        ]
        placeholder = make_placeholder(7, len(batch))
        cursor.execute(
            f"""
        INSERT INTO rounds (
          season_id, game_state_id, created_at, map_id, winner, loser, mvp
        )
        VALUES {placeholder}
        """,
            params,
        )

    max_round_id = cast(int, cursor.lastrowid)
    return max_round_id - len(rounds) + 1, max_round_id


def insert_round_stats(
    skill_db: DbConnection,
    round_stats_by_game_state_id: Dict[int, Dict[int, PlayerStats]]
) -> None:
    """
    Insert round statistics for players.

    Args:
        skill_db: Skill database connection
        round_stats_by_game_state_id: Nested dictionary mapping game state IDs to
                                      player IDs to their statistics
    """
    if not round_stats_by_game_state_id:
        return  # Nothing to insert

    min_game_state_id = min(round_stats_by_game_state_id.keys())
    max_game_state_id = max(round_stats_by_game_state_id.keys())

    # Get mapping from game state IDs to round IDs
    round_mappings = execute(
        skill_db,
        """
    SELECT game_state_id, round_id
    FROM rounds
    WHERE game_state_id BETWEEN ? AND ?
    """,
        (min_game_state_id, max_game_state_id),
    )

    game_state_id_to_round_id = {
        cast(int, row[0]): cast(int, row[1])
        for row in round_mappings
        if cast(int, row[0]) in round_stats_by_game_state_id
    }

    # Create rows for batch insertion
    round_stats_rows = [
        (
            game_state_id_to_round_id[game_state_id],
            player_id,
            player_stats["kills"],
            player_stats["assists"],
            player_stats["damage"],
            player_stats["survived"],
        )
        for game_state_id, round_stats in round_stats_by_game_state_id.items()
        for player_id, player_stats in round_stats.items()
    ]

    # Insert in batches
    cursor = skill_db.cursor()
    for batch in make_batches(round_stats_rows, 128):
        params = [value for row in batch for value in row]
        placeholder = make_placeholder(6, len(batch))
        cursor.execute(
            f"""
        INSERT INTO round_stats (round_id, player_id, kills, assists, damage, survived)
        VALUES {placeholder}
        """,
            params,
        )


def get_all_players(skill_db: DbConnection) -> List[Player]:
    """
    Get all players from the database.

    Args:
        skill_db: Skill database connection

    Returns:
        List of Player objects with their current skill ratings
    """
    player_rows = execute(
        skill_db,
        """
    SELECT player_id
         , steam_name
         , skill_mean
         , skill_stdev
         , impact_rating
    FROM players
    """,
    )

    return [
        Player(
            int(player_id),
            str(steam_name),
            float(skill_mean),
            float(skill_stdev),
            0.0 if impact_rating is None else float(impact_rating)
        )
        for player_id, steam_name, skill_mean, skill_stdev, impact_rating in player_rows
    ]


def get_overall_skills(skill_db: DbConnection) -> Dict[int, Rating]:
    """
    Get all players' current skill ratings.

    Args:
        skill_db: Skill database connection

    Returns:
        Dictionary mapping player IDs to their TrueSkill Rating objects
    """
    return {player.player_id: player.skill for player in get_all_players(skill_db)}


def get_player_round_stat_averages(skill_db: DbConnection, player_id: int) -> RoundStats:
    """
    Get average round statistics for a player.

    Args:
        skill_db: Skill database connection
        player_id: ID of the player to get statistics for

    Returns:
        Dictionary with average statistics (MVPs, kills, deaths, damage, KAS)

    Raises:
        StopIteration: If the player has no round stats
    """
    row = execute_one(
        skill_db,
        """
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
    """,
        (player_id,),
    )

    average_mvps, average_kills, average_deaths, average_damage, average_kas = row

    return {
        "average_mvps": cast(float, average_mvps),
        "average_kills": cast(float, average_kills),
        "average_deaths": cast(float, average_deaths),
        "average_damage": cast(float, average_damage),
        "average_kas": cast(float, average_kas),
    }


def get_player_round_stat_averages_by_season(
    skill_db: DbConnection, player_id: int
) -> Dict[int, RoundStats]:
    """
    Get average round statistics for a player by season.

    Args:
        skill_db: Skill database connection
        player_id: ID of the player to get statistics for

    Returns:
        Dictionary mapping season IDs to round statistics dictionaries
    """
    # Call me when SQLite supports WITH ROLLUP
    stat_rows = execute(
        skill_db,
        """
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
    """,
        (player_id,),
    )

    return {
        cast(int, season_id): {
            "average_mvps": cast(float, average_mvps),
            "average_kills": cast(float, average_kills),
            "average_deaths": cast(float, average_deaths),
            "average_damage": cast(float, average_damage),
            "average_kas": cast(float, average_kas),
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


def get_overall_impact_ratings(skill_db: DbConnection) -> Dict[int, float]:
    """
    Get impact ratings for all players across all seasons.

    Args:
        skill_db: Skill database connection

    Returns:
        Dictionary mapping player IDs to their overall impact ratings
    """
    return {
        cast(int, row[0]): cast(float, row[1])
        for row in execute(
            skill_db,
            """
    SELECT rc.player_id
         , {} * AVG(rc.kill_rating)
         + {} * AVG(rc.death_rating)
         + {} * AVG(rc.damage_rating)
         + {} * AVG(rc.kas_rating)
         + {}
         AS rating
     FROM rating_components rc
     GROUP BY rc.player_id
     """.format(
                *COEFFICIENTS
            ),
        )
    }


def get_impact_ratings_by_season(skill_db: DbConnection) -> Dict[int, Dict[int, float]]:
    """
    Get impact ratings for all players by season.

    Args:
        skill_db: Skill database connection

    Returns:
        Dictionary mapping season IDs to player ID to impact rating dictionaries
    """
    rating_rows = execute(
        skill_db,
        """
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
     """.format(
            *COEFFICIENTS
        ),
    )

    return {
        cast(int, season_id): {
            cast(int, row[1]): cast(float, row[2]) for row in season_ratings
        }
        for season_id, season_ratings in itertools.groupby(
            rating_rows, operator.itemgetter(0)
        )
    }


def get_player_skills_by_season(
    skill_db: DbConnection, player_id: int
) -> Dict[int, Player]:
    """
    Get a player's skills by season.

    Args:
        skill_db: Skill database connection
        player_id: ID of the player to get skills for

    Returns:
        Dictionary mapping season IDs to Player objects with seasonal skills
    """
    skill_rows = execute(
        skill_db,
        """
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
    """,
        (player_id,),
    )
    return {
        cast(int, season_id): Player(
            int(cast(int, player_id_row)),
            cast(str, steam_name),
            cast(float, skill_mean),
            cast(float, skill_stdev),
            cast(float, impact_rating)
        )
        for (
            season_id,
            player_id_row,
            steam_name,
            skill_mean,
            skill_stdev,
            impact_rating,
        ) in skill_rows
    }


def get_player_rows_by_season(
    skill_db: DbConnection,
    seasons: Optional[List[int]]
) -> Iterator[Tuple[int, Iterator[SqliteRow]]]:
    """
    Get player rows from the database grouped by season.

    Args:
        skill_db: Skill database connection
        seasons: Optional list of season IDs to filter by

    Returns:
        Iterator of (season_id, player_rows) tuples
    """
    if seasons is None:
        where_clause = ""
        params: Tuple[Any, ...] = ()
    else:
        where_clause = f"WHERE skills.season_id IN {make_placeholder(len(seasons), 1)}"
        params = tuple(seasons)

    player_rows = execute(
        skill_db,
        f"""
    SELECT skills.season_id
         , players.player_id
         , players.steam_name
         , skills.mean
         , skills.stdev
         , skills.impact_rating
    FROM players
    JOIN skills
    ON   players.player_id = skills.player_id
    {where_clause}
    ORDER BY skills.season_id
    """,
        params,
    )

    return itertools.groupby(player_rows, operator.itemgetter(0))


def get_skills_by_season(
    skill_db: DbConnection,
    seasons: List[int]
) -> Dict[int, Dict[int, Rating]]:
    """
    Get all players' skills grouped by season.

    Args:
        skill_db: Skill database connection
        seasons: List of season IDs to include

    Returns:
        Dictionary mapping season IDs to player ID to Rating dictionaries
    """
    return {
        int(season_id): {
            int(player_row[1]): Rating(
                float(player_row[3]), float(player_row[4])
            )
            for player_row in season_players
        }
        for season_id, season_players in get_player_rows_by_season(skill_db, seasons)
    }


def get_season_players(skill_db: DbConnection, season: int) -> List[Player]:
    """
    Get all players for a specific season.

    Args:
        skill_db: Skill database connection
        season: Season ID to get players for

    Returns:
        List of Player objects with their seasonal skill ratings
    """
    return [
        Player(
            int(player_id),
            str(steam_name),
            float(skill_mean),
            float(skill_stdev),
            0.0 if impact_rating is None else float(impact_rating)
        )
        for season_id, player_rows in get_player_rows_by_season(skill_db, [season])
        for season_id_, player_id, steam_name, skill_mean, skill_stdev, impact_rating in player_rows
    ]


def get_player_profile(
    skill_db: DbConnection, player_id: int
) -> Tuple[Player, PlayerRecord]:
    """
    Get a player's profile with overall record.

    Args:
        skill_db: Skill database connection
        player_id: ID of the player to get profile for

    Returns:
        Tuple of (Player object, record dictionary)

    Raises:
        StopIteration: If the player doesn't exist
    """
    row = execute_one(
        skill_db,
        """
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
    """,
        (player_id,),
    )

    steam_name, skill_mean, skill_stdev, impact_rating, rounds_won, rounds_lost = row

    player = Player(
        player_id,
        str(steam_name),
        float(skill_mean),
        float(skill_stdev),
        0.0 if impact_rating is None else float(impact_rating)
    )

    overall_record: PlayerRecord = {
        "rounds_won": int(rounds_won),
        "rounds_lost": int(rounds_lost),
    }

    return player, overall_record


def get_players_in_last_round(skill_db: DbConnection) -> Set[int]:
    """
    Get the set of player IDs that participated in the most recent round.

    Args:
        skill_db: Skill database connection

    Returns:
        Set of player IDs
    """
    player_ids = execute(
        skill_db,
        """
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
    """,
    )
    return {cast(int, row[0]) for row in player_ids}


def get_all_rounds(
    skill_db: DbConnection,
    round_range: Optional[Tuple[int, int]]
) -> List[RoundRow]:
    """
    Get all rounds from the database.

    Args:
        skill_db: Skill database connection
        round_range: Optional tuple of (min_id, max_id) to filter by

    Returns:
        List of RoundRow objects
    """
    if round_range is not None:
        where_clause = "WHERE round_id BETWEEN ? AND ?"
        params: Tuple[Any, ...] = round_range
    else:
        where_clause = ""
        params = ()

    rounds = execute(
        skill_db,
        f"""
    SELECT round_id, created_at, season_id, winner, loser, mvp
    FROM rounds
    {where_clause}
    """,
        params,
    )
    return [
        RoundRow(
            cast(int, round_id),
            cast(datetime.datetime, created_at),
            cast(int, season_id),
            cast(int, winner),
            cast(int, loser),
            cast(Optional[int], mvp)
        )
        for round_id, created_at, season_id, winner, loser, mvp in rounds
    ]


def get_all_teams(skill_db: DbConnection) -> Dict[int, FrozenSet[int]]:
    """
    Get all teams and their member player IDs.

    Args:
        skill_db: Skill database connection

    Returns:
        Dictionary mapping team IDs to frozen sets of player IDs
    """
    memberships = execute(
        skill_db,
        """
    SELECT team_id, player_id
    FROM team_membership
    ORDER BY team_id
    """,
    )
    return {
        cast(int, team_id): frozenset(cast(int, team[1]) for team in teams)
        for team_id, teams in itertools.groupby(memberships, operator.itemgetter(0))
    }


def get_game_state_progress(skill_db: DbConnection) -> int:
    """
    Get the ID of the last processed game state.

    Args:
        skill_db: Skill database connection

    Returns:
        Game state ID of the last processed state, or 0 if none processed yet
    """
    try:
        result = execute_one(
            skill_db,
            """
        SELECT last_processed_game_state
        FROM game_state_progress
        """,
        )
        return int(result[0])
    except StopIteration:
        return 0


def save_game_state_progress(skill_db: DbConnection, max_game_state_id: int) -> None:
    """
    Save the progress of game state processing.

    Args:
        skill_db: Skill database connection
        max_game_state_id: ID of the last processed game state
    """
    cursor = skill_db.cursor()
    cursor.execute(
        """
    REPLACE INTO game_state_progress (
      game_state_progress_id
    , updated_at
    , last_processed_game_state
    ) VALUES (1, CURRENT_TIMESTAMP, ?)
    """,
        [max_game_state_id],
    )


def update_player_skills(
    skill_db: DbConnection,
    ratings: Dict[int, Rating],
    impact_ratings: Dict[int, float]
) -> None:
    """
    Update players' skill ratings and impact ratings.

    Args:
        skill_db: Skill database connection
        ratings: Dictionary mapping player IDs to Rating objects
        impact_ratings: Dictionary mapping player IDs to impact rating values
    """
    cursor = skill_db.cursor()
    for player_id, rating in ratings.items():
        cursor.execute(
            """
        UPDATE players
        SET skill_mean = ?
          , skill_stdev = ?
          , impact_rating = ?
        WHERE player_id = ?
        """,
            (rating.mu, rating.sigma, impact_ratings[player_id], player_id),
        )


def replace_overall_skill_history(
    skill_db: DbConnection,
    skill_history: List[SkillHistory]
) -> None:
    """
    Replace the overall skill history with new data.

    Args:
        skill_db: Skill database connection
        skill_history: List of SkillHistory objects to insert
    """
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
        cursor.execute(
            f"""
        REPLACE INTO overall_skill_history (
            player_id
          , round_id
          , skill_mean
          , skill_stdev
        )
        VALUES {placeholder}
        """,
            params,
        )


def replace_season_skills(
    skill_db: DbConnection,
    season_skills: Dict[Tuple[int, int], Rating],
    season_impact_ratings: Dict[int, Dict[int, float]],
) -> None:
    """
    Replace season-specific skills with new data.

    Args:
        skill_db: Skill database connection
        season_skills: Dictionary mapping (player_id, season_id) tuples to Rating objects
        season_impact_ratings: Dictionary mapping season IDs to player ID to impact rating dictionaries
    """
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

    cursor.execute(
        f"""
    REPLACE INTO skills (
      player_id
    , season_id
    , mean
    , stdev
    , impact_rating
    ) VALUES {make_placeholder(5, len(season_skills))}
    """,
        params,
    )


def _skill_history_sort_key(history: SkillHistory) -> Tuple[int, int]:
    """
    Helper function to sort skill history by player ID and round ID.

    Args:
        history: SkillHistory object

    Returns:
        Tuple of (player_id, round_id) for sorting
    """
    return history.player_id, history.round_id


def replace_season_skill_history(
    skill_db: DbConnection,
    history_by_season: Dict[int, List[SkillHistory]]
) -> None:
    """
    Replace season-specific skill history with new data.

    Args:
        skill_db: Skill database connection
        history_by_season: Dictionary mapping season IDs to lists of SkillHistory objects
    """
    skill_history: List[SkillHistory] = list(
        itertools.chain(*history_by_season.values())
    )

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
        cursor.execute(
            f"""
        REPLACE INTO season_skill_history (
            player_id
          , round_id
          , skill_mean
          , skill_stdev
        )
        VALUES {placeholder}
        """,
            params,
        )


def make_skill_history(
    player_id: int, skill_history: Iterator[Tuple[str, float, float]]
) -> Dict[str, Player]:
    """
    Create a dictionary of Player objects from skill history data.

    Args:
        player_id: ID of the player
        skill_history: Iterator of (date_str, skill_mean, skill_stdev) tuples

    Returns:
        Dictionary mapping date strings to Player objects
    """
    return {
        str(date): Player(player_id, "", float(skill_mean), float(skill_stdev), 0.0)
        for date, skill_mean, skill_stdev in skill_history
    }


def adapt_timezone(tz: datetime.timezone) -> str:
    """
    Convert a timezone object to a string format for SQLite.

    Args:
        tz: Timezone object

    Returns:
        String representation of the timezone offset (e.g., "+01:00")
    """
    utcoffset = tz.utcoffset(None)
    if utcoffset is None:
        return "+00:00"

    signum = "+" if utcoffset.days == 0 else "-"
    hours = utcoffset.seconds // 3600
    minutes = utcoffset.seconds % 3600 // 60
    return f"{signum}{hours:02}:{minutes:02}"


def get_impact_ratings_by_day(
    skill_db: DbConnection,
    player_id: int,
    tz: datetime.timezone,
    season_id: Optional[int] = None
) -> Dict[str, float]:
    """
    Get a player's impact ratings by day.

    Args:
        skill_db: Skill database connection
        player_id: ID of the player to get ratings for
        tz: Timezone for grouping dates
        season_id: Optional season ID to filter by

    Returns:
        Dictionary mapping date strings to impact rating values
    """
    tz_offset = adapt_timezone(tz)

    format_args: List[Any] = list(COEFFICIENTS)
    params: List[Any] = [tz_offset, player_id]
    if season_id is not None:
        format_args.append("AND r.season_id = ?")
        params.append(season_id)
    else:
        format_args.append("")

    ratings = execute(
        skill_db,
        """
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
     """.format(
            *format_args
        ),
        params,
    )
    return {cast(str, row[0]): cast(float, row[1]) for row in ratings}


def get_overall_skill_history(
    skill_db: DbConnection,
    player_id: int,
    tz: datetime.timezone
) -> Dict[str, Player]:
    """
    Get a player's overall skill history across all seasons.

    Args:
        skill_db: Skill database connection
        player_id: ID of the player to get history for
        tz: Timezone for grouping dates

    Returns:
        Dictionary mapping date strings to Player objects with historical skills
    """
    tz_offset = adapt_timezone(tz)
    skill_history = execute(
        skill_db,
        """
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
    """,
        (tz_offset, tz_offset, tz_offset, player_id),
    )
    return make_skill_history(player_id, skill_history)


def get_season_skill_history(
    skill_db: DbConnection,
    season: int,
    player_id: int,
    tz: datetime.timezone
) -> Dict[str, Player]:
    """
    Get a player's skill history for a specific season.

    Args:
        skill_db: Skill database connection
        season: Season ID to get history for
        player_id: ID of the player to get history for
        tz: Timezone for grouping dates

    Returns:
        Dictionary mapping date strings to Player objects with historical skills
    """
    tz_offset = adapt_timezone(tz)
    skill_history = execute(
        skill_db,
        """
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
    """,
        (tz_offset, tz_offset, tz_offset, season, player_id),
    )
    return make_skill_history(player_id, skill_history)


def get_season_range(skill_db: DbConnection) -> List[int]:
    """
    Get the range of seasons available in the database.

    Args:
        skill_db: Skill database connection

    Returns:
        List of sequential season IDs from 1 to max
    """
    row = execute_one(skill_db, "SELECT COUNT(*) FROM seasons")
    season_count = int(row[0])
    return list(range(1, season_count + 1))


def initialize_skill_db(skill_db: DbConnection) -> None:
    """
    Initialize the skill database schema if it doesn't exist.

    This creates all the necessary tables and indices for tracking player skills
    and game statistics.

    Args:
        skill_db: Skill database connection to initialize
    """
    logger.debug("Initializing skill_db")
    cursor = skill_db.cursor()

    # Seasons table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS seasons(
      season_id  INTEGER PRIMARY KEY
    , start_date DATETIME NOT NULL
    );
    """
    )

    # Players table
    cursor.execute(
        f"""
    CREATE TABLE IF NOT EXISTS players(
      player_id     INTEGER PRIMARY KEY
    , steam_name    TEXT    NOT NULL
    , skill_mean    DOUBLE  NOT NULL DEFAULT {SKILL_MEAN}
    , skill_stdev   DOUBLE  NOT NULL DEFAULT {SKILL_STDEV}
    , impact_rating DOUBLE
    );
    """
    )

    # Season-specific skills
    cursor.execute(
        """
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
    """
    )

    # Teams table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS teams(
      team_id    INTEGER PRIMARY KEY
    , created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    )

    # Team membership
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS team_membership(
      player_id INTEGER NOT NULL
    , team_id   INTEGER NOT NULL
    , PRIMARY KEY (player_id, team_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (team_id) REFERENCES teams (team_id)
    );
    """
    )

    # Maps table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS maps(
      map_id     INTEGER PRIMARY KEY
    , map_name   TEXT NOT NULL UNIQUE
    );
    """
    )

    # Rounds table
    cursor.execute(
        """
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
    """
    )

    # Indices for common round lookups
    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS ix_rounds_winner ON rounds (winner);
    """
    )

    cursor.execute(
        """
    CREATE INDEX IF NOT EXISTS ix_rounds_loser ON rounds (loser);
    """
    )

    # Player weapon statistics
    cursor.execute(
        """
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
    """
    )

    # Player roles
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS player_roles(
      player_id INTEGER NOT NULL
    , role      TEXT NOT NULL
    , PRIMARY KEY (player_id, role)
    );
    """
    )

    # Overall skill history
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS overall_skill_history(
      player_id   INTEGER NOT NULL
    , round_id    INTEGER NOT NULL
    , skill_mean  DOUBLE NOT NULL
    , skill_stdev DOUBLE NOT NULL
    , PRIMARY KEY (player_id, round_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (round_id) REFERENCES rounds (round_id)
    );
    """
    )

    # Season-specific skill history
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS season_skill_history(
      player_id   INTEGER NOT NULL
    , round_id    INTEGER NOT NULL
    , skill_mean  DOUBLE NOT NULL
    , skill_stdev DOUBLE NOT NULL
    , PRIMARY KEY (player_id, round_id)
    , FOREIGN KEY (player_id) REFERENCES players (player_id)
    , FOREIGN KEY (round_id) REFERENCES rounds (round_id)
    );
    """
    )

    # Round statistics
    cursor.execute(
        """
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
    """
    )

    # Rating components view
    cursor.execute(
        """
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
    """
    )

    # Game state processing progress
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS game_state_progress(
      game_state_progress_id    INTEGER PRIMARY KEY
    , updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP
    , last_processed_game_state INTEGER NOT NULL
    );
    """
    )


def initialize_dbs() -> None:
    """
    Initialize both game and skill databases.

    Creates the data directory if it doesn't exist and initializes both database schemas.
    """
    if not os.path.exists(DATA_DIR):
        os.mkdir(DATA_DIR)
    with get_skill_db() as skill_db, get_game_db() as game_db:
        initialize_skill_db(skill_db)
        initialize_game_db(game_db)
        skill_db.commit()
        game_db.commit()
