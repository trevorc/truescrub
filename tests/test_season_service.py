from unittest.mock import MagicMock

import pytest

from proto import season_service_pb2
from tests.db_test_utils import set_context_var
from truescrub import db
from truescrub.interceptors import grpc_db_conn
from truescrub.rpc import SeasonServiceServicer


def test_get_available_seasons(monkeypatch):
  mock_get_season_range = MagicMock(return_value=[1, 2, 3])
  monkeypatch.setattr(db, "get_season_range", mock_get_season_range)
  monkeypatch.setattr(db, "get_skill_db", MagicMock())

  servicer = SeasonServiceServicer()
  request = season_service_pb2.GetAvailableSeasonsRequest()

  with set_context_var(grpc_db_conn, MagicMock()):
    response = servicer.GetAvailableSeasons(request, None)
    assert list(response.available_seasons) == [1, 2, 3]
