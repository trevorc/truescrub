import datetime
import operator
import sqlite3
from typing import Dict, List, Optional, Tuple, TypedDict

from truescrub.db import COEFFICIENTS, execute, execute_one
from truescrub.models import SKILL_MEAN, SKILL_STDEV, Player, skill_group_name


class SkillGroupInfo(TypedDict):
    mmr: int
    skill_group: str


class SkillGroupChange(TypedDict):
    player_id: int
    steam_name: str
    previous_skill: SkillGroupInfo
    next_skill: SkillGroupInfo


class RatingDetails(TypedDict):
    average_kills: float
    average_deaths: float
    average_damage: float
    average_assists: float
    total_kills: int
    total_deaths: int
    total_damage: int
    total_assists: int
    kdr: float


class PlayerRating(TypedDict):
    player_id: int
    steam_name: str
    impact_rating: float
    previous_skill: SkillGroupInfo
    rating_details: RatingDetails
    rounds_played: int
    mvps: int


class Highlights(TypedDict):
    time_window: List[str]
    rounds_played: int
    most_played_maps: Dict[str, int]
    player_ratings: List[PlayerRating]
    season_skill_group_changes: List[SkillGroupChange]


def get_highlights(skill_db: sqlite3.Connection, day: datetime.datetime) -> Highlights:
    """
    Get game highlights for a specific day.

    Args:
        skill_db: Database connection
        day: Date to get highlights for

    Returns:
        Dictionary with highlights information

    Raises:
        StopIteration: If no rounds were played on that day
    """
    round_range, rounds_played = get_round_range_for_day(skill_db, day)

    if rounds_played == 0:
        raise StopIteration

    # Ensure round range values are not None before passing to functions
    if round_range[0] is None or round_range[1] is None:
        # This shouldn't happen if rounds_played > 0, but handle it just in case
        raise ValueError("Invalid round range: contains None values")

    round_range_valid = (int(round_range[0]), int(round_range[1]))

    player_ratings = get_player_ratings_between_rounds(skill_db, round_range_valid)
    most_played_maps = get_most_played_maps_between_rounds(skill_db, round_range_valid)

    skill_group_changes: List[SkillGroupChange] = [
        {
            "player_id": previous_skill.player_id,
            "steam_name": previous_skill.steam_name,
            "previous_skill": {
                "mmr": previous_skill.mmr,
                "skill_group": skill_group_name(previous_skill.skill_group_index),
            },
            "next_skill": {
                "mmr": next_skill.mmr,
                "skill_group": skill_group_name(next_skill.skill_group_index),
            },
        }
        for (previous_skill, next_skill) in get_skill_changes_between_rounds(
            skill_db, round_range_valid
        )
    ]
    time_window = [day.isoformat(), (day + datetime.timedelta(days=1)).isoformat()]
    return {
        "time_window": time_window,
        "rounds_played": rounds_played,
        "most_played_maps": most_played_maps,
        "player_ratings": player_ratings,
        "season_skill_group_changes": skill_group_changes,
    }


def get_most_played_maps_between_rounds(
    skill_db: sqlite3.Connection, round_range: Tuple[int, int]
) -> Dict[str, int]:
    """
    Get the most played maps between a range of rounds.

    Args:
        skill_db: Database connection
        round_range: Tuple of (first_round_id, last_round_id)

    Returns:
        Dictionary mapping map names to play counts
    """
    return dict(
        execute(
            skill_db,
            """
    SELECT map_name
         , COUNT(*) AS round_count
    FROM rounds
    JOIN maps ON rounds.map_id = maps.map_id
    WHERE round_id BETWEEN ? AND ?
    GROUP BY map_name
    ORDER BY round_count DESC
    """,
            round_range,
        )
    )


