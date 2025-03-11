import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from truescrub import db
from truescrub.queue_consumer import QueueConsumer
from truescrub.updater.recalculate import (
    compute_rounds_and_players,
    recalculate,
    recalculate_ratings,
)

logger = logging.getLogger(__name__)

# Type aliases
GameStateID = int
Message = Dict[str, Any]


def process_game_states(game_states: List[GameStateID]) -> None:
    """Process a list of game state IDs to update player ratings.

    Args:
        game_states: List of game state IDs to process
    """
    logger.debug("processing game states %s", game_states)
    with db.get_game_db() as game_db, db.get_skill_db() as skill_db:
        game_db_conn: sqlite3.Connection = game_db
        skill_db_conn: sqlite3.Connection = skill_db

        max_processed_game_state: int = db.get_game_state_progress(skill_db_conn)
        new_max_game_state: int = max(game_states)
        game_state_range: Tuple[int, int] = (max_processed_game_state + 1, new_max_game_state)

        rounds_result = compute_rounds_and_players(game_db_conn, skill_db_conn, game_state_range)
        new_rounds: Optional[Tuple[int, int]] = rounds_result[1]

        if new_rounds is not None:
            recalculate_ratings(skill_db_conn, new_rounds)

        db.save_game_state_progress(skill_db_conn, new_max_game_state)
        skill_db_conn.commit()


class Updater(QueueConsumer):
    """Queue consumer that processes game state updates and recalculation requests."""

    def process_messages(self, messages: List[Union[Dict[str, Any], object]]) -> None:
        """Process messages from the queue, either updating game states or recalculating ratings.

        Args:
            messages: List of message dictionaries from the queue
        """
        # Cast all messages to the correct type for processing
        message_dicts = [cast(Message, msg) for msg in messages if isinstance(msg, dict)]

        if any(message.get("command") == "recalculate" for message in message_dicts):
            logger.debug("%s processing recalculate message", type(self).__name__)
            recalculate()
        else:
            logger.debug(
                "%s processing %d game states", type(self).__name__, len(message_dicts)
            )
            game_state_ids: List[GameStateID] = [
                message["game_state_id"] for message in message_dicts if "game_state_id" in message
            ]
            if game_state_ids:
                process_game_states(game_state_ids)
