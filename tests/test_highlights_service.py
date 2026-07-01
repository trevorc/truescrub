import datetime
from unittest.mock import MagicMock

import pytest

import grpc
from proto import common_pb2
from proto import highlights_service_pb2
from tests.db_test_utils import TestDBManager, create_game_state_for_round, set_context_var
from truescrub.rpc import HighlightsServiceServicer
from truescrub.interceptors import grpc_db_conn


@pytest.fixture
def populated_db():
  db_manager = TestDBManager()

  ct_team = [(1, 'Player1'), (2, 'Player2')]
  t_team = [(3, 'Player3')]

  game_states = []

  # Day 1: 2022-01-15 (UTC)
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

  # Day 2: 2022-01-16 (UTC)
  day2 = datetime.datetime(2022, 1, 16, 12, 0, 0, tzinfo=datetime.timezone.utc)
  game_states.append(create_game_state_for_round(
    timestamp=day2, map_name='de_inferno', ct_team=ct_team, t_team=t_team,
    winner='T',
    player_stats={
      1: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0, 'survived': False,
          'match_mvps': 1, 'mvp': False},
      2: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0, 'survived': False,
          'match_mvps': 0, 'mvp': False},
      3: {'kills': 2, 'assists': 0, 'deaths': 0, 'damage': 200,
          'survived': True, 'match_mvps': 1, 'mvp': True}}
  ))

  # Day 3: 2022-01-17 (UTC)
  day3 = datetime.datetime(2022, 1, 17, 2, 0, 0, tzinfo=datetime.timezone.utc)
  game_states.append(create_game_state_for_round(
    timestamp=day3, map_name='de_mirage', ct_team=ct_team, t_team=t_team,
    winner='CT',
    player_stats={1: {'kills': 1, 'assists': 0, 'deaths': 0, 'damage': 100,
                      'survived': True, 'match_mvps': 2, 'mvp': True},
                  2: {'kills': 0, 'assists': 1, 'deaths': 0, 'damage': 50,
                      'survived': True, 'match_mvps': 0, 'mvp': False},
                  3: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0,
                      'survived': False, 'match_mvps': 1, 'mvp': False}}
  ))

  db_manager.add_game_states(game_states)
  db_manager.process_game_states()
  yield db_manager.skill_db
  db_manager.close()


@pytest.fixture
def servicer(populated_db, monkeypatch):
  with set_context_var(grpc_db_conn, populated_db):
      yield HighlightsServiceServicer()


def test_list_match_days_utc(servicer):
  request = highlights_service_pb2.ListMatchDaysRequest(timezone="+00:00")
  context = MagicMock()

  response = servicer.ListMatchDays(request, context)

  assert not context.abort.called
  assert len(response.match_days) == 3

  days = [(d.year, d.month, d.day) for d in response.match_days]
  assert days == [(2022, 1, 17), (2022, 1, 16), (2022, 1, 15)]


def test_list_match_days_offset_timezone(servicer):
  # -05:00 timezone.
  # Day 3 is 2022-01-17 02:00 UTC, which is 2022-01-16 21:00 in -05:00.
  # So Day 3 groups into 2022-01-16!
  request = highlights_service_pb2.ListMatchDaysRequest(timezone="-05:00")
  context = MagicMock()

  response = servicer.ListMatchDays(request, context)

  assert not context.abort.called
  assert len(response.match_days) == 2

  days = [(d.year, d.month, d.day) for d in response.match_days]
  assert days == [(2022, 1, 16), (2022, 1, 15)]


def test_list_match_days_invalid_timezone(servicer):
  request = highlights_service_pb2.ListMatchDaysRequest(timezone="invalid")
  context = MagicMock()

  servicer.ListMatchDays(request, context)

  context.abort.assert_called_once_with(
    grpc.StatusCode.INVALID_ARGUMENT, "Invalid timezone invalid"
  )
