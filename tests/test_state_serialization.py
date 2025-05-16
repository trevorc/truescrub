import json
import unittest

import pytest

from google.protobuf import text_format
from google.protobuf.timestamp_pb2 import Timestamp

from truescrub.proto import game_state_pb2
from truescrub.statewriter.state_parsing import parse_game_state
from truescrub.statewriter.state_serialization import (
  serialize_game_state,
  serialize_provider,
  serialize_player,
  serialize_match_stats,
  serialize_player_state,
  serialize_round,
  serialize_map,
  serialize_team_state,
  serialize_allplayers_entry,
  serialize_previously,
  serialize_added,
)


@unittest.skip
def test_json_proto_json_roundtrip():
  with open('tests/sample_game_states.json') as f:
    sample_states = json.load(f)

  for original_state in sample_states:
    gs_proto = parse_game_state(original_state)
    roundtripped_state = serialize_game_state(gs_proto)
    assert roundtripped_state == original_state


def test_serialize_provider():
  provider_proto = game_state_pb2.Provider(
    name="test_provider",
    app_id=730,
    version=13784,
    steam_id=76561198000000000,
    timestamp=Timestamp(seconds=1678886400)
  )
  expected_dict = {
    "name": "test_provider",
    "appid": 730,
    "version": 13784,
    "steamid": "76561198000000000",
    "timestamp": 1678886400,
  }
  assert serialize_provider(provider_proto) == expected_dict


def test_serialize_match_stats():
  match_stats_proto = game_state_pb2.MatchStats(
    kills=10,
    assists=5,
    deaths=7,
    mvps=2,
    score=25,
  )
  expected_dict = {
    "kills": 10,
    "assists": 5,
    "deaths": 7,
    "mvps": 2,
    "score": 25,
  }
  assert serialize_match_stats(match_stats_proto) == expected_dict


def test_serialize_player_state():
  player_state_proto = game_state_pb2.PlayerState(
    health=100,
    armor=50,
    helmet=True,
    flashed=0,
    smoked=0,
    burning=0,
    money=16000,
    round_kills=2,
    round_killhs=1,
    round_totaldmg=150,
    equip_value=5000,
    defusekit=True,
  )
  expected_dict = {
    "health": 100,
    "armor": 50,
    "helmet": True,
    "flashed": 0,
    "smoked": 0,
    "burning": 0,
    "money": 16000,
    "round_kills": 2,
    "round_killhs": 1,
    "round_totaldmg": 150,
    "equip_value": 5000,
    "defusekit": True,
  }
  assert serialize_player_state(player_state_proto) == expected_dict


def test_serialize_player_state_no_defusekit():
  player_state_proto = game_state_pb2.PlayerState(
    health=100,
    armor=50,
    helmet=True,
    flashed=0,
    smoked=0,
    burning=0,
    money=16000,
    round_kills=2,
    round_killhs=1,
    round_totaldmg=150,
    equip_value=5000,
    defusekit=False,
  )
  expected_dict = {
    "health": 100,
    "armor": 50,
    "helmet": True,
    "flashed": 0,
    "smoked": 0,
    "burning": 0,
    "money": 16000,
    "round_kills": 2,
    "round_killhs": 1,
    "round_totaldmg": 150,
    "equip_value": 5000,
  }
  assert serialize_player_state(player_state_proto) == expected_dict


def test_serialize_player():
  match_stats_proto = game_state_pb2.MatchStats(
    kills=10,
    assists=5,
    deaths=7,
    mvps=2,
    score=25,
  )
  player_state_proto = game_state_pb2.PlayerState(
    health=100,
    armor=50,
    helmet=True,
    flashed=0,
    smoked=0,
    burning=0,
    money=16000,
    round_kills=2,
    round_killhs=1,
    round_totaldmg=150,
    equip_value=5000,
    defusekit=True,
  )
  player_proto = game_state_pb2.Player(
    steam_id=76561198000000001,
    clan="testclan",
    name="testplayer",
    observer_slot=1,
    team=game_state_pb2.TEAM_CT,
    activity=game_state_pb2.Player.ACTIVITY_PLAYING,
    match_stats=match_stats_proto,
    state=player_state_proto,
  )
  expected_dict = {
    "steamid": "76561198000000001",
    "clan": "testclan",
    "name": "testplayer",
    "observer_slot": 1,
    "team": "CT",
    "activity": "playing",
    "match_stats": {
      "kills": 10,
      "assists": 5,
      "deaths": 7,
      "mvps": 2,
      "score": 25,
    },
    "state": {
      "health": 100,
      "armor": 50,
      "helmet": True,
      "flashed": 0,
      "smoked": 0,
      "burning": 0,
      "money": 16000,
      "round_kills": 2,
      "round_killhs": 1,
      "round_totaldmg": 150,
      "equip_value": 5000,
      "defusekit": True,
    },
  }
  assert serialize_player(player_proto) == expected_dict


