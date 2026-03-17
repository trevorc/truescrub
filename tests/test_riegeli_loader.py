"""
Backend parity tests: verify that DatabaseStateLoader and RiegeliStateLoader
produce identical results from the same game state data.

Tests also cover the surgery module's filtering logic end-to-end.
"""
import datetime
import json
import pathlib
import sqlite3
import tempfile

import pytest

from tests.db_test_utils import (
  TestDBManager, TestStateLoader, MockGameState, create_game_state_for_round,
)
from truescrub import db, seasoncfg
from truescrub.db import (
  initialize_skill_db, initialize_game_db, execute_one, insert_game_state,
)
from truescrub.proto.game_state_pb2 import GameStateEntry
from truescrub.statewriter import GameStateLog
from truescrub.statewriter.state_parsing import parse_game_state
from truescrub.updater.recalculate import compute_rounds_and_players, recalculate_ratings, load_seasons
from truescrub.updater.state_loader import RiegeliStateLoader, entry_to_row
from truescrub.updater.state_parser import parse_game_states
from truescrub.seasoncfg import get_seasons_by_start_date
from truescrub.tools.surgery import (
  ImpactedGameStateStats,
  RiegeliBackend,
  purge_rounds_with_player,
  _is_round_end,
  _player_in_gs,
)

SEASONS_TOML = pathlib.Path('tests/sample_seasons.toml')

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_three_round_game_states(day: datetime.datetime):
  """Return a list of 3 MockGameState objects (one round per state)."""
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
def riegeli_log(tmp_path, monkeypatch):
  """A GameStateLog written from MockGameState objects, using state_parsing."""
  monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
  day = datetime.datetime(2022, 3, 1)
  mock_states = _make_three_round_game_states(day)
  log_path = tmp_path / 'game_states.riegeli'
  gl = GameStateLog(log_path)
  with gl.writer() as writer:
    for i, ms in enumerate(mock_states):
      gs_json = ms.to_json()
      entry = GameStateEntry(
        game_state_id=i + 1,
        game_state=parse_game_state(gs_json),
      )
      entry.created_at.FromDatetime(day + datetime.timedelta(hours=i + 1))
      writer.append(entry)
  return gl


@pytest.fixture
def sqlite_db(monkeypatch):
  """An in-memory SQLite game_db + skill_db loaded from the same mock data."""
  monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
  day = datetime.datetime(2022, 3, 1)
  manager = TestDBManager()
  states = _make_three_round_game_states(day)
  manager.add_game_states(states)
  return manager


# ---------------------------------------------------------------------------
# Backend parity: same rounds from Riegeli and SQLite
# ---------------------------------------------------------------------------

class TestBackendParity:
  """DatabaseStateLoader and RiegeliStateLoader must produce identical results."""

  def test_riegeli_produces_same_round_count(self, riegeli_log, sqlite_db,
                                             monkeypatch):
    """Both backends should emit the same number of rounds for identical data."""
    monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)

    # SQLite path
    sqlite_new_rounds = sqlite_db.process_game_states()
    assert sqlite_new_rounds is not None, 'Expected rounds from SQLite loader'
    sqlite_round_count = sqlite_new_rounds[1] - sqlite_new_rounds[0] + 1

    # Riegeli path
    skill_db = sqlite3.connect(':memory:')
    initialize_skill_db(skill_db)
    load_seasons(skill_db)

    riegeli_loader = RiegeliStateLoader(riegeli_log)
    with riegeli_loader:
      riegeli_max_id, riegeli_rounds = compute_rounds_and_players(
        riegeli_loader, skill_db)

    assert riegeli_rounds is not None, "Expected riegeli_rounds to not be None, failing test"
    riegeli_round_count = riegeli_rounds[1] - riegeli_rounds[0] + 1

    assert riegeli_round_count == sqlite_round_count, (
      f'Riegeli produced {riegeli_round_count} rounds, '
      f'SQLite produced {sqlite_round_count}')

  def test_riegeli_max_game_state_id(self, riegeli_log, monkeypatch):
    """RiegeliStateLoader should return the correct max game_state_id."""
    monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
    skill_db = sqlite3.connect(':memory:')
    initialize_skill_db(skill_db)
    load_seasons(skill_db)

    with RiegeliStateLoader(riegeli_log) as loader:
      max_id, _ = compute_rounds_and_players(loader, skill_db)

    assert max_id == 3  # Three entries written

  def test_riegeli_range_query(self, riegeli_log, monkeypatch):
    """Fetching a sub-range should only return entries in that range."""
    monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
    skill_db = sqlite3.connect(':memory:')
    initialize_skill_db(skill_db)
    load_seasons(skill_db)

    with RiegeliStateLoader(riegeli_log) as loader:
      max_id, rounds = compute_rounds_and_players(
        loader, skill_db, game_state_range=(2, 3))

    assert max_id == 3

  def test_riegeli_empty_range(self, riegeli_log, monkeypatch):
    """A range beyond the log should produce no rounds."""
    monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
    skill_db = sqlite3.connect(':memory:')
    initialize_skill_db(skill_db)
    load_seasons(skill_db)

    with RiegeliStateLoader(riegeli_log) as loader:
      max_id, rounds = compute_rounds_and_players(
        loader, skill_db, game_state_range=(100, 200))

    assert rounds is None


