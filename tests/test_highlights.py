import datetime
import sqlite3
from typing import Dict

import pytest

from tests.db_test_utils import TestDBManager, create_game_state_for_round
from truescrub.highlights import (
  get_highlights, get_round_range_for_day, get_player_ratings_between_rounds,
  get_most_played_maps_between_rounds, get_skill_changes_between_rounds,
  make_player_rating
)
from truescrub.models import Player, skill_group_name


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


def test_make_player_rating():
  player = Player(
    player_id=12345,
    steam_name="TestPlayer",
    skill_mean=1200,
    skill_stdev=125,
    impact_rating=1.5
  )

  rating_details = {
    'average_kills': 2.5,
    'average_deaths': 1.2,
    'average_damage': 150,
    'average_assists': 1.0,
    'total_kills': 25,
    'total_deaths': 12,
    'total_damage': 1500,
    'total_assists': 10,
    'kdr': 2.08
  }

  rounds_played = 10
  mvps = 3

  result = make_player_rating(player, rating_details, rounds_played, mvps)

  assert result == {
    'player_id': 12345,
    'steam_name': 'TestPlayer',
    'impact_rating': 1.5,
    'previous_skill': {
      'mmr': 950,  # 1200 - 2*125
      'skill_group': skill_group_name(player.skill_group_index),
    },
    'rating_details': rating_details,
    'rounds_played': rounds_played,
    'mvps': mvps,
  }


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

  player_ids = {player['player_id'] for player in result}
  assert {1, 2, 3}.issubset(player_ids)

  for player_rating in result:
    assert 'rating_details' in player_rating
    assert 'previous_skill' in player_rating
    assert 'rounds_played' in player_rating
    assert 'mvps' in player_rating

    rating_details = player_rating['rating_details']
    assert 'average_kills' in rating_details
    assert 'average_deaths' in rating_details
    assert 'average_damage' in rating_details
    assert 'average_assists' in rating_details
    assert 'total_kills' in rating_details
    assert 'total_deaths' in rating_details
    assert 'total_damage' in rating_details
    assert 'total_assists' in rating_details
    assert 'kdr' in rating_details


def test_get_skill_changes_between_rounds(test_db):
  round_range = (1, 10)

  result = get_skill_changes_between_rounds(test_db, round_range)

  previous, next_skill = next(skill_change
                              for skill_change in result
                              if skill_change[0].player_id == 1)

  assert previous.skill_group_index != next_skill.skill_group_index
  assert next_skill.mmr > previous.mmr


def test_get_highlights(test_db):
  day = datetime.datetime(2022, 1, 15)

  result = get_highlights(test_db, day)

  assert set(result.keys()) == {
    'time_window', 'rounds_played', 'most_played_maps',
    'player_ratings', 'season_skill_group_changes'
  }

  # Check time window
  assert result['time_window'] == [
    day.isoformat(),
    (day + datetime.timedelta(days=1)).isoformat()
  ]

  # Check rounds played
  assert result['rounds_played'] == 10

  # Check maps
  assert result['most_played_maps'] == {
    'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2}

  assert len(result['player_ratings']) == 3

  skill_changes = result['season_skill_group_changes']
  assert len(skill_changes) >= 1

  player1 = next(change for change in skill_changes if change['player_id'] == 1)

  assert 'previous_skill' in player1
  assert 'next_skill' in player1
  assert (player1['previous_skill']['skill_group'] !=
          player1['next_skill']['skill_group'])
  assert player1['next_skill']['mmr'] > player1['previous_skill']['mmr']


if __name__ == '__main__':
  raise SystemExit(pytest.main([__file__]))