def test_serialize_player_minimal():
  player_proto = game_state_pb2.Player(
    steam_id=76561198000000001,
    name="testplayer",
    team=game_state_pb2.TEAM_T,
    activity=game_state_pb2.Player.ACTIVITY_MENU,
  )
  expected_dict = {
    "steamid": "76561198000000001",
    "name": "testplayer",
    "team": "T",
    "activity": "menu",
  }
  assert serialize_player(player_proto) == expected_dict


def test_serialize_round():
  round_proto = game_state_pb2.Round(
    phase=game_state_pb2.Round.ROUND_PHASE_LIVE,
    win_team=game_state_pb2.TEAM_CT,
    bomb=game_state_pb2.Round.BOMB_PLANTED,
  )
  expected_dict = {
    "phase": "live",
    "win_team": "CT",
    "bomb": "planted",
  }
  assert serialize_round(round_proto) == expected_dict


def test_serialize_round_no_bomb():
  round_proto = game_state_pb2.Round(
    phase=game_state_pb2.Round.ROUND_PHASE_FREEZETIME,
    win_team=game_state_pb2.TEAM_T,
  )
  expected_dict = {
    "phase": "freezetime",
    "win_team": "T",
  }
  assert serialize_round(round_proto) == expected_dict


def test_serialize_team_state():
  team_state_proto = game_state_pb2.TeamState(
    score=10,
    consecutive_round_losses=2,
    timeouts_remaining=1,
    matches_won_this_series=1,
  )
  expected_dict = {
    "score": 10,
    "consecutive_round_losses": 2,
    "timeouts_remaining": 1,
    "matches_won_this_series": 1,
  }
  assert serialize_team_state(team_state_proto) == expected_dict


def test_serialize_map():
  team_t_state_proto = game_state_pb2.TeamState(
    score=10,
    consecutive_round_losses=2,
    timeouts_remaining=1,
    matches_won_this_series=1,
  )
  team_ct_state_proto = game_state_pb2.TeamState(
    score=16,
    consecutive_round_losses=0,
    timeouts_remaining=0,
    matches_won_this_series=2,
  )
  round_win_proto_1 = game_state_pb2.RoundWin(
    round_num=1,
    win_condition=game_state_pb2.RoundWin.WIN_CONDITION_CT_WIN_DEFUSE,
  )
  round_win_proto_2 = game_state_pb2.RoundWin(
    round_num=2,
    win_condition=game_state_pb2.RoundWin.WIN_CONDITION_T_WIN_ELIMINATION,
  )
  map_proto = game_state_pb2.Map(
    mode=game_state_pb2.MODE_COMPETITIVE,
    name="de_dust2",
    phase=game_state_pb2.MAP_PHASE_LIVE,
    round=15,
    team_t=team_t_state_proto,
    team_ct=team_ct_state_proto,
    num_matches_to_win_series=3,
    current_spectators=50,
    souvenirs_total=10,
    round_wins=[round_win_proto_1, round_win_proto_2],
  )
  expected_dict = {
    "mode": "competitive",
    "name": "de_dust2",
    "phase": "live",
    "round": 15,
    "team_t": {
      "score": 10,
      "consecutive_round_losses": 2,
      "timeouts_remaining": 1,
      "matches_won_this_series": 1,
    },
    "team_ct": {
      "score": 16,
      "consecutive_round_losses": 0,
      "timeouts_remaining": 0,
      "matches_won_this_series": 2,
    },
    "num_matches_to_win_series": 3,
    "round_wins": {
      "1": "ct_win_defuse",
      "2": "t_win_elimination",
    },
    "current_spectators": 50,
    "souvenirs_total": 10,
  }
  assert serialize_map(map_proto) == expected_dict


