import argparse
import datetime
import json
import logging
import pathlib
import sqlite3
from google.protobuf.timestamp_pb2 import Timestamp
from tqdm import tqdm
from truescrub.proto.game_state_pb2 import GameStateEntry

from truescrub.db import get_game_state_count, get_raw_game_states, \
  initialize_game_db
from truescrub.statewriter.game_state_log import GameStateLog
from truescrub.statewriter.state_parsing import parse_game_state, \
  InvalidGameStateException
from truescrub.statewriter.state_serialization import serialize_game_state

logger = logging.getLogger(__name__)


def iter_entries_from_db(connection) -> 'Iterator[GameStateEntry]':
  """Yield GameStateEntry protos from a SQLite game state database."""
  total = get_game_state_count(connection)
  for game_state_id, created_at, game_state in tqdm(
      get_raw_game_states(connection), total=total,
      desc="Reading game states"):
    try:
      gs_proto = parse_game_state(game_state)
    except InvalidGameStateException as e:
      logger.warning('skipping invalid round (reason: %s): %s',
                     e, json.dumps(game_state))
      continue
    timestamp = Timestamp()
    timestamp.FromSeconds(created_at)
    yield GameStateEntry(
      game_state_id=game_state_id,
      created_at=timestamp,
      game_state=gs_proto)


def db_to_riegeli(db_path: pathlib.Path, riegeli_path: pathlib.Path):
  if riegeli_path.exists():
    riegeli_path.unlink()
  log = GameStateLog(riegeli_path)

  connection = sqlite3.connect(db_path)
  try:
    with log.writer(0.0) as writer:
      for entry in iter_entries_from_db(connection):
        writer.append(entry)
  finally:
    connection.close()


def insert_historical_game_state(game_db: sqlite3.Connection,
                                 game_state_id: int,
                                 created_at: datetime.datetime, state: dict):
  cursor = game_db.cursor()
  state_json = json.dumps(state)
  cursor.execute(
    'INSERT INTO game_state (game_state_id, created_at, game_state) VALUES (?, ?, ?)',
    (game_state_id, created_at, state_json)
  )


def riegeli_to_db(riegeli_path: pathlib.Path, db_path: pathlib.Path):
  if db_path.exists():
    db_path.unlink()
  log = GameStateLog(riegeli_path)
  connection = sqlite3.connect(db_path)
  try:
    initialize_game_db(connection)

    with log.reader(0.0) as reader:
      for entry in tqdm(reader, desc="Translating to SQLite"):
        created_at = entry.created_at.ToDatetime().replace(
          tzinfo=datetime.timezone.utc)
        game_state_json = serialize_game_state(entry.game_state)
        insert_historical_game_state(connection, entry.game_state_id,
                                     created_at, game_state_json)
    connection.commit()
  finally:
    connection.close()


def make_arg_parser():
  arg_parser = argparse.ArgumentParser(
    description="Translate between SQLite and Riegeli game state logs.")
  arg_parser.add_argument('-i', '--input', type=pathlib.Path, required=True,
                          help='Input file (.db or .riegeli)')
  arg_parser.add_argument('-o', '--output', type=pathlib.Path, required=True,
                          help='Output file (.db or .riegeli)')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()

  if opts.input.suffix == '.db' and opts.output.suffix == '.riegeli':
    db_to_riegeli(opts.input, opts.output)
  elif opts.input.suffix == '.riegeli' and opts.output.suffix == '.db':
    riegeli_to_db(opts.input, opts.output)
  else:
    raise ValueError(
      f"Unsupported translation direction: {opts.input.suffix} to {opts.output.suffix}. Expected .db to .riegeli or .riegeli to .db")


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  main()