def make_player_rating(
    player: Player, rating_details: RatingDetails, rounds_played: int, mvps: int
) -> PlayerRating:
    """
    Create a player rating dictionary from the given data.

    Args:
        player: The player
        rating_details: Statistics about the player's performance
        rounds_played: Number of rounds played
        mvps: Number of MVPs earned

    Returns:
        Dictionary with player rating information
    """
    return {
        "player_id": player.player_id,
        "steam_name": player.steam_name,
        "impact_rating": player.impact_rating,
        "previous_skill": {
            "mmr": player.mmr,
            "skill_group": skill_group_name(player.skill_group_index),
        },
        "rating_details": rating_details,
        "rounds_played": rounds_played,
        "mvps": mvps,
    }


def get_player_ratings_between_rounds(
    skill_db: sqlite3.Connection, round_range: Tuple[int, int]
) -> List[PlayerRating]:
    """
    Get player ratings between a range of rounds.

    Args:
        skill_db: Database connection
        round_range: Tuple of (first_round_id, last_round_id)

    Returns:
        List of player ratings sorted by impact rating (descending)
    """
    rating_details = execute(
        skill_db,
        """
    WITH components AS (
            SELECT rc.player_id
                 , AVG(rc.kill_rating) AS average_kills
                 , AVG(rc.death_rating) AS average_deaths
                 , AVG(rc.damage_rating) AS average_damage
                 , AVG(rc.kas_rating) AS average_kas
                 , AVG(rc.assists_rating) AS average_assists
                 , COUNT(*) AS rounds_played
                 , SUM(rc.mvp_rating) AS total_mvps
            FROM rating_components rc
            WHERE rc.round_id BETWEEN ? AND ?
            GROUP BY rc.player_id
        ), impact_ratings AS (
            SELECT c.player_id
                 , {} * c.average_kills
                 + {} * c.average_deaths
                 + {} * c.average_damage
                 + {} * c.average_kas
                 + {} AS rating
                 , c.*
            FROM components c
        ), starting_skills AS (
            SELECT ssh.player_id
                 , ssh.skill_mean
                 , ssh.skill_stdev
            FROM season_skill_history ssh
            JOIN ( SELECT ssh2.player_id
                        , MAX(ssh2.round_id) AS max_round_id
                   FROM season_skill_history ssh2
                   WHERE ssh2.round_id < ?
                   GROUP BY ssh2.player_id
               ) ms
            ON ms.player_id = ssh.player_id
            AND ssh.round_id = ms.max_round_id
        )
    SELECT players.player_id
         , players.steam_name
         , ir.rating
         , ir.average_kills
         , -ir.average_deaths AS average_deaths
         , ir.average_damage
         , ir.average_kas
         , ir.average_assists
         , ir.rounds_played
         , ir.total_mvps
         , s.skill_mean
         , s.skill_stdev
    FROM players
    JOIN impact_ratings ir
    ON   players.player_id = ir.player_id
    LEFT JOIN starting_skills s
    ON   players.player_id = s.player_id
    """.format(
            *COEFFICIENTS
        ),
        (round_range[0], round_range[1], round_range[0]),
    )

    player_ratings: List[PlayerRating] = []

    for row in rating_details:
        (
            player_id,
            steam_name,
            impact_rating,
            average_kills,
            average_deaths,
            average_damage,
            average_kas,
            average_assists,
            rounds_played,
            mvps,
            skill_mean,
            skill_stdev,
        ) = row

        # Handle null values from the database
        skill_mean_value = SKILL_MEAN if skill_mean is None else float(skill_mean)
        skill_stdev_value = SKILL_STDEV if skill_stdev is None else float(skill_stdev)
        rounds_played_value = int(rounds_played)

        # Ensure all values are the correct type
        player = Player(
            int(player_id),
            str(steam_name),
            skill_mean_value,
            skill_stdev_value,
            float(impact_rating),
        )

        rating_details_dict: RatingDetails = {
            "average_kills": float(average_kills),
            "average_deaths": float(average_deaths),
            "average_damage": float(average_damage),
            "average_assists": float(average_assists),
            "total_kills": int(float(average_kills) * rounds_played_value),
            "total_deaths": int(float(average_deaths) * rounds_played_value),
            "total_damage": int(float(average_damage) * rounds_played_value),
            "total_assists": int(float(average_assists) * rounds_played_value),
            "kdr": (float(average_kills) * rounds_played_value)
            / max(1.0, float(average_deaths) * rounds_played_value),
        }

        player_rating = make_player_rating(
            player, rating_details_dict, rounds_played_value, int(mvps)
        )
        player_ratings.append(player_rating)

    player_ratings.sort(key=operator.itemgetter("impact_rating"), reverse=True)

    return player_ratings