def test_serialize_thin_player():
  match_stats_proto = game_state_pb2.MatchStats(
    kills=5,
    assists=2,
    deaths=3,
    mvps=1,
    score=15,
  )
  player_state_proto = game_state_pb2.PlayerState(
    health=80,
    armor=80,
    helmet=False,
    flashed=10,
    smoked=5,
    burning=0,
    money=5000,
    round_kills=1,
    round_killhs=1,
    round_totaldmg=80,
    equip_value=3000,
    defusekit=False,
  )
  thin_player_proto = game_state_pb2.ThinPlayer(
    steam_id=76561198000000002,
    name="thinplayer",
    observer_slot=2,
    team=game_state_pb2.TEAM_T,
    match_stats=match_stats_proto,
    state=player_state_proto,
    clan="thinclan",
  )
  expected_tuple = (
    "76561198000000002", {
    "name": "thinplayer",
    "observer_slot": 2,
    "team": "T",
    "match_stats": {
      "kills": 5,
      "assists": 2,
      "deaths": 3,
      "mvps": 1,
      "score": 15,
    },
    "state": {
      "health": 80,
      "armor": 80,
      "helmet": False,
      "flashed": 10,
      "smoked": 5,
      "burning": 0,
      "money": 5000,
      "round_kills": 1,
      "round_killhs": 1,
      "round_totaldmg": 80,
      "equip_value": 3000,
    },
    "clan": "thinclan",
  }
  )
  assert serialize_allplayers_entry(thin_player_proto) == expected_tuple


def test_serialize_previously():
  map_proto = game_state_pb2.Map(
    mode=game_state_pb2.MODE_CASUAL,
    name="de_mirage",
    phase=game_state_pb2.MAP_PHASE_INTERMISSION,
    round=10,
  )
  player_proto = game_state_pb2.Player(
    steam_id=76561198000000003,
    name="prevplayer",
    team=game_state_pb2.TEAM_CT,
    activity=game_state_pb2.Player.ACTIVITY_TEXTINPUT,
  )
  round_proto = game_state_pb2.Round(
    phase=game_state_pb2.Round.ROUND_PHASE_OVER,
    win_team=game_state_pb2.TEAM_T,
    bomb=game_state_pb2.Round.BOMB_EXPLODED,
  )
  thin_player_proto_1 = game_state_pb2.ThinPlayer(
    steam_id=76561198000000004,
    name="prevalplayer1",
    team=game_state_pb2.TEAM_T,
  )
  thin_player_proto_2 = game_state_pb2.ThinPlayer(
    steam_id=76561198000000005,
    name="prevalplayer2",
    team=game_state_pb2.TEAM_CT,
  )
  previous_allplayers_proto = game_state_pb2.PreviousAllPlayers(
    allplayers=[thin_player_proto_1, thin_player_proto_2]
  )
  previously_proto = game_state_pb2.Previously(
    map=map_proto,
    player=player_proto,
    round=round_proto,
    allplayers=previous_allplayers_proto,
  )
  expected_dict = {
    "map": {
      "mode": "casual",
      "name": "de_mirage",
      "phase": "intermission",
      "round": 10,
      "num_matches_to_win_series": 0,
      "round_wins": {},
      "current_spectators": 0,
      "souvenirs_total": 0,
    },
    "player": {
      "steamid": "76561198000000003",
      "name": "prevplayer",
      "team": "CT",
      "activity": "textinput",
    },
    "round": {
      "phase": "over",
      "win_team": "T",
      "bomb": "exploded",
    },
    "allplayers": {
      "76561198000000004": {
        "name": "prevalplayer1",
        "team": "T",
      },
      "76561198000000005": {
        "name": "prevalplayer2",
        "team": "CT",
      },
    },
  }
  assert serialize_previously(previously_proto) == expected_dict


def test_serialize_previously_allplayers_present():
  previously_proto = game_state_pb2.Previously(
    allplayers_present=True
  )
  assert serialize_previously(previously_proto) == {
    "allplayers": True,
  }


def test_serialize_previously_round_present():
  previously_proto = game_state_pb2.Previously(round_present=True)
  assert serialize_previously(previously_proto) == {"round": True}


def test_serialize_added_player():
  player_added_proto = game_state_pb2.PlayerAdded(
    clan=True,
    observer_slot=True,
    team=True,
    match_stats=True,
    state=True,
  )
  added_proto = game_state_pb2.Added(
    player=player_added_proto
  )
  expected_dict = {
    "player": {
      "clan": True,
      "observer_slot": True,
      "team": True,
      "match_stats": True,
      "state": True,
    }
  }
  assert serialize_added(added_proto) == expected_dict


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xvv", __file__]))
