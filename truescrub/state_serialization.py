import itertools
import json
import logging
from typing import Optional

from google.protobuf.timestamp_pb2 import Timestamp

from truescrub.proto import game_state_pb2


class DeserializationError(RuntimeError):
  pass


class InvalidGameStateException(RuntimeError):
  pass


logger = logging.getLogger(__name__)


def translate_enum(enum, prefix):
  tr = {}
  for name, value in enum.items():
    if not name.startswith(prefix):
      raise ValueError(f'{name} did not start with {prefix}')
    tr[name[len(prefix):].lower()] = value
  return tr


TEAMS = {'T': 0, 'CT': 1}
ACTIVITIES = translate_enum(game_state_pb2.Player.Activity, 'ACTIVITY_')
ROUND_PHASES = translate_enum(game_state_pb2.Round.RoundPhase, 'ROUND_PHASE_')
BOMBS = translate_enum(game_state_pb2.Round.Bomb, 'BOMB_')
MODES = translate_enum(game_state_pb2.Mode, 'MODE_')
MAP_PHASES = translate_enum(game_state_pb2.MapPhase, 'MAP_PHASE_')
WIN_CONDITIONS = translate_enum(game_state_pb2.RoundWin.WinCondition,
                                'WIN_CONDITION_')


def parse_team_state(ts_json: dict) -> game_state_pb2.TeamState:
  return game_state_pb2.TeamState(
      score=ts_json.get('score'),
      consecutive_round_losses=ts_json.get('consecutive_round_losses'),
      timeouts_remaining=ts_json.get('timeouts_remaining'),
      matches_won_this_series=ts_json.get('matches_won_this_series'),
  )


def parse_round_win(round_num: str, win_condition: str) -> game_state_pb2.RoundWin:
  if win_condition == '':
    raise InvalidRoundException(f'empty win condition for round {round_num}')
  return game_state_pb2.RoundWin(
      round_num=int(round_num),
      win_condition=WIN_CONDITIONS[win_condition])


def parse_map(map_json) -> game_state_pb2.Map:
  if map_json is None:
    return None
  try:
    mode = MODES[map_json['mode']] if 'mode' in map_json else None
    phase = MAP_PHASES[map_json['phase']] if 'phase' in map_json else None
    team_ct = parse_team_state(map_json['team_ct']) \
      if 'team_ct' in map_json else None
    team_t = parse_team_state(map_json['team_t']) \
      if 'team_t' in map_json else None
    return game_state_pb2.Map(
        mode=mode, name=map_json.get('name'), phase=phase,
        round=map_json.get('round'), team_ct=team_ct, team_t=team_t,
        num_matches_to_win_series=map_json.get('num_matches_to_win_series'),
        round_wins=list(itertools.starmap(
            parse_round_win, map_json.get('round_wins', {}).items())),
    )
  except KeyError as e:
    raise DeserializationError(e)


def parse_player(player_json: Optional[dict]) -> Optional[game_state_pb2.Player]:
  if player_json is None:
    return None
  steam_id = int(player_json['steamid']) if 'steamid' in player_json else None
  team = TEAMS[player_json['team']] if 'team' in player_json else None
  try:
    activity = ACTIVITIES[player_json['activity']] \
      if 'activity' in player_json else None
    match_stats = parse_match_stats(player_json['match_stats']) \
      if 'match_stats' in player_json else None
    player_state = parse_player_state(player_json['state']) \
      if 'state' in player_json else None
  except KeyError as e:
    raise DeserializationError(e)

  return game_state_pb2.Player(
      steam_id=steam_id,
      clan=player_json.get('clan'),
      name=player_json.get('name'),
      observer_slot=player_json.get('observer_slot'),
      team=team, activity=activity, match_stats=match_stats,
      state=player_state,
  )


