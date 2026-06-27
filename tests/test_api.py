"""
Flask API route tests for truescrub.api.

Uses Flask's test client and a MockDBManager-populated database to test
the HTTP interface end-to-end.
"""
import datetime
import json

import pytest

from tests.db_test_utils import TestDBManager, create_game_state_for_round
from truescrub.api import app, parse_timezone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_db():
  """Create a populated database with 10 rounds."""
  db_manager = TestDBManager()

  ct_team = [(1, 'Player1'), (2, 'Player2')]
  t_team = [(3, 'Player3')]
  day = datetime.datetime(2022, 1, 15)

  game_states = []
  player_stats = {1: {'match_mvps': 0}, 2: {'match_mvps': 0},
                  3: {'match_mvps': 0}}

  for i in range(1, 11):
    round_stats = {
      1: {'kills': i % 3, 'assists': i % 2, 'deaths': 0,
          'damage': 50 + i * 10, 'survived': True,
          'match_mvps': player_stats[1]['match_mvps'],
          'mvp': i % 3 == 0},
      2: {'kills': i % 2, 'assists': i % 3, 'deaths': 0,
          'damage': 100 + i * 10, 'survived': True,
          'match_mvps': player_stats[2]['match_mvps'],
          'mvp': i % 3 == 1},
      3: {'kills': 0, 'assists': 0, 'deaths': 1,
          'damage': 20 + i * 5, 'survived': False,
          'match_mvps': player_stats[3]['match_mvps'],
          'mvp': i % 3 == 2},
    }
    for pid in player_stats:
      if round_stats[pid]['mvp']:
        player_stats[pid]['match_mvps'] += 1

    game_states.append(create_game_state_for_round(
      timestamp=day + datetime.timedelta(hours=i),
      map_name='de_dust2',
      ct_team=ct_team,
      t_team=t_team,
      winner='CT',
      player_stats=round_stats,
    ))

  db_manager.add_game_states(game_states)
  db_manager.process_game_states()
  yield db_manager.skill_db
  db_manager.close()


@pytest.fixture
def client(populated_db, monkeypatch):
  """Create a Flask test client with a pre-populated database."""
  app.config['TESTING'] = True

  # Monkeypatch get_skill_db so the before_request handler uses our test DB
  monkeypatch.setattr('truescrub.db.get_skill_db', lambda name=None: populated_db)

  with app.test_client() as client:
    yield client


# ---------------------------------------------------------------------------
# parse_timezone (unit)
# ---------------------------------------------------------------------------

class TestParseTimezone:
  def test_positive_offset(self):
    tz = parse_timezone('+05:00')
    assert tz.utcoffset(None) == datetime.timedelta(hours=5)

  def test_negative_offset(self):
    tz = parse_timezone('-05:00')
    assert tz.utcoffset(None) == datetime.timedelta(hours=-5)

  def test_zero_offset(self):
    tz = parse_timezone('+00:00')
    assert tz.utcoffset(None) == datetime.timedelta(0)

  def test_invalid_raises(self):
    with pytest.raises(ValueError):
      parse_timezone('invalid')

  def test_partial_offset_accepted(self):
    """strptime %z handles partial offsets correctly."""
    tz = parse_timezone('+05:30')
    assert tz.utcoffset(None) == datetime.timedelta(hours=5, minutes=30)


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

class TestLeaderboardApi:
  def test_season_leaderboard(self, client):
    resp = client.get('/api/leaderboard/season/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'players' in data
    assert len(data['players']) >= 1

    player = data['players'][0]
    assert 'player_id' in player
    assert 'steam_name' in player
    assert 'mmr' in player
    assert 'skill_group' in player


class TestLeaderboardPage:
  def test_default_leaderboard_renders(self, client):
    resp = client.get('/leaderboard')
    assert resp.status_code == 200
    assert b'Player1' in resp.data or b'Player2' in resp.data

  def test_season_leaderboard_renders(self, client):
    resp = client.get('/leaderboard/season/1')
    assert resp.status_code == 200


class TestGameStateEndpoint:
  def test_rejects_missing_auth(self, client):
    resp = client.post('/api/game_state',
                       data=json.dumps({'map': {'name': 'de_dust2'}}),
                       content_type='application/json')
    assert resp.status_code == 403

  def test_rejects_wrong_token(self, client):
    resp = client.post('/api/game_state',
                       data=json.dumps({
                         'auth': {'token': 'wrong_key'},
                         'map': {'name': 'de_dust2'},
                       }),
                       content_type='application/json')
    assert resp.status_code == 403


class TestSkillGroupsPage:
  def test_renders(self, client):
    resp = client.get('/skill_groups')
    assert resp.status_code == 200
    assert b'Cardboard' in resp.data


class TestIndexPage:
  def test_renders(self, client):
    resp = client.get('/')
    assert resp.status_code == 200


class TestMatchmakingPage:
  def test_matchmaking_no_season_renders(self, client):
    resp = client.get('/matchmaking/season/1')
    assert resp.status_code == 200


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