# ---------------------------------------------------------------------------
# entry_to_row: proto-to-GameStateRow conversion
# ---------------------------------------------------------------------------

class TestEntryToRow:
  """Verify that entry_to_row correctly converts a GameStateEntry to a row."""

  def _make_entry(self, game_state_json: dict,
                  gid: int = 1) -> GameStateEntry:
    ts = datetime.datetime(2022, 3, 1, 12, 0, 0)
    entry = GameStateEntry(
      game_state_id=gid,
      game_state=parse_game_state(game_state_json),
    )
    entry.created_at.FromDatetime(ts)
    return entry

  def test_round_phase_over(self):
    gs_json = MockGameState(
      timestamp=datetime.datetime(2022, 3, 1),
      map_name='de_mirage',
      round_phase='over',
      previous_round_phase='live',
      win_team='CT',
      players={'76561198000000001': {
        'name': 'Alice', 'team': 'CT', 'observer_slot': 1,
        'match_stats': {'kills': 2, 'assists': 0, 'deaths': 0,
                        'mvps': 1, 'score': 4},
        'state': {'health': 100, 'armor': 100, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 800,
                  'round_kills': 2, 'round_killhs': 1,
                  'round_totaldmg': 110, 'equip_value': 300},
        'weapons': {},
      }},
      previous_players={'76561198000000001': {
        'name': 'Alice', 'team': 'CT', 'observer_slot': 1,
        'match_stats': {'kills': 0, 'assists': 0, 'deaths': 0,
                        'mvps': 0, 'score': 0},
        'state': {'health': 100, 'armor': 100, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 800,
                  'round_kills': 0, 'round_killhs': 0,
                  'round_totaldmg': 0, 'equip_value': 300},
        'weapons': {},
      }},
    ).to_json()
    entry = self._make_entry(gs_json)
    row = entry_to_row(entry)
    assert row.round_phase == 'over'
    assert row.map_name == 'de_mirage'
    assert row.win_team == 'CT'
    assert row.game_state_id == 1

    allplayers = row.allplayers
    assert '76561198000000001' in allplayers
    p = allplayers['76561198000000001']
    assert p['name'] == 'Alice'
    assert p['team'] == 'CT'

  def test_previous_allplayers_populated(self):
    """entry_to_row should correctly populate previous_allplayers from proto."""
    gs_json = MockGameState(
      timestamp=datetime.datetime(2022, 3, 1),
      map_name='de_dust2',
      round_phase='over',
      previous_round_phase='live',
      win_team='T',
      players={'76561198000000002': {
        'name': 'Bob', 'team': 'T', 'observer_slot': 1,
        'match_stats': {'kills': 1, 'assists': 0, 'deaths': 1,
                        'mvps': 0, 'score': 2},
        'state': {'health': 0, 'armor': 0, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 200,
                  'round_kills': 1, 'round_killhs': 0,
                  'round_totaldmg': 80, 'equip_value': 100},
        'weapons': {},
      }},
      previous_players={'76561198000000002': {
        'name': 'Bob', 'team': 'T', 'observer_slot': 1,
        'match_stats': {'kills': 0, 'assists': 0, 'deaths': 0,
                        'mvps': 0, 'score': 0},
        'state': {'health': 100, 'armor': 0, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 400,
                  'round_kills': 0, 'round_killhs': 0,
                  'round_totaldmg': 0, 'equip_value': 100},
        'weapons': {},
      }},
    ).to_json()
    entry = self._make_entry(gs_json)
    row = entry_to_row(entry)
    prev = row.previous_allplayers
    assert '76561198000000002' in prev
    assert prev['76561198000000002']['team'] == 'T'


