import datetime
import sqlite3
import pytest
from typing import Dict

from truescrub.models import Player, skill_group_name
from truescrub.highlights import (
    get_highlights, get_round_range_for_day, get_player_ratings_between_rounds,
    get_most_played_maps_between_rounds, get_skill_changes_between_rounds,
    make_player_rating
)
from tests.db_test_utils import TestDBManager, create_game_state_for_round


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
  game_db, skill_db = db_manager.create_in_memory_dbs()

  map_distribution = map_distribution or {'de_dust2': 5, 'de_mirage': 3,
                                          'de_nuke': 2}

  # Define team members
  ct_team = [(1, "Player1"), (2, "Player2")]
  t_team = [(3, "Player3")]

  # Create game states
  game_states = []

  # Track player statistics across rounds
  player_stats = {
    1: {"match_mvps": 0},
    2: {"match_mvps": 0},
    3: {"match_mvps": 0}
  }

  # Create rounds for the specific day
  for i in range(1, num_rounds + 1):
    # Determine which map to use based on distribution
    map_index = i
    current_map = None
    for map_name, count in map_distribution.items():
      if map_index <= count:
        current_map = map_name
        break
      map_index -= count

    # Determine winner
    winner = "CT"  # CT wins every round for simplicity

    # Update player stats for this round
    round_stats = {
      1: {
        "kills": i % 3,
        "assists": i % 2,
        "deaths": 0,
        "damage": 50 + i * 10,
        "survived": True,
        "match_mvps": player_stats[1]["match_mvps"],
        "mvp": i % 3 == 0  # Player 1 gets MVP every 3rd round
      },
      2: {
        "kills": i % 2,
        "assists": i % 3,
        "deaths": 0,
        "damage": 100 + i * 10,
        "survived": True,
        "match_mvps": player_stats[2]["match_mvps"],
        "mvp": i % 3 == 1  # Player 2 gets MVP every 3rd+1 round
      },
      3: {
        "kills": 0,
        "assists": 0,
        "deaths": 1,
        "damage": 20 + i * 5,
        "survived": False,
        "match_mvps": player_stats[3]["match_mvps"],
        "mvp": i % 3 == 2  # Player 3 gets MVP every 3rd+2 round
      }
    }

    # Update match MVP counts
    for player_id in player_stats:
      if round_stats[player_id]["mvp"]:
        player_stats[player_id]["match_mvps"] += 1

    # Create game state
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

  # Add game states to database
  db_manager.add_game_states(game_states)

  # Process game states to update skill database
  db_manager.process_game_states()

  return skill_db


@pytest.fixture
def populated_db():
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


def test_get_round_range_for_day(populated_db):
    db = populated_db
    day = datetime.datetime(2022, 1, 15)
    
    round_range, rounds_played = get_round_range_for_day(db, day)
    
    # Check correct round range is returned
    assert round_range == (1, 10)
    assert rounds_played == 10


def test_get_most_played_maps_between_rounds(populated_db):
    db = populated_db
    round_range = (1, 10)
    
    result = get_most_played_maps_between_rounds(db, round_range)
    
    # Check the distribution of maps
    assert result == {'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2}


def test_get_player_ratings_between_rounds(populated_db):
    db = populated_db
    round_range = (1, 10)
    
    result = get_player_ratings_between_rounds(db, round_range)
    
    # Verify results
    assert len(result) == 3  # Three players
    
    # Results should be sorted by impact_rating in descending order
    player_ids = [player['player_id'] for player in result]
    assert 1 in player_ids  # Player 1 should be included
    assert 2 in player_ids  # Player 2 should be included
    assert 3 in player_ids  # Player 3 should be included
    
    # Check rating details structure for each player
    for player_rating in result:
        assert 'rating_details' in player_rating
        assert 'previous_skill' in player_rating
        assert 'rounds_played' in player_rating
        assert 'mvps' in player_rating
        
        # Check rating details has expected fields
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


def test_get_skill_changes_between_rounds(populated_db):
    db = populated_db
    round_range = (1, 10)
    
    result = get_skill_changes_between_rounds(db, round_range)
    
    # Player 1 should have a skill group change due to significant skill increase
    player_ids = [previous.player_id for previous, _ in result]
    assert 1 in player_ids
    
    # Find Player 1's skill change
    for previous, next_skill in result:
        if previous.player_id == 1:
            # Verify the skill group change
            assert previous.skill_group_index != next_skill.skill_group_index
            
            # MMR should have increased
            assert next_skill.mmr > previous.mmr
            break


def test_get_highlights(populated_db):
    db = populated_db
    day = datetime.datetime(2022, 1, 15)
    
    result = get_highlights(db, day)
    
    # Check result structure
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
    assert result['most_played_maps'] == {'de_dust2': 5, 'de_mirage': 3, 'de_nuke': 2}
    
    # Check player ratings
    assert len(result['player_ratings']) == 3
    
    # Check skill group changes
    skill_changes = result['season_skill_group_changes']
    assert len(skill_changes) >= 1
    
    # At least Player 1 should have changed skill groups
    player_ids = [change['player_id'] for change in skill_changes]
    assert 1 in player_ids
    
    # Verify skill group change structure
    for change in skill_changes:
        if change['player_id'] == 1:
            assert 'previous_skill' in change
            assert 'next_skill' in change
            assert change['previous_skill']['skill_group'] != change['next_skill']['skill_group']
            assert change['next_skill']['mmr'] > change['previous_skill']['mmr']


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__]))