def parse_provider(provider_json) -> game_state_pb2.Provider:
  try:
    timestamp = Timestamp()
    timestamp.FromSeconds(provider_json['timestamp'])
    return game_state_pb2.Provider(
        app_id=int(provider_json['appid']),
        name=provider_json['name'],
        steam_id=int(provider_json['steamid']),
        timestamp=timestamp,
        version=int(provider_json['version']),
    )
  except (TypeError, KeyError) as e:
    raise DeserializationError(e)


def parse_round(round_json: Optional[dict]) -> Optional[game_state_pb2.Round]:
  if round_json is None:
    return None
  win_team = TEAMS[round_json['win_team']] \
    if 'win_team' in round_json else None
  return game_state_pb2.Round(
      phase=ROUND_PHASES[round_json['phase']],
      win_team=win_team,
      bomb=BOMBS[round_json.get('bomb', 'unspecified')],
  )


def parse_match_stats(ms: dict) -> game_state_pb2.MatchStats:
  return game_state_pb2.MatchStats(**ms)


def parse_player_state(ps: dict) -> game_state_pb2.PlayerState:
  return game_state_pb2.PlayerState(**ps)


def parse_allplayers_entry(steam_id: str, player: dict) ->\
    game_state_pb2.ThinPlayer:
  team = TEAMS[player['team']] if 'team' in player else None
  match_stats = parse_match_stats(player['match_stats']) \
    if 'match_stats' in player else None
  state = parse_player_state(player['state']) \
    if 'state' in player else None
  player = game_state_pb2.ThinPlayer(
      steam_id=int(steam_id),
      name=player.get('name'),
      observer_slot=player.get('observer_slot'),
      team=team, match_stats=match_stats, state=state,
  )
  return player


def parse_previously(previously: dict) -> game_state_pb2.Previously:
  oneof_fields = {}

  if previously.get('allplayers'):
    oneof_fields['allplayers_present'] = True
  elif 'allplayers' in previously:
    oneof_fields['allplayers'] = game_state_pb2.PreviousAllPlayers(allplayers=[
      parse_allplayers_entry(steam_id, allplayers_entry)
      for steam_id, allplayers_entry in previously['allplayers'].items()
    ])

  if previously.get('round'):
    oneof_fields['round_present'] = True
  elif 'round' in previously:
    oneof_fields['round'] = parse_round(previously['round'])

  return game_state_pb2.Previously(
      map=parse_map(previously.get('map')),
      player=parse_player(previously.get('player')),
      **oneof_fields,
  )


def parse_player_added(paj: dict) -> game_state_pb2.PlayerAdded:
  return game_state_pb2.PlayerAdded(
      clan=paj.get('clan'),
      observer_slot=paj.get('observer_slot'),
      team=paj.get('team'),
      match_stats=paj.get('match_stats') is True,
      state=paj.get('state') is True,
  )


def parse_added(added: dict) -> game_state_pb2.Added:
  player_added = parse_player_added(added['player']) \
    if 'player' in added else None
  return game_state_pb2.Added(player=player_added)


def parse_game_state(gs_json: dict) -> game_state_pb2.GameState:
  """Deserialize a JSON-formatted game state to protobuf."""

  if 'provider' not in gs_json:
    raise InvalidGameStateException(gs_json)

  try:
    map_ = parse_map(gs_json.get('map'))
    provider = parse_provider(gs_json['provider'])
    round_ = parse_round(gs_json.get('round'))
    player = parse_player(gs_json['player'])
    allplayers = [
      parse_allplayers_entry(steam_id, allplayers_entry)
      for steam_id, allplayers_entry in gs_json.get('allplayers', {}).items()
    ]
    previously = parse_previously(gs_json['previously']) \
      if 'previously' in gs_json else None
    added = parse_added(gs_json['added']) if 'added' in gs_json else None
    return game_state_pb2.GameState(
        provider=provider, map=map_, round=round_, player=player,
        allplayers=allplayers, previously=previously, added=added)
  except DeserializationError as e:
    logger.error('Failed to deserialize game_state: %s', json.dumps(gs_json))
    raise e