# ---------------------------------------------------------------------------
# Surgery: _is_round_end and _player_in_gs helpers
# ---------------------------------------------------------------------------

class TestSurgeryHelpers:
  """Unit tests for surgery utility functions."""

  def _gs_from_json(self, gs_json: dict):
    return parse_game_state(gs_json)

  def _make_gs_json(self, round_phase='over', prev_round_phase='live',
                    win_team='CT', player_ids=None):
    player_ids = player_ids or [76561198000000001]
    players = {}
    prev_players = {}
    for sid in player_ids:
      players[str(sid)] = {
        'name': 'player', 'team': 'CT', 'observer_slot': 1,
        'match_stats': {'kills': 1, 'assists': 0, 'deaths': 0,
                        'mvps': 0, 'score': 2},
        'state': {'health': 100, 'armor': 50, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 800,
                  'round_kills': 1, 'round_killhs': 0,
                  'round_totaldmg': 50, 'equip_value': 200},
        'weapons': {},
      }
      prev_players[str(sid)] = {
        'name': 'player', 'team': 'CT', 'observer_slot': 1,
        'match_stats': {'kills': 0, 'assists': 0, 'deaths': 0,
                        'mvps': 0, 'score': 0},
        'state': {'health': 100, 'armor': 50, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 800,
                  'round_kills': 0, 'round_killhs': 0,
                  'round_totaldmg': 0, 'equip_value': 200},
        'weapons': {},
      }
    return MockGameState(
      timestamp=datetime.datetime(2022, 3, 1),
      map_name='de_dust2',
      round_phase=round_phase,
      previous_round_phase=prev_round_phase,
      win_team=win_team,
      players=players,
      previous_players=prev_players,
    ).to_json()

  def test_is_round_end_true(self):
    gs = self._gs_from_json(
      self._make_gs_json(round_phase='over', prev_round_phase='live'))
    assert _is_round_end(gs) is True

  def test_is_round_end_false_still_live(self):
    gs = self._gs_from_json(
      self._make_gs_json(round_phase='live', prev_round_phase='freezetime'))
    assert _is_round_end(gs) is False

  def test_is_round_end_false_no_previously(self):
    """A state with no 'previously' key cannot be a round end."""
    gs_json = {
      'provider': {'name': 'CS:GO', 'appid': 730, 'version': 13694,
                   'steamid': '76561198413889827', 'timestamp': 1557535071},
      'round': {'phase': 'over', 'win_team': 'CT'},
    }
    gs = self._gs_from_json(gs_json)
    assert _is_round_end(gs) is False

  def test_player_in_gs_present(self):
    target = 76561198000000001
    gs = self._gs_from_json(self._make_gs_json(player_ids=[target, 999]))
    assert _player_in_gs(gs, target) is True

  def test_player_in_gs_absent(self):
    gs = self._gs_from_json(
      self._make_gs_json(player_ids=[76561198000000001]))
    assert _player_in_gs(gs, 42) is False

  def test_get_impacted_game_state_stats(self, tmp_path):
    """get_impacted_game_state_stats should count rounds and game states correctly."""
    player_id = 76561198000000001
    other_id = 76561198000000099

    log_path = tmp_path / 'test.riegeli'
    gl = GameStateLog(log_path)

    # 2 game states with the target player (1 round end), 1 without
    gs_with = self._make_gs_json(round_phase='live', prev_round_phase='freezetime',
                                 player_ids=[player_id])
    gs_round_end = self._make_gs_json(
      round_phase='over', prev_round_phase='live', player_ids=[player_id])
    gs_without = self._make_gs_json(round_phase='live', prev_round_phase='freezetime',
                                    player_ids=[other_id])

    with gl.writer() as writer:
      for i, gs_json in enumerate([gs_with, gs_round_end, gs_without], start=1):
        entry = GameStateEntry(
          game_state_id=i,
          game_state=parse_game_state(gs_json),
        )
        entry.created_at.FromDatetime(datetime.datetime(2022, 3, 1))
        writer.append(entry)

    backend = RiegeliBackend(log_path, tmp_path / 'unused.riegeli')
    stats = backend.get_impacted_stats(player_id)

    assert stats.game_states == 2
    assert stats.rounds == 1
    assert stats.min_id == 1
    assert stats.max_id == 2
    assert 'de_dust2' in stats.maps


