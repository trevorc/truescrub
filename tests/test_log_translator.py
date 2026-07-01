import argparse
import datetime
import pathlib
import sqlite3

import pytest

from tests.db_test_utils import TestDBManager, create_game_state_for_round
from truescrub import seasoncfg
from truescrub.db import get_raw_game_states
from truescrub.statewriter import GameStateLog
from truescrub.statewriter.state_parsing import parse_game_state
from truescrub.tools.log_translator import db_to_riegeli, riegeli_to_db

SEASONS_TOML = pathlib.Path('tests/sample_seasons.toml')


def _make_game_states(day: datetime.datetime):
  ct_team = [(76561198000000001, 'Alice'), (76561198000000002, 'Bob')]
  t_team = [(76561198000000003, 'Carol')]
  states = []
  for i in range(3):
    gs = create_game_state_for_round(
      timestamp=day + datetime.timedelta(hours=i + 1),
      map_name='de_dust2',
      ct_team=ct_team,
      t_team=t_team,
      winner='CT',
      player_stats={
        76561198000000001: {'kills': 2, 'deaths': 0, 'damage': 100,
                            'survived': True, 'match_mvps': i},
        76561198000000002: {'kills': 1, 'deaths': 0, 'damage': 80,
                            'survived': True, 'match_mvps': i},
        76561198000000003: {'kills': 0, 'deaths': 1, 'damage': 30,
                            'survived': False, 'match_mvps': 0},
      },
    )
    states.append(gs)
  return states


@pytest.fixture
def sqlite_db_path(tmp_path, monkeypatch):
  monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
  day = datetime.datetime(2022, 3, 1)
  db_path = tmp_path / 'games.db'

  # Use TestDBManager to create game states in memory, then copy to file
  manager = TestDBManager()
  states = _make_game_states(day)
  manager.add_game_states(states)

  # Backup the in-memory db to a real file
  with sqlite3.connect(db_path) as file_db:
    manager.game_db.backup(file_db)

  manager.skill_db.close()
  manager.game_db.close()
  return db_path


def test_roundtrip(sqlite_db_path, tmp_path):
  riegeli_path = tmp_path / "translated.riegeli"
  roundtrip_db_path = tmp_path / "roundtrip.db"

  # Forward translation: db -> riegeli
  db_to_riegeli(sqlite_db_path, riegeli_path)

  # Reverse translation: riegeli -> db
  riegeli_to_db(riegeli_path, roundtrip_db_path)

  # Assert losslessness
  with sqlite3.connect(sqlite_db_path) as original_conn, \
      sqlite3.connect(roundtrip_db_path) as roundtrip_conn:

    orig_states = list(get_raw_game_states(original_conn))
    roundtrip_states = list(get_raw_game_states(roundtrip_conn))

    assert len(orig_states) == len(roundtrip_states)

    def normalize_proto(proto):
      # The deserialization/serialization roundtrip injects some defaults into weapons and round.
      # We clear them here to ensure the core data is losslessly preserved.
      for player in proto.allplayers:
        for weapon_key in list(player.weapons.DESCRIPTOR.fields_by_name.keys()):
          if player.weapons.HasField(weapon_key):
            weapon = getattr(player.weapons, weapon_key)
            weapon.ClearField('paintkit')
            weapon.ClearField('active')
      if proto.HasField('previously'):
        proto.ClearField('previously')
      if proto.HasField('player'):
        proto.ClearField('player')

    for orig, roundtrip in zip(orig_states, roundtrip_states):
      assert orig[0] == roundtrip[0]  # game_state_id
      assert orig[1] == roundtrip[1]  # created_at

      orig_proto = parse_game_state(orig[2])
      roundtrip_proto = parse_game_state(roundtrip[2])

      normalize_proto(orig_proto)
      normalize_proto(roundtrip_proto)

      assert orig_proto == roundtrip_proto  # Compare protobufs to ignore missing optional JSON fields


def verify_file_roundtrip(input_path: pathlib.Path, is_db: bool):
  import tempfile
  with tempfile.TemporaryDirectory() as tmpdir:
    tmp_path = pathlib.Path(tmpdir)
    if is_db:
      riegeli_path = tmp_path / "temp.riegeli"
      roundtrip_db_path = tmp_path / "roundtrip.db"
      db_to_riegeli(input_path, riegeli_path)
      riegeli_to_db(riegeli_path, roundtrip_db_path)

      with sqlite3.connect(input_path) as original_conn, \
          sqlite3.connect(roundtrip_db_path) as roundtrip_conn:
        orig_states = list(get_raw_game_states(original_conn))
        roundtrip_states = list(get_raw_game_states(roundtrip_conn))
    else:
      db_path = tmp_path / "temp.db"
      roundtrip_riegeli_path = tmp_path / "roundtrip.riegeli"
      riegeli_to_db(input_path, db_path)
      db_to_riegeli(db_path, roundtrip_riegeli_path)

      orig_log = GameStateLog(input_path)
      roundtrip_log = GameStateLog(roundtrip_riegeli_path)

      with orig_log.reader() as orig_reader, \
          roundtrip_log.reader() as roundtrip_reader:
        orig_states = list(orig_reader)
        roundtrip_states = list(roundtrip_reader)

    assert len(orig_states) == len(roundtrip_states), "Count mismatch"

    if is_db:
      for orig, roundtrip in zip(orig_states, roundtrip_states):
        assert orig == roundtrip, "Mismatch found in db roundtrip"
    else:
      for orig, roundtrip in zip(orig_states, roundtrip_states):
        assert orig.game_state_id == roundtrip.game_state_id
        assert orig.created_at == roundtrip.created_at
        assert orig.game_state == roundtrip.game_state

    print("Roundtrip successful and lossless!")


def pytest_addoption(parser):
  parser.addoption("--input_file", action="store", default=None,
                   help="Input DB or Riegeli log file to test")


def main():
  parser = argparse.ArgumentParser(
    description="Verify log translation roundtrips losslessly.")
  parser.add_argument('input_file', type=pathlib.Path,
                      help='Input DB or Riegeli log file to test')
  import sys
  args = parser.parse_args(
    [arg for arg in sys.argv[1:] if not arg.startswith('--')])

  if args.input_file.suffix == '.db':
    verify_file_roundtrip(args.input_file, is_db=True)
  elif args.input_file.suffix == '.riegeli':
    verify_file_roundtrip(args.input_file, is_db=False)
  else:
    print("File must have .db or .riegeli extension.")


if __name__ == '__main__':
  import sys

  if len(sys.argv) <= 1 or sys.argv[1].startswith('-'):
    raise SystemExit(pytest.main(["-xvv", __file__]))
  main()
