"""Game state transformation utility.

This module provides utilities for converting game states from the database
into protocol buffer format for efficient storage and processing.
"""

import argparse
import json
import logging
import struct
from typing import Any, BinaryIO, Callable, Dict, Iterator, Tuple, cast

from google.protobuf import text_format
from google.protobuf.timestamp_pb2 import Timestamp
from tqdm import tqdm

from truescrub.db import get_game_db, get_game_state_count, get_raw_game_states
from truescrub.proto import game_state_pb2
from truescrub.state_serialization import (
    GameState,
    GameStateDict,
    InvalidGameStateException,
    parse_game_state,
)

logger = logging.getLogger(__name__)


# Type for writer functions that serialize protocol buffers to a file
WriterFunc = Callable[[game_state_pb2.GameStateEntry, BinaryIO], None]


def write_textpb(gs_proto: game_state_pb2.GameStateEntry, output: BinaryIO) -> None:
    """Write protocol buffer in text format with length prefix.

    Args:
        gs_proto: Protocol buffer message to serialize
        output: Binary file-like object to write to
    """
    serialized: str = text_format.MessageToString(gs_proto)
    output.write(f"{len(serialized)}\n".encode())
    output.write(serialized.encode("UTF-8"))


def write_protos(gs_proto: game_state_pb2.GameStateEntry, output: BinaryIO) -> None:
    """Write protocol buffer in binary format with length prefix.

    Args:
        gs_proto: Protocol buffer message to serialize
        output: Binary file-like object to write to
    """
    serialized: bytes = gs_proto.SerializeToString()
    output.write(struct.pack("<l", len(serialized)))
    output.write(serialized)


# Dictionary mapping format names to writer functions
FORMATS: Dict[str, WriterFunc] = {
    "textpb": write_textpb,
    "protos": write_protos,
}


def make_arg_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the command line interface.

    Returns:
        An ArgumentParser instance configured with the tool's options
    """
    arg_parser = argparse.ArgumentParser(
        description="Convert game states from the database to protocol buffer format"
    )
    arg_parser.add_argument(
        "-o",
        "--output",
        default="game_states.protos",
        help="write delimited protos to this file",
    )
    arg_parser.add_argument(
        "-f",
        "--format",
        choices=list(FORMATS.keys()),
        default="protos",
        help="output format (text or binary protobuf)"
    )
    return arg_parser


def main() -> None:
    """Main entry point for the gstrans tool.

    Converts game states from the database to protocol buffer format and
    writes them to a file in the specified format.
    """
    opts = make_arg_parser().parse_args()

    with get_game_db() as game_db, open(opts.output, "wb") as output:
        writer: WriterFunc = FORMATS[opts.format]
        total: int = get_game_state_count(game_db=game_db)
        game_states: Iterator[Tuple[int, int, Dict[str, Any]]] = get_raw_game_states(game_db=game_db)

        for game_state_id, created_at, game_state in tqdm(game_states, total=total):
            try:
                gs_proto: GameState = parse_game_state(cast(GameStateDict, game_state))
            except InvalidGameStateException as e:
                logger.warning(
                    "skipping invalid round (reason: %s): %s", e, json.dumps(game_state)
                )
                continue

            timestamp = Timestamp()
            timestamp.FromSeconds(created_at)

            gs_entry = game_state_pb2.GameStateEntry(
                game_state_id=game_state_id,
                created_at=timestamp,
                game_state=gs_proto
            )

            writer(gs_entry, output)


if __name__ == "__main__":
    main()
