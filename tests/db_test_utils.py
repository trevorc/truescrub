"""
Utility module for creating and populating in-memory test databases.
This module uses the existing updater logic to transform game states into skill database content.
"""
import datetime
import json
import pathlib
import sqlite3
from typing import Dict, List, Tuple

import pytest

from truescrub import seasoncfg
from truescrub.db import (
  initialize_skill_db, initialize_game_db, execute_one,
  insert_game_state
)
from truescrub.updater.recalculate import (
  compute_rounds_and_players, recalculate_ratings, load_seasons
)


class TestGameState:
  """
  Class representing a test game state with simplified structure.
  Only includes the fields necessary for testing.
  """

  def __init__(
      self,
      timestamp: datetime.datetime,
      map_name: str,
      round_phase: str = 'over',
      previous_round_phase: str = 'live',
      win_team: str = "CT",
      players: Dict[str, Dict] = None,
      previous_players: Dict[str, Dict] = None
  ):
    """
    Initialize a test game state.

    Args:
        timestamp: Timestamp of the game state
        map_name: Map name
        round_phase: Current round phase
        previous_round_phase: Previous round phase
        win_team: Winning team
        players: Dictionary of player data by Steam ID
        previous_players: Dictionary of previous player data by Steam ID
    """
    self.timestamp = int(timestamp.timestamp())
    self.map_name = map_name
    self.round_phase = round_phase
    self.previous_round_phase = previous_round_phase
    self.win_team = win_team
    self.players = players or {}
    self.previous_players = previous_players or {}

  def to_json(self) -> Dict:
    """Convert to a simplified game state JSON structure for testing."""
    game_state = {
      "provider": {
        "name": "Counter-Strike: Global Offensive",
        "appid": 730,
        "version": 13694,
        "steamid": "76561198413889827",
        "timestamp": self.timestamp
      },
      "map": {
        "name": self.map_name,
        "phase": "live",
        "round": 1,
        "team_ct": {
          "score": 0,
          "consecutive_round_losses": 0,
          "timeouts_remaining": 1,
          "matches_won_this_series": 0
        },
        "team_t": {
          "score": 0,
          "consecutive_round_losses": 0,
          "timeouts_remaining": 1,
          "matches_won_this_series": 0
        }
      },
      "round": {
        "phase": self.round_phase,
        "win_team": self.win_team if self.round_phase == "over" else None
      },
      "allplayers": self.players,
      "previously": {
        "round": {
          "phase": self.previous_round_phase
        },
        "allplayers": self.previous_players
      }
    }
    return game_state


class TestDBManager:
  """
  Manager for creating and populating test databases.
  Uses the existing updater logic to transform game states into skill database content.
  """

  def __init__(self):
    self.game_db = sqlite3.connect(":memory:")
    self.skill_db = sqlite3.connect(":memory:")
    self.seasons_toml = pathlib.Path('tests/sample_seasons.toml')
    initialize_game_db(self.game_db)
    initialize_skill_db(self.skill_db)
    self._setup_seasons()

  def _setup_seasons(self):
    """Set up basic seasons in both databases."""
    with pytest.MonkeyPatch.context() as m:
      m.setattr(seasoncfg, 'SEASONS_TOML', self.seasons_toml)
      load_seasons(self.skill_db)

  def add_game_states(self, game_states: List[TestGameState]) -> List[int]:
    """
    Add game states to the game database and return the game state IDs.

    Args:
        game_states: List of TestGameState objects

    Returns:
        List of inserted game state IDs
    """

    game_state_ids = []

    for gs in game_states:
      # Convert to JSON string and insert
      gs_json = json.dumps(gs.to_json())
      game_state_id = insert_game_state(self.game_db, gs_json)
      game_state_ids.append(game_state_id)

    self.game_db.commit()
    return game_state_ids

  def process_game_states(self):
    """
    Process game states and update player skills using the existing updater logic.
    """

    # Get count of game states
    game_state_count = execute_one(
      self.game_db, "SELECT COUNT(*) FROM game_state")[0]
    if game_state_count == 0:
      return None

    game_state_range = (1, game_state_count)

    with pytest.MonkeyPatch.context() as m:
      m.setattr(seasoncfg, 'SEASONS_TOML', self.seasons_toml)

      max_game_state_id, new_rounds = compute_rounds_and_players(
        self.game_db, self.skill_db, game_state_range)

      if new_rounds is not None:
        recalculate_ratings(self.skill_db, new_rounds)

      self.game_db.commit()
      self.skill_db.commit()
      return new_rounds

  def close(self):
    """Close database connections."""
    self.game_db.close()
    self.skill_db.close()


