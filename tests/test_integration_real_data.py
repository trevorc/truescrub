"""
Integration test using pseudonymized real game data.

Feeds 18 round‑ending game states through the /api/game_state "front door",
synchronously drives the GameStateWriter → Updater pipeline, and asserts
the REST API returns correct leaderboard and highlights responses.
"""
import datetime
import json
import pathlib
import sqlite3
from unittest.mock import MagicMock

import pytest

from google.protobuf.field_mask_pb2 import FieldMask
from proto import common_pb2
from proto import highlights_service_pb2
from truescrub import db, seasoncfg
from truescrub.api import app
from truescrub.envconfig import SHARED_KEY
from truescrub.interceptors import grpc_db_conn
from truescrub.rpc import HighlightsServiceServicer
from truescrub.statewriter.state_writer import GameStateWriter
from tests.db_test_utils import set_context_var
from truescrub.updater.recalculate import (
  compute_rounds_and_players, recalculate_ratings, load_seasons,
)
from truescrub.updater.state_loader import DatabaseStateLoader

FIXTURE_PATH = pathlib.Path(__file__).parent / 'real_game_states_fixture.json'
SEASONS_TOML = pathlib.Path(__file__).parent / 'sample_seasons.toml'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def integration_env(monkeypatch):
  """Stand up in‑memory game + skill DBs, wire up GameStateWriter/Updater,
  and yield a Flask test client that routes through the real pipeline."""

  game_db = sqlite3.connect(':memory:')
  skill_db = sqlite3.connect(':memory:')
  db.initialize_game_db(game_db)
  db.initialize_skill_db(skill_db)

  monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', SEASONS_TOML)
  load_seasons(skill_db)
  skill_db.commit()

  # The Flask teardown handler calls g.conn.close() after every request,
  # which would destroy our shared in‑memory connection.  Return a thin
  # wrapper whose close() is a no‑op.
  class _NonClosingProxy:
    """Delegates everything to the real connection but ignores close()."""

    def __init__(self, conn):
      self._conn = conn

    def close(self):
      pass  # keep the real connection alive

    def __getattr__(self, name):
      return getattr(self._conn, name)

    def __enter__(self):
      self._conn.__enter__()
      return self

    def __exit__(self, exc_type, exc_val, exc_tb):
      return self._conn.__exit__(exc_type, exc_val, exc_tb)

  skill_proxy = _NonClosingProxy(skill_db)

  monkeypatch.setattr('truescrub.db.get_game_db', lambda: game_db)
  monkeypatch.setattr('truescrub.db.get_skill_db',
                      lambda name=None: skill_proxy)

  # Build a real (but synchronous) GameStateWriter.
  # The updater is handled explicitly after posting, so we use a stub that
  # just records the messages the writer sends.
  class _MessageSink:
    """Lightweight sink that collects messages instead of enqueueing them."""

    def __init__(self):
      self.messages = []

    def send_message(self, **msg):
      self.messages.append(msg)

  sink = _MessageSink()
  writer = GameStateWriter(updater=sink)
  app.state_writer = writer
  app.config['TESTING'] = True

  with app.test_client() as client:
    yield client, game_db, skill_db, writer, sink

  game_db.close()
  skill_db.close()


@pytest.fixture()
def real_game_states():
  """Load the baked‑in pseudonymized fixture."""
  with open(FIXTURE_PATH) as f:
    return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_game_states(client, game_states):
  """POST each game state to the front‑door endpoint."""
  for gs in game_states:
    payload = {**gs, 'auth': {'token': SHARED_KEY}}
    resp = client.post(
      '/api/game_state',
      data=json.dumps(payload),
      content_type='application/json',
    )
    assert resp.status_code == 200, (
      f'game_state POST failed: {resp.status_code} {resp.data}')


def _drain_writer(writer):
  """Synchronously drain the writer's message queue.

  Sends the QUEUE_DONE sentinel then runs the queue loop, which calls
  process_messages() for all enqueued game states.  This inserts them
  into the game DB and sends updater messages to the sink.
  """
  writer.stop()
  writer.run()


