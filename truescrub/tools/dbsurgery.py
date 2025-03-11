"""Database surgery tool for purging rounds containing specific players.

This module provides functionality to remove game states and rounds
associated with a specific player from the database. This is useful
for correcting data issues or removing problematic matches.
"""

import argparse
import logging
import sqlite3
import sys
from typing import Iterator, Set, Tuple

from truescrub.db import (
    execute,
    execute_one,
    get_game_db,
    get_player_profile,
    get_skill_db,
)
from truescrub.models import Player

logger = logging.getLogger(__name__)


class ImpactedGameStateStats:
    """Statistics for game states impacted by a purge operation.

    Tracks information about game states that will be purged, including
    the maps involved, number of rounds, and game state ID ranges.
    """

    def __init__(self) -> None:
        """Initialize a new statistics container with default values."""
        self.maps: Set[str] = set()
        self.min_game_state: int = sys.maxsize
        self.max_game_state: int = 0
        self.rounds: int = 0
        self.game_states: int = 0


def get_impacted_game_state_stats(
    game_db: sqlite3.Connection, condition: str
) -> ImpactedGameStateStats:
    """Get statistics about game states that match the given condition.

    Args:
        game_db: Connection to the game database
        condition: SQL condition for selecting game states

    Returns:
        Statistics about the selected game states
    """
    stats = ImpactedGameStateStats()
    results: Iterator[Tuple[int, str, str, str]] = execute(
        game_db,
        f"""
  SELECT game_state_id
     , json_extract(game_state, '$.map.name')
     , json_extract(game_state, '$.round.phase')
     , json_extract(game_state, '$.previously.round.phase')
  FROM game_state
  WHERE {condition}
  """,
    )

    for game_state_id, map_name, round_phase, previous_phase in results:
        stats.maps.add(map_name)
        if previous_phase == "live" and round_phase == "over":
            stats.rounds += 1
        stats.min_game_state = min(stats.min_game_state, game_state_id)
        stats.max_game_state = max(stats.max_game_state, game_state_id)
        stats.game_states += 1

    return stats


def get_impacted_game_state_range(
    game_db: sqlite3.Connection, tentative_stats: ImpactedGameStateStats
) -> Tuple[int, int]:
    """Get the range of game state IDs to delete.

    This expands the range from the tentative stats to include the complete
    rounds at the start and end of the range.

    Args:
        game_db: Connection to the game database
        tentative_stats: Statistics about game states to delete

    Returns:
        Tuple of (start_game_state_id, end_game_state_id)
    """
    round_start_result: Tuple[int, str] = execute_one(
        game_db,
        """
  SELECT game_state_id
       , json_extract(game_state, '$.round.phase')
  FROM game_state
  WHERE game_state_id =
        ( SELECT MAX(g2.game_state_id)
          FROM game_state g2
          WHERE g2.game_state_id < ?
                  AND json_extract(g2.game_state,
                                   '$.previously.round.phase') = 'over'
        );
  """,
        [tentative_stats.min_game_state],
    )
    round_start_game_state, round_start_phase = round_start_result
    logger.info("Round start phase: %s", round_start_phase)

    round_end_result: Tuple[int, str] = execute_one(
        game_db,
        """
    SELECT game_state_id
         , json_extract(game_state, '$.round.phase')
    FROM game_state
    WHERE game_state_id =
          ( SELECT MIN(g2.game_state_id)
            FROM game_state g2
            WHERE g2.game_state_id > ?
                    AND json_extract(g2.game_state,
                                     '$.previously.round.phase') = 'over'
          );
    """,
        [tentative_stats.max_game_state],
    )
    round_end_game_state, round_end_phase = round_end_result
    logger.info("Round end phase: %s", round_end_phase)

    return round_start_game_state, round_end_game_state


def delete_game_states(
    game_db: sqlite3.Connection,
    final_stats: ImpactedGameStateStats,
    round_end_game_state: int,
    round_start_game_state: int,
) -> None:
    """Delete game states within the specified range.

    Args:
        game_db: Connection to the game database
        final_stats: Statistics about the game states to delete
        round_end_game_state: End of the range of game state IDs to delete
        round_start_game_state: Start of the range of game state IDs to delete
    """
    execute(
        game_db,
        f"""
  DELETE FROM game_state
  WHERE game_state_id BETWEEN {round_start_game_state} AND {round_end_game_state}
  """,
    )
    logger.debug(
        "%d game states and %d rounds deleted",
        final_stats.game_states,
        final_stats.rounds,
    )


def purge_rounds_with_player(game_db: sqlite3.Connection, player: Player) -> None:
    """Purge all rounds containing the specified player from the database.

    Args:
        game_db: Connection to the game database
        player: Player to remove from the database
    """
    tentative_stats = get_impacted_game_state_stats(
        game_db,
        f"""
  json_type(game_state, '$.allplayers.{player.player_id}') IS NOT NULL
  """,
    )
    logger.info(
        "Found %d game states including %d rounds containing %r",
        tentative_stats.game_states,
        tentative_stats.rounds,
        player.steam_name,
    )
    if tentative_stats.game_states == 0:
        logger.debug("No matching game states found; exiting")
        return
    logger.info("Tentative maps: %s", ", ".join(tentative_stats.maps))

    round_start_game_state, round_end_game_state = get_impacted_game_state_range(
        game_db, tentative_stats
    )
    final_stats = get_impacted_game_state_stats(
        game_db,
        f"""
  game_state_id BETWEEN {round_start_game_state} AND {round_end_game_state}
  """,
    )

    print(
        f"Deleting {final_stats.game_states} game states "
        f"including {final_stats.rounds} rounds"
    )
    logger.info("Impacted maps: %s", ", ".join(map(str, final_stats.maps)))

    confirmation = input(
        "Confirm deletion by typing the number of game states that will be erased: "
    )
    if confirmation != str(final_stats.game_states):
        print("Aborting")
        return

    delete_game_states(
        game_db, final_stats, round_end_game_state, round_start_game_state
    )


def make_arg_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the command line interface.

    Returns:
        An ArgumentParser instance configured with the tool's options
    """
    arg_parser = argparse.ArgumentParser(
        description="Purge rounds containing specific players from the database"
    )
    arg_parser.add_argument(
        "steamid", type=int, help="purge rounds containing this player"
    )
    return arg_parser


def main() -> None:
    """Main entry point for the dbsurgery tool.

    Parses command line arguments, looks up the specified player,
    and purges rounds containing that player from the database.
    """
    opts = make_arg_parser().parse_args()
    logging.basicConfig(
        format="%(asctime)s.%(msecs).3dZ\t%(name)s\t%(levelname)s\t%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        level=logging.DEBUG,
    )

    with get_game_db() as game_db, get_skill_db() as skill_db:
        try:
            player_result = get_player_profile(skill_db, opts.steamid)
            player, overall_record = player_result
        except StopIteration:
            print("No such player found")
            return

        logger.info(
            "Deleting rounds including player %s (record: %d-%d)",
            player.steam_name,
            overall_record["rounds_won"],
            overall_record["rounds_lost"],
        )
        purge_rounds_with_player(game_db, player)


if __name__ == "__main__":
    main()