def get_skill_changes_between_rounds(
    skill_db: sqlite3.Connection, round_range: Tuple[int, int]
) -> List[Tuple[Player, Player]]:
    """
    Get skill changes between a range of rounds.

    Args:
        skill_db: Database connection
        round_range: Tuple of (first_round_id, last_round_id)

    Returns:
        List of tuples containing (previous_skill, next_skill) for players
        who changed skill groups, sorted by next skill MMR (descending)
    """
    skill_change_rows = execute(
        skill_db,
        """
    SELECT players.player_id
         , players.steam_name
         , earlier_ssh.skill_mean  AS earlier_skill_mean
         , earlier_ssh.skill_stdev AS earlier_skill_stdev
         , later_ssh.skill_mean    AS later_skill_mean
         , later_ssh.skill_stdev   AS later_skill_stdev
    FROM players
    JOIN season_skill_history later_ssh
    ON players.player_id = later_ssh.player_id
    AND later_ssh.round_id =
        ( SELECT MAX(ssh_after.round_id)
          FROM season_skill_history ssh_after
          WHERE ssh_after.round_id BETWEEN ? AND ?
          AND ssh_after.player_id = players.player_id
        )
    JOIN rounds later_round
    ON later_ssh.round_id = later_round.round_id
    LEFT JOIN season_skill_history earlier_ssh
    ON players.player_id = earlier_ssh.player_id
    AND earlier_ssh.round_id =
        ( SELECT MAX(ssh_before.round_id)
          FROM season_skill_history ssh_before
          JOIN rounds rounds_before
          ON ssh_before.round_id = rounds_before.round_id
          WHERE ssh_before.round_id < ?
          AND ssh_before.player_id = players.player_id
          AND rounds_before.season_id = later_round.season_id
        )
    """,
        (round_range[0], round_range[1], round_range[0]),
    )

    skill_changes: List[Tuple[Player, Player]] = []

    for row in skill_change_rows:
        player_id, steam_name, earlier_mean, earlier_stdev, later_mean, later_stdev = (
            row
        )

        # Create previous and next player objects
        previous_player = Player(
            int(player_id),
            str(steam_name),
            SKILL_MEAN if earlier_mean is None else float(earlier_mean),
            SKILL_STDEV if earlier_stdev is None else float(earlier_stdev),
            0.0,
        )

        next_player = Player(
            int(player_id), str(steam_name), float(later_mean), float(later_stdev), 0.0
        )

        skill_changes.append((previous_player, next_player))

    skill_changes.sort(key=lambda change: -change[1].mmr)

    return [
        (previous_skill, next_skill)
        for previous_skill, next_skill in skill_changes
        if previous_skill.skill_group_index != next_skill.skill_group_index
    ]


def get_round_range_for_day(
    skill_db: sqlite3.Connection, day: datetime.datetime
) -> Tuple[Tuple[Optional[int], Optional[int]], int]:
    """
    Get the range of round IDs for a specific day.

    Args:
        skill_db: Database connection
        day: The day to get rounds for

    Returns:
        Tuple containing ((first_round_id, last_round_id), round_count)
        where round IDs may be None if no rounds were played
    """
    next_day = day + datetime.timedelta(days=1)

    first_round, last_round, round_count = execute_one(
        skill_db,
        """
    SELECT MIN(round_id)
         , MAX(round_id)
         , COUNT(*)
    FROM rounds
    WHERE created_at BETWEEN ? AND ?
    """,
        (day, next_day),
    )

    # Handle case where no rounds were played (NULL values from database)
    first_round_id = int(first_round) if first_round is not None else None
    last_round_id = int(last_round) if last_round is not None else None

    return (first_round_id, last_round_id), int(round_count)