def create_player_data(
    name: str,
    team: str,
    kills: int = 0,
    assists: int = 0,
    deaths: int = 0,
    damage: int = 0,
    survived: bool = True,
    match_mvps: int = 0,
    previous_match_mvps: int = 0,
    weapons: Dict = None
) -> Dict:
  """
  Create a player data dictionary for use in TestGameState.

  Args:
      name: Player name
      team: Team (CT or T)
      kills: Number of kills
      assists: Number of assists
      deaths: Number of deaths
      damage: Amount of damage
      survived: Whether the player survived the round
      match_mvps: Current match MVP count
      previous_match_mvps: Previous match MVP count
      weapons: Dictionary of weapons

  Returns:
      Player data dictionary
  """
  weapons_dict = weapons or {}

  # If no weapons provided, create a default loadout
  if not weapons_dict:
    if team == "CT":
      weapons_dict = {
        "0": {"name": "weapon_knife"},
        "1": {"name": "weapon_usp_silencer"},
        "2": {"name": "weapon_m4a1"}
      }
    else:
      weapons_dict = {
        "0": {"name": "weapon_knife_t"},
        "1": {"name": "weapon_glock"},
        "2": {"name": "weapon_ak47"}
      }

  return {
    "name": name,
    "team": team,
    "observer_slot": 1,
    "match_stats": {
      "kills": kills,
      "assists": assists,
      "deaths": deaths,
      "mvps": match_mvps,
      "score": kills * 2 + assists
    },
    "state": {
      "health": 100 if survived else 0,
      "armor": 100 if survived else 0,
      "helmet": False,
      "flashed": 0,
      "burning": 0,
      "money": 800,
      "round_kills": kills,
      "round_killhs": kills // 2,
      "round_totaldmg": damage,
      "equip_value": 200
    },
    "weapons": weapons_dict
  }


def create_game_state_for_round(
    timestamp: datetime.datetime,
    map_name: str,
    ct_team: List[Tuple[int, str]],  # List of (steam_id, name) tuples
    t_team: List[Tuple[int, str]],  # List of (steam_id, name) tuples
    winner: str,  # "CT" or "T"
    player_stats: Dict[int, Dict] = None
    # {steam_id: {kills, assists, deaths, damage, survived}}
) -> TestGameState:
  """
  Create a game state for a complete round.

  Args:
      timestamp: Timestamp of the round
      map_name: Map name
      ct_team: List of (steam_id, name) tuples for CT team
      t_team: List of (steam_id, name) tuples for T team
      winner: Winner team ("CT" or "T")
      player_stats: Dictionary of player stats by Steam ID

  Returns:
      TestGameState object
  """
  stats = player_stats or {}
  current_players = {}
  previous_players = {}

  # Create player data for CT team
  for steam_id, name in ct_team:
    player_stat = stats.get(steam_id, {})
    current_players[str(steam_id)] = create_player_data(
      name=name,
      team="CT",
      kills=player_stat.get("kills", 0),
      assists=player_stat.get("assists", 0),
      deaths=player_stat.get("deaths", 0),
      damage=player_stat.get("damage", 0),
      survived=player_stat.get("survived", True),
      match_mvps=player_stat.get("match_mvps", 0) + (
        1 if winner == "CT" and player_stat.get("mvp", False) else 0),
      previous_match_mvps=player_stat.get("match_mvps", 0)
    )

    # Create "previous" state with no kills in this round
    previous_players[str(steam_id)] = create_player_data(
      name=name,
      team="CT",
      kills=0,
      assists=player_stat.get("assists", 0),
      deaths=player_stat.get("deaths", 0),
      match_mvps=player_stat.get("match_mvps", 0)
    )

  # Create player data for T team
  for steam_id, name in t_team:
    player_stat = stats.get(steam_id, {})
    current_players[str(steam_id)] = create_player_data(
      name=name,
      team="T",
      kills=player_stat.get("kills", 0),
      assists=player_stat.get("assists", 0),
      deaths=player_stat.get("deaths", 0),
      damage=player_stat.get("damage", 0),
      survived=player_stat.get("survived", True),
      match_mvps=player_stat.get("match_mvps", 0) + (
        1 if winner == "T" and player_stat.get("mvp", False) else 0),
      previous_match_mvps=player_stat.get("match_mvps", 0)
    )

    # Create "previous" state with no kills in this round
    previous_players[str(steam_id)] = create_player_data(
      name=name,
      team="T",
      kills=0,
      assists=player_stat.get("assists", 0),
      deaths=player_stat.get("deaths", 0),
      match_mvps=player_stat.get("match_mvps", 0)
    )

  return TestGameState(
    timestamp=timestamp,
    map_name=map_name,
    round_phase="over",
    previous_round_phase="live",
    win_team=winner,
    players=current_players,
    previous_players=previous_players
  )