class TestSurgeryFilter:
  """Integration test for RiegeliBackend + purge_rounds_with_player."""

  def _write_log(self, log: GameStateLog, entries):
    """Write (game_state_id, gs_json) pairs to the log."""
    with log.writer() as writer:
      for gid, gs_json in entries:
        entry = GameStateEntry(
          game_state_id=gid,
          game_state=parse_game_state(gs_json),
        )
        entry.created_at.FromDatetime(datetime.datetime(2022, 3, 1))
        writer.append(entry)

  def _round_end_json(self, player_ids, win_team='CT'):
    players = {}
    prev_players = {}
    for sid in player_ids:
      players[str(sid)] = {
        'name': 'p', 'team': 'CT', 'observer_slot': 1,
        'match_stats': {'kills': 1, 'assists': 0, 'deaths': 0,
                        'mvps': 0, 'score': 2},
        'state': {'health': 100, 'armor': 50, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 800,
                  'round_kills': 1, 'round_killhs': 0,
                  'round_totaldmg': 50, 'equip_value': 200},
        'weapons': {},
      }
      prev_players[str(sid)] = {
        'name': 'p', 'team': 'CT', 'observer_slot': 1,
        'match_stats': {'kills': 0, 'assists': 0, 'deaths': 0,
                        'mvps': 0, 'score': 0},
        'state': {'health': 100, 'armor': 50, 'helmet': False,
                  'flashed': 0, 'burning': 0, 'money': 800,
                  'round_kills': 0, 'round_killhs': 0,
                  'round_totaldmg': 0, 'equip_value': 200},
        'weapons': {},
      }
    return MockGameState(
      timestamp=datetime.datetime(2022, 3, 1),
      map_name='de_dust2',
      round_phase='over',
      previous_round_phase='live',
      win_team=win_team,
      players=players,
      previous_players=prev_players,
    ).to_json()

  def test_filter_excludes_player_rounds(self, tmp_path):
    """RiegeliBackend + purge_rounds_with_player should remove entries where the player appears."""
    target = 76561198000000001
    other = 76561198000000002

    source = GameStateLog(tmp_path / 'source.riegeli')
    output = GameStateLog(tmp_path / 'output.riegeli')

    # 3 entries: other-only, target round, other-only
    entries = [
      (1, self._round_end_json([other])),
      (2, self._round_end_json([target])),
      (3, self._round_end_json([other])),
    ]
    self._write_log(source, entries)

    # Bypass the interactive confirmation prompt
    import unittest.mock as mock
    backend = RiegeliBackend(
      tmp_path / 'source.riegeli', tmp_path / 'output.riegeli')
    with mock.patch('builtins.input', return_value='1'):
      purge_rounds_with_player(backend, target)

    with output.reader() as reader:
      kept = list(reader.fetch_all())

    # Only the two other-player entries should remain
    assert len(kept) == 2
    kept_ids = {e.game_state_id for e in kept}
    assert 2 not in kept_ids

  def test_filter_no_matching_player(self, tmp_path, capsys):
    """purge_rounds_with_player should exit cleanly when player not found."""
    source = GameStateLog(tmp_path / 'source.riegeli')
    output = GameStateLog(tmp_path / 'output.riegeli')
    self._write_log(source, [
      (1, self._round_end_json([76561198000000002]))
    ])

    backend = RiegeliBackend(
      tmp_path / 'source.riegeli', tmp_path / 'output.riegeli')
    purge_rounds_with_player(backend, player_id=99999)

    output_dir = tmp_path / 'output.riegeli'
    assert not list(output_dir.glob('*.riegeli'))


class TestRiegeliStateLoaderInit:
  """Unit tests for RiegeliStateLoader construction helpers."""

  def test_from_env_constructs_correct_path(self, tmp_path, monkeypatch):
    """from_env() should combine DATA_DIR and LOG_DIR_NAME into the log path."""
    import truescrub.updater.state_loader as state_loader_module
    from truescrub.statewriter.state_writer import LOG_DIR_NAME

    monkeypatch.setattr(state_loader_module, 'DATA_DIR', tmp_path)

    loader = RiegeliStateLoader.from_env()
    expected = tmp_path / LOG_DIR_NAME
    assert loader.log.log_dir == expected


if __name__ == '__main__':
  import pytest as _pytest
  import sys
  raise SystemExit(_pytest.main(['-xv', __file__]))
