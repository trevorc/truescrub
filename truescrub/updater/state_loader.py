import abc
import json
from typing import Optional, Tuple

from truescrub.proto.game_state_pb2 import GameStateEntry

from truescrub import db
from truescrub.envconfig import DATA_DIR
from truescrub.models import GameStateRow
from truescrub.seasoncfg import get_seasons_by_start_date
from truescrub.statewriter import GameStateLog
from truescrub.statewriter.state_serialization import (
  ROUND_PHASES, TEAMS, MAP_PHASES, serialize_allplayers_entry)
from truescrub.statewriter.state_writer import LOG_FILE_NAME
from truescrub.updater.state_parser import parse_game_states, RoundsAndPlayers


class StateLoader(abc.ABC):
  @abc.abstractmethod
  def extract_game_states(self, game_state_range: Optional[Tuple[int, int]]):
    pass


class DatabaseStateLoader(StateLoader):
  def __init__(self):
    self.game_db = db.get_game_db()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.game_db.close()

  def extract_game_states(self, game_state_range) -> RoundsAndPlayers:
    season_ids = get_seasons_by_start_date()
    game_states = db.get_game_states(self.game_db, game_state_range)

    return parse_game_states(game_states, season_ids)


def entry_to_row(entry: GameStateEntry) -> GameStateRow:
  game_state = entry.game_state

  allplayers = dict(
    serialize_allplayers_entry(p) for p in game_state.allplayers)

  previous_allplayers = dict(
    serialize_allplayers_entry(p)
    for p in game_state.previously.allplayers.allplayers
  ) if (game_state.HasField('previously') and
        game_state.previously.HasField('allplayers') and
        game_state.previously.allplayers.allplayers) else {}

  return GameStateRow(
    game_state_id=entry.game_state_id,
    round_phase=ROUND_PHASES[game_state.round.phase],
    map_name=game_state.map.name,
    map_phase=MAP_PHASES[game_state.map.phase],
    win_team=TEAMS[game_state.round.win_team],
    timestamp=int(entry.created_at.seconds),
    allplayers=json.dumps(allplayers),
    previous_allplayers=json.dumps(previous_allplayers),
  )


class RiegeliStateLoader(StateLoader):
  def __init__(self, state_log: GameStateLog):
    self.log = state_log

  @classmethod
  def from_env(cls) -> StateLoader:
    log_path = DATA_DIR.joinpath(LOG_FILE_NAME)
    return cls(GameStateLog(log_path))

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    pass


  def extract_game_states(self, game_state_range: Optional[Tuple[int, int]]) \
      -> RoundsAndPlayers:
    season_ids = get_seasons_by_start_date()

    with self.log.reader() as reader:
      start_id = game_state_range[0] if game_state_range else None
      end_id = game_state_range[1] if game_state_range and len(
        game_state_range) > 1 else None

      if end_id is not None:
        game_states = reader.fetch(start_id, end_id)
      else:
        game_states = reader.fetch_all(start_id)

      game_state_rows = map(entry_to_row, game_states)
      return parse_game_states(game_state_rows, season_ids)