def _run_updater(skill_db, sink):
  """Synchronously drive the updater logic using the messages recorded
  by the writer's sink."""
  game_state_ids = [m['game_state_id'] for m in sink.messages]
  if not game_state_ids:
    return
  max_processed = db.get_game_state_progress(skill_db)
  new_max = max(game_state_ids)
  game_state_range = (max_processed + 1, new_max)

  loader = DatabaseStateLoader()
  with loader as state_loader:
    _, new_rounds = compute_rounds_and_players(
      state_loader, skill_db, game_state_range)
    assert new_rounds is not None, "Expected new_rounds to not be None, failing test"
    recalculate_ratings(skill_db, new_rounds)
    db.save_game_state_progress(skill_db, new_max)
    skill_db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRealDataPipeline:
  """End‑to‑end: POST real game states → process → query REST APIs."""

  def test_leaderboard_populated_after_ingestion(
      self, integration_env, real_game_states):
    client, game_db, skill_db, writer, sink = integration_env

    # 1. Feed every state through the front door.
    _post_game_states(client, real_game_states)

    # 2. Drain the writer queue — this calls process_messages() which
    #    inserts game states into the game DB and sends updater messages.
    _drain_writer(writer)

    # 3. Drive the updater to compute skills.
    _run_updater(skill_db, sink)

    # 3. Query the leaderboard API.
    resp = client.get('/api/leaderboard/season/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'players' in data
    players = data['players']
    assert len(players) >= 2, (
      f'Expected at least 2 players, got {len(players)}')

    # Every player record should have the expected shape.
    for p in players:
      assert 'player_id' in p
      assert 'steam_name' in p
      assert 'mmr' in p
      assert 'skill_group' in p

    # Confirm that pseudonymized names appear.
    names = {p['steam_name'] for p in players}
    assert len(names & {'Alpha', 'Bravo', 'Charlie', 'Delta',
                        'Echo', 'Foxtrot'}) >= 2

  def test_leaderboard_page_renders(
      self, integration_env, real_game_states):
    client, game_db, skill_db, writer, sink = integration_env
    _post_game_states(client, real_game_states)
    _drain_writer(writer)
    _run_updater(skill_db, sink)

    resp = client.get('/leaderboard/season/1')
    assert resp.status_code == 200
    # At least one pseudonymized name should appear in the HTML.
    assert any(name.encode() in resp.data
               for name in ('Alpha', 'Bravo', 'Charlie',
                            'Delta', 'Echo', 'Foxtrot'))

  def test_highlights_returns_player_ratings(
      self, integration_env, real_game_states):
    client, game_db, skill_db, writer, sink = integration_env
    _post_game_states(client, real_game_states)
    _drain_writer(writer)
    _run_updater(skill_db, sink)

    ts = real_game_states[0]['provider']['timestamp']
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)

    servicer = HighlightsServiceServicer()
    req = highlights_service_pb2.GetDailyHighlightsRequest(
      date=common_pb2.Date(year=dt.year, month=dt.month, day=dt.day),
      timezone="+00:00"
    )
    context = MagicMock()
    with set_context_var(grpc_db_conn, skill_db):
        resp = servicer.GetDailyHighlights(req, context)

    assert not context.abort.called
    assert resp.rounds_played >= 1
    assert len(resp.players) >= 1

  def test_highlights_returns_accolades(
      self, integration_env, real_game_states):
    client, game_db, skill_db, writer, sink = integration_env
    _post_game_states(client, real_game_states)
    _drain_writer(writer)
    _run_updater(skill_db, sink)

    ts = real_game_states[0]['provider']['timestamp']
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)

    servicer = HighlightsServiceServicer()
    req = highlights_service_pb2.GetDailyHighlightsRequest(
      date=common_pb2.Date(
        year=dt.year, month=dt.month, day=dt.day),
      timezone="+00:00",
      read_mask=FieldMask(paths=['players.accolades'])
    )
    context = MagicMock()
    
    with set_context_var(grpc_db_conn, skill_db):
        resp = servicer.GetDailyHighlights(req, context)

    assert not context.abort.called

    all_accolades = []
    for player in resp.players:
      all_accolades.extend(player.accolades)

    assert len(all_accolades) >= 1

    first_accolade = all_accolades[0]
    assert first_accolade.name != ""

    accolade_names = {acc.name for acc in all_accolades}
    assert 'Grand Slamma Jamma' in accolade_names
    assert 'Bench Warmer' in accolade_names
    assert 'Cannon Fodder' in accolade_names
    assert 'Wallflower' in accolade_names

  def test_skill_groups_page_renders(
      self, integration_env, real_game_states):
    client, game_db, skill_db, writer, sink = integration_env
    _post_game_states(client, real_game_states)
    _drain_writer(writer)
    _run_updater(skill_db, sink)

    resp = client.get('/skill_groups')
    assert resp.status_code == 200
    assert b'Cardboard' in resp.data


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
