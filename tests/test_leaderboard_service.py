import datetime
from unittest.mock import MagicMock

import pytest

from proto import leaderboard_service_pb2
from tests.db_test_utils import TestDBManager, create_game_state_for_round, \
  set_context_var
from truescrub.interceptors import grpc_db_conn
from truescrub.rpc import LeaderboardServiceServicer


@pytest.fixture
def populated_db():
  """Test DB with 2 seasons and 3 players who played 1 round in season 1."""
  db_manager = TestDBManager()

  ct_team = [(1, 'Player1'), (2, 'Player2')]
  t_team = [(3, 'Player3')]

  game_states = []

  day1 = datetime.datetime(2022, 1, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
  game_states.append(create_game_state_for_round(
    timestamp=day1, map_name='de_dust2', ct_team=ct_team, t_team=t_team,
    winner='CT',
    player_stats={1: {'kills': 1, 'assists': 0, 'deaths': 0, 'damage': 100,
                      'survived': True, 'match_mvps': 1, 'mvp': True},
                  2: {'kills': 0, 'assists': 1, 'deaths': 0, 'damage': 50,
                      'survived': True, 'match_mvps': 0, 'mvp': False},
                  3: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0,
                      'survived': False, 'match_mvps': 0, 'mvp': False}}
  ))

  db_manager.add_game_states(game_states)
  db_manager.process_game_states()
  yield db_manager.skill_db
  db_manager.close()


@pytest.fixture
def servicer(populated_db):
  with set_context_var(grpc_db_conn, populated_db):
    yield LeaderboardServiceServicer()


class TestGetLeaderboardAllSeasons:
  """GetLeaderboard with no season_id returns all players sorted by MMR."""

  def test_returns_all_players(self, servicer):
    request = leaderboard_service_pb2.GetLeaderboardRequest()
    context = MagicMock()

    response = servicer.GetLeaderboard(request, context)

    assert not context.abort.called
    player_ids = [p.player_id for p in response.leaderboard]
    assert len(player_ids) == 3
    assert set(player_ids) == {1, 2, 3}

  def test_sorted_by_mmr_descending(self, servicer):
    request = leaderboard_service_pb2.GetLeaderboardRequest()
    context = MagicMock()

    response = servicer.GetLeaderboard(request, context)

    mmrs = [p.skill.mmr for p in response.leaderboard]
    assert mmrs == sorted(mmrs, reverse=True)

  def test_players_have_skill_info(self, servicer):
    request = leaderboard_service_pb2.GetLeaderboardRequest()
    context = MagicMock()

    response = servicer.GetLeaderboard(request, context)

    for player in response.leaderboard:
      assert player.skill.skill_group != ''
      assert player.skill.mu > 0
      assert player.skill.sigma > 0
      assert player.steam_name != ''


class TestGetLeaderboardBySeason:
  """GetLeaderboard with a season_id returns only that season's players."""

  def test_returns_season_players(self, servicer):
    request = leaderboard_service_pb2.GetLeaderboardRequest(season_id=1)
    context = MagicMock()

    response = servicer.GetLeaderboard(request, context)

    assert not context.abort.called
    player_ids = {p.player_id for p in response.leaderboard}
    assert player_ids == {1, 2, 3}

  def test_empty_season_returns_empty(self, servicer):
    """Season 2 exists but has no rounds, so should return empty."""
    request = leaderboard_service_pb2.GetLeaderboardRequest(season_id=2)
    context = MagicMock()

    response = servicer.GetLeaderboard(request, context)

    assert not context.abort.called
    assert len(response.leaderboard) == 0


class TestGetLeaderboardSeasonIdZero:
  """season_id=0 (proto3 default) should behave like no season_id."""

  def test_season_id_zero_returns_all(self, servicer):
    request = leaderboard_service_pb2.GetLeaderboardRequest(season_id=0)
    context = MagicMock()

    response = servicer.GetLeaderboard(request, context)

    assert not context.abort.called
    player_ids = {p.player_id for p in response.leaderboard}
    assert player_ids == {1, 2, 3}
