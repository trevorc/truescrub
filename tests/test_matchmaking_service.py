import datetime
from unittest.mock import MagicMock

import pytest

import grpc
from proto import common_pb2
from proto import matchmaking_service_pb2
from tests.db_test_utils import TestDBManager, create_game_state_for_round, \
  set_context_var
from truescrub.interceptors import grpc_db_conn
from truescrub.rpc import MatchmakingServiceServicer


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
def servicer(populated_db, monkeypatch):
  with set_context_var(grpc_db_conn, populated_db):
    yield MatchmakingServiceServicer()


class TestRoundSelectionWithSeason:
  """Explicit season + round_selection: use season players, select from
  last round. Equivalent to /matchmaking/latest with a specific season."""

  def test_returns_season_players_and_matches(self, servicer):
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      season_id=1,
      round_selection=matchmaking_service_pb2.RoundSelection()
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    player_ids = {p.player_id for p in response.available_players}
    assert player_ids == {1, 2, 3}
    assert len(response.proposed_matches) > 0

    player_1 = next(
      p for p in response.available_players if p.player_id == 1)
    assert player_1.skill.skill_group != ''


class TestRoundSelectionDefaultsToLatestSeason:
  """round_selection with no season_id defaults to the latest season.
  This is the /matchmaking/latest behavior: the client doesn't need to
  know which season is latest — the server resolves it."""

  def test_defaults_to_latest_season(self, servicer):
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      round_selection=matchmaking_service_pb2.RoundSelection()
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    # Server defaulted to the latest season; the 3 players who played
    # in season 1 are in the pool.  Season 2 has no rounds so its pool
    # is empty — if the server picked season 2 this would be empty.
    player_ids = {p.player_id for p in response.available_players}
    assert player_ids == {1, 2, 3}
    assert len(response.proposed_matches) > 0

  def test_season_id_zero_defaults_to_latest(self, servicer):
    """Proto3 default int32 is 0.  season_id=0 is not a valid season,
    so round_selection should still default to the latest season."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      season_id=0,
      round_selection=matchmaking_service_pb2.RoundSelection()
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    player_ids = {p.player_id for p in response.available_players}
    assert player_ids == {1, 2, 3}
    assert len(response.proposed_matches) > 0


class TestPlayerSelectionAllSeasons:
  """player_selection with no season_id means 'all seasons'.
  Equivalent to /matchmaking?player=... — the player pool comes from
  get_all_players (overall skill, not per-season)."""

  def test_returns_all_players_and_matches(self, servicer):
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[1, 2]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    # All players are available, not just the selected ones
    player_ids = {p.player_id for p in response.available_players}
    assert player_ids == {1, 2, 3}

    assert len(response.proposed_matches) > 0
    match = response.proposed_matches[0]
    assert len(match.team1) == 1
    assert len(match.team2) == 1

  def test_season_id_zero_means_all_seasons(self, servicer):
    """season_id=0 is invalid, so player_selection falls back to
    all-season behavior."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      season_id=0,
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[1, 2]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    player_ids = {p.player_id for p in response.available_players}
    assert player_ids == {1, 2, 3}
    assert len(response.proposed_matches) > 0


class TestPlayerSelectionWithSeason:
  """player_selection with an explicit season_id.
  Equivalent to /matchmaking/season/N?player=..."""

  def test_returns_season_players_and_matches(self, servicer):
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      season_id=1,
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[1, 2]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    player_ids = {p.player_id for p in response.available_players}
    assert player_ids == {1, 2, 3}
    assert len(response.proposed_matches) > 0
    match = response.proposed_matches[0]
    assert len(match.team1) == 1
    assert len(match.team2) == 1


class TestNoPlayersSelected:
  """No players selected yet — return the player pool but no matches."""

  def test_empty_player_ids(self, servicer):
    """Initial /matchmaking page load with no ?player= params."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    assert len(response.available_players) == 3
    assert len(response.proposed_matches) == 0

  def test_no_selection_oneof(self, servicer):
    """No selection oneof set at all."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest()
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    assert len(response.available_players) == 3
    assert len(response.proposed_matches) == 0

  def test_nonexistent_players_yield_no_matches(self, servicer):
    """Selected player IDs that don't exist in the pool."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[999, 998]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    assert len(response.available_players) == 3
    assert len(response.proposed_matches) == 0


class TestInvalidSeason:
  """Invalid or nonexistent season_id."""

  def test_nonexistent_season_returns_no_players(self, servicer):
    """A season that doesn't exist returns an empty player pool."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      season_id=999,
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[1, 2]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    assert len(response.available_players) == 0
    assert len(response.proposed_matches) == 0

  def test_season_with_no_rounds_returns_no_players(self, servicer):
    """Season 2 exists but has no rounds played, so no skills."""
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      season_id=2,
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=[1, 2]
      )
    )
    context = MagicMock()

    response = servicer.ComputeMatchmaking(request, context)

    assert not context.abort.called
    assert len(response.available_players) == 0
    assert len(response.proposed_matches) == 0


class TestInvalidInput:
  """Error handling."""

  def test_too_many_players(self, servicer):
    request = matchmaking_service_pb2.ComputeMatchmakingRequest(
      player_selection=matchmaking_service_pb2.PlayerSelection(
        player_ids=list(range(1, 21))
      )
    )
    context = MagicMock()

    servicer.ComputeMatchmaking(request, context)

    assert context.abort.called
    args, _ = context.abort.call_args
    assert args[0] == grpc.StatusCode.INVALID_ARGUMENT
    assert "Cannot compute matches for more than" in args[1]


