import datetime
import sqlite3
from typing import Dict

import pytest

from proto import common_pb2
from proto import highlights_service_pb2
from tests.db_test_utils import TestDBManager, create_game_state_for_round
from truescrub.accolades import get_accolades
from truescrub.highlights import (
  get_highlights, get_round_range_for_day, get_player_ratings_between_rounds,
  get_most_played_maps_between_rounds, get_skill_changes_between_rounds
)


def create_test_db(
    day: datetime.datetime,
    num_rounds: int = 10,
    map_distribution: Dict[str, int] = None
) -> sqlite3.Connection:
  """
  Create a test database specifically configured for testing highlights.py

  Args:
      day: The day to create highlights for
      num_rounds: Number of rounds to create
      map_distribution: Dict mapping map names to count of rounds
                       (e.g. {'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2})

  Returns:
      Populated skill database connection
  """
  db_manager = TestDBManager()

  map_distribution = map_distribution or {'de_dust2': 5, 'de_mirage': 3,
                                          'de_nuke': 2}

  ct_team = [(1, "Player1"), (2, "Player2")]
  t_team = [(3, "Player3")]

  game_states = []

  player_stats = {
    1: {"match_mvps": 0},
    2: {"match_mvps": 0},
    3: {"match_mvps": 0}
  }

  for i in range(1, num_rounds + 1):
    map_index = i
    current_map = None
    for map_name, count in map_distribution.items():
      if map_index <= count:
        current_map = map_name
        break
      map_index -= count

    winner = "CT"

    round_stats = {
      1: {
        "kills": i % 3,
        "assists": i % 2,
        "deaths": 0,
        "damage": 50 + i * 10,
        "survived": True,
        "match_mvps": player_stats[1]["match_mvps"],
        "mvp": i % 3 == 0
      },
      2: {
        "kills": i % 2,
        "assists": i % 3,
        "deaths": 0,
        "damage": 100 + i * 10,
        "survived": True,
        "match_mvps": player_stats[2]["match_mvps"],
        "mvp": i % 3 == 1
      },
      3: {
        "kills": 0,
        "assists": 0,
        "deaths": 1,
        "damage": 20 + i * 5,
        "survived": False,
        "match_mvps": player_stats[3]["match_mvps"],
        "mvp": i % 3 == 2
      }
    }

    for player_id in player_stats:
      if round_stats[player_id]["mvp"]:
        player_stats[player_id]["match_mvps"] += 1

    timestamp = day + datetime.timedelta(hours=i)
    game_state = create_game_state_for_round(
      timestamp=timestamp,
      map_name=current_map,
      ct_team=ct_team,
      t_team=t_team,
      winner=winner,
      player_stats=round_stats
    )

    game_states.append(game_state)

  db_manager.add_game_states(game_states)
  db_manager.process_game_states()

  return db_manager.skill_db


@pytest.fixture
def test_db():
  """Create a populated database for testing highlights module."""
  day = datetime.datetime(2022, 1, 15)
  map_distribution = {'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2}
  return create_test_db(day, 10, map_distribution)


def test_get_round_range_for_day(test_db):
  day = datetime.datetime(2022, 1, 15)

  round_range, rounds_played = get_round_range_for_day(test_db, day)

  assert round_range == (1, 10)
  assert rounds_played == 10


def test_get_most_played_maps_between_rounds(test_db):
  round_range = (1, 10)

  result = get_most_played_maps_between_rounds(test_db, round_range)

  # Check the distribution of maps
  assert result == {'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2}


def test_get_player_ratings_between_rounds(test_db):
  db = test_db
  round_range = (1, 10)

  result = get_player_ratings_between_rounds(db, round_range)

  assert len(result) == 3  # Three players

  player_ids = {player.player.player_id for player in result}
  assert {1, 2, 3}.issubset(player_ids)

  for player_rating in result:
    assert isinstance(player_rating, highlights_service_pb2.DailyHighlight)
    assert player_rating.HasField('rating_details')
    assert player_rating.HasField('starting_skill')
    assert player_rating.rounds_played > 0

    rd = player_rating.rating_details
    assert rd.average_kills >= 0
    assert rd.average_deaths >= 0
    assert rd.average_damage >= 0
    assert rd.average_assists >= 0
    assert rd.total_kills >= 0
    assert rd.total_deaths >= 0
    assert rd.total_damage >= 0
    assert rd.total_assists >= 0
    assert rd.kdr >= 0


def test_get_skill_changes_between_rounds(test_db):
  round_range = (1, 10)

  result = get_skill_changes_between_rounds(test_db, round_range)

  skill_change = next(change for change in result if change.player_id == 1)

  from truescrub.models import find_skill_group
  assert find_skill_group(skill_change.previous_skill.mmr) != find_skill_group(skill_change.next_skill.mmr)
  assert skill_change.next_skill.mmr > skill_change.previous_skill.mmr


def test_get_highlights(test_db):
  day = datetime.datetime(2022, 1, 15)

  result = get_highlights(test_db, day)

  assert isinstance(result, highlights_service_pb2.GetDailyHighlightsResponse)

  # Check time window
  assert len(result.time_windows) == 1
  assert result.time_windows[0].start_inclusive.ToDatetime() == day
  assert result.time_windows[0].end_exclusive.ToDatetime() == day + datetime.timedelta(days=1)

  # Check rounds played
  assert result.rounds_played == 10

  # Check maps
  assert dict(result.most_played_maps) == {
    'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2}

  assert len(result.players) == 3

  player1 = next(p for p in result.players if p.player.player_id == 1)

  assert player1.HasField('starting_skill')
  assert player1.player.HasField('skill')
  assert player1.starting_skill.mmr != player1.player.skill.mmr
  assert player1.player.skill.mmr > player1.starting_skill.mmr

  skill_changes = result.season_skill_group_changes
  assert len(skill_changes) >= 1

  player1_change = next(change for change in skill_changes if change.player_id == 1)

  assert player1_change.HasField('previous_skill')
  assert player1_change.HasField('next_skill')
  from truescrub.models import find_skill_group
  assert find_skill_group(player1_change.previous_skill.mmr) != find_skill_group(player1_change.next_skill.mmr)
  assert player1_change.next_skill.mmr > player1_change.previous_skill.mmr


def test_get_accolades_in_highlights(test_db):
  day = datetime.datetime(2022, 1, 15)
  round_range, rounds_played = get_round_range_for_day(test_db, day)
  player_ratings = get_player_ratings_between_rounds(test_db, round_range)
  accolades_dict = get_accolades(player_ratings)

  assert len(accolades_dict) == 3
  assert set(accolades_dict.keys()) == {1, 2, 3}

  for accolade_data in accolades_dict.values():
    assert isinstance(accolade_data, highlights_service_pb2.Accolade)
    assert isinstance(accolade_data.name, str)
    assert len(accolade_data.name) > 0
    assert len(accolade_data.details) > 0


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xv", __file__]))
