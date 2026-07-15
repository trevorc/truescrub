import datetime
from unittest.mock import MagicMock
import pytest

from proto import profile_service_pb2
from tests.db_test_utils import TestDBManager, create_game_state_for_round, \
  set_context_var
from truescrub.interceptors import grpc_db_conn
from truescrub.rpc import ProfileServiceServicer
from truescrub.db import get_players_in_last_round


@pytest.fixture
def populated_db():
  manager = TestDBManager()
  PLAYER_1 = 76561198000000001

  # Round 1: Team [1, 2] vs [3, 4] -> Winner: CT [1, 2]
  round1 = create_game_state_for_round(
    timestamp=datetime.datetime(2023, 1, 1, 12, 0, 0,
                                tzinfo=datetime.timezone.utc),
    map_name="de_dust2",
    ct_team=[(PLAYER_1, "Player1"), (2, "Player2")],
    t_team=[(3, "Player3"), (4, "Player4")],
    winner="CT",
    player_stats={
      PLAYER_1: {"kills": 2, "assists": 1, "deaths": 0, "damage": 300,
                 "survived": True, "mvp": True}
    }
  )

  # Round 2: Team [1, 2] vs [3, 4] -> Winner: T [3, 4]
  round2 = create_game_state_for_round(
    timestamp=datetime.datetime(2023, 1, 1, 12, 5, 0,
                                tzinfo=datetime.timezone.utc),
    map_name="de_dust2",
    ct_team=[(PLAYER_1, "Player1"), (2, "Player2")],
    t_team=[(3, "Player3"), (4, "Player4")],
    winner="T",
    player_stats={
      PLAYER_1: {"kills": 0, "assists": 0, "deaths": 1, "damage": 50,
                 "survived": False, "mvp": False}
    }
  )

  # Round 3: Team [1, 3] vs [2, 4] -> Winner: CT [1, 3]
  round3 = create_game_state_for_round(
    timestamp=datetime.datetime(2023, 1, 1, 12, 10, 0,
                                tzinfo=datetime.timezone.utc),
    map_name="de_inferno",
    ct_team=[(PLAYER_1, "Player1"), (3, "Player3")],
    t_team=[(2, "Player2"), (4, "Player4")],
    winner="CT",
    player_stats={
      PLAYER_1: {"kills": 1, "assists": 0, "deaths": 0, "damage": 100,
                 "survived": True, "mvp": False}
    }
  )

  manager.add_game_states([round1, round2, round3])
  manager.process_game_states()

  yield manager.skill_db, PLAYER_1
  manager.close()


@pytest.fixture
def servicer(populated_db):
  skill_db, player_id = populated_db
  with set_context_var(grpc_db_conn, skill_db):
    yield ProfileServiceServicer(), player_id


class TestProfileEndpoints:
  def test_get_profile_overall_records(self, servicer):
    profile_servicer, player_id = servicer
    request = profile_service_pb2.GetProfileRequest(player_id=player_id)
    context = MagicMock()

    response = profile_servicer.GetProfile(request, context)
    assert not context.abort.called

    # Player 1 won 2 rounds, lost 1 round
    assert response.rounds_won == 2
    assert response.rounds_lost == 1

  def test_get_player_team_records(self, servicer):
    profile_servicer, player_id = servicer
    request = profile_service_pb2.GetPlayerTeamRecordsRequest(
      player_id=player_id)
    context = MagicMock()

    response = profile_servicer.GetPlayerTeamRecords(request, context)
    assert not context.abort.called

    # Player 1 played on two distinct teams: [Player1, Player2] and [Player1, Player3]
    assert len(response.team_records) == 2
    team_1_2 = next(
      t for t in response.team_records if "Player2" in t.team_members)
    team_1_3 = next(
      t for t in response.team_records if "Player3" in t.team_members)

    assert team_1_2.rounds_won == 1
    assert team_1_2.rounds_lost == 1
    assert team_1_3.rounds_won == 1
    assert team_1_3.rounds_lost == 0

  def test_get_player_rounds(self, servicer):
    profile_servicer, player_id = servicer
    request = profile_service_pb2.GetPlayerRoundsRequest(player_id=player_id)
    context = MagicMock()

    response = profile_servicer.GetPlayerRounds(request, context)
    assert not context.abort.called

    # Should return 3 rounds total, ordered descending by date
    assert len(response.rounds) == 3
    # Most recent round (Round 3) won by Player1 and Player3
    assert set(response.rounds[0].winning_team_names) == {"Player1", "Player3"}
    assert set(response.rounds[0].losing_team_names) == {"Player2", "Player4"}

  def test_get_players_in_last_round(self, populated_db):
    skill_db, _ = populated_db
    # Tests the matchmaking dependency function
    last_round_players = get_players_in_last_round(skill_db)

    assert last_round_players == {76561198000000001, 2, 3, 4}
