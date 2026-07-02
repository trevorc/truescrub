import json
import logging
from typing import Optional

from google.protobuf.json_format import ParseDict

from google.protobuf.timestamp_pb2 import Timestamp
from truescrub.proto import game_state_pb2


class DeserializationError(RuntimeError):
  pass


class InvalidGameStateException(RuntimeError):
  pass


class InvalidRoundException(RuntimeError):
  pass


class InvalidWeaponException(RuntimeError):
  pass


logger = logging.getLogger(__name__)


def translate_enum(enum, prefix):
  tr = {}
  for name, value in enum.items():
    if not name.startswith(prefix):
      raise ValueError(f'{name} did not start with {prefix}')
    tr[name[len(prefix):].lower()] = value
  return tr


TEAMS = {'T': 1, 'CT': 2}
ACTIVITIES = translate_enum(game_state_pb2.Player.Activity, 'ACTIVITY_')
ROUND_PHASES = translate_enum(game_state_pb2.Round.RoundPhase, 'ROUND_PHASE_')
BOMBS = translate_enum(game_state_pb2.Round.Bomb, 'BOMB_')
MODES = translate_enum(game_state_pb2.Mode, 'MODE_')
MAP_PHASES = translate_enum(game_state_pb2.MapPhase, 'MAP_PHASE_')
WIN_CONDITIONS = translate_enum(game_state_pb2.RoundWin.WinCondition,
                                'WIN_CONDITION_')
WEAPON_TYPES = translate_enum(game_state_pb2.Weapon.WeaponType, 'WEAPON_TYPE_')


def parse_team_state(ts_json: dict) -> game_state_pb2.TeamState:
  return ParseDict(ts_json, game_state_pb2.TeamState())


def parse_match_stats(ms: dict) -> game_state_pb2.MatchStats:
  return ParseDict(ms, game_state_pb2.MatchStats())


def parse_player_state(ps: dict) -> game_state_pb2.PlayerState:
  return ParseDict(ps, game_state_pb2.PlayerState())


def parse_round_win(round_num: str,
                    win_condition: str) -> game_state_pb2.RoundWin:
  if win_condition == '':
    raise InvalidRoundException(f'empty win condition for round {round_num}')
  return game_state_pb2.RoundWin(
    round_num=int(round_num),
    win_condition=WIN_CONDITIONS[win_condition])


def parse_map(map_json) -> game_state_pb2.Map:
  if map_json is None or map_json is True:
    return None
  try:
    mode = MODES[map_json['mode']] if 'mode' in map_json else None
    phase = MAP_PHASES[map_json['phase']] if 'phase' in map_json else None
    team_ct = parse_team_state(map_json['team_ct']) \
      if 'team_ct' in map_json else None
    team_t = parse_team_state(map_json['team_t']) \
      if 'team_t' in map_json else None
    round_wins = [
      parse_round_win(round_num, win_condition)
      for round_num, win_condition in map_json.get('round_wins', {}).items()
      if win_condition != ''
    ]
    return game_state_pb2.Map(
      mode=mode, name=map_json.get('name'), phase=phase,
      round=map_json.get('round'), team_ct=team_ct, team_t=team_t,
      num_matches_to_win_series=map_json.get('num_matches_to_win_series'),
      round_wins=round_wins,
    )
  except KeyError as e:
    raise DeserializationError(e)


def parse_player(player_json: Optional[dict]) -> Optional[
  game_state_pb2.Player]:
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
  try:
    phase = ROUND_PHASES[round_json['phase']] if 'phase' in round_json else None
    win_team = TEAMS[round_json['win_team']] \
      if 'win_team' in round_json else game_state_pb2.TEAM_UNSPECIFIED
    return game_state_pb2.Round(
      phase=phase, win_team=win_team,
      bomb=BOMBS[round_json.get('bomb', 'unspecified')],
    )
  except KeyError as e:
    raise DeserializationError(e)


def parse_weapon(weapon_json: dict) -> game_state_pb2.Weapon:
  try:
    weapon_type = WEAPON_TYPES[weapon_json['type'].lower().replace(' ', '_')] \
      if 'type' in weapon_json \
      else game_state_pb2.Weapon.WEAPON_TYPE_UNSPECIFIED
    return game_state_pb2.Weapon(
      ammo_clip=weapon_json.get('ammo_clip'),
      ammo_clip_max=weapon_json.get('ammo_clip_max'),
      ammo_reserve=weapon_json.get('ammo_reserve'),
      name=weapon_json.get('name'),
      paintkit=weapon_json.get('paintkit'),
      active=weapon_json.get('state') == 'active',
      type=weapon_type,
    )
  except KeyError as e:
    raise InvalidWeaponException(e)


def parse_weapons(weapons_json: dict) -> game_state_pb2.Weapons:
  return game_state_pb2.Weapons(**{
    key: parse_weapon(weapon_json)
    for key, weapon_json in weapons_json.items()
  })


def parse_allplayers_entry(steam_id: str, player: dict) -> \
    game_state_pb2.ThinPlayer:
  team = TEAMS.get(player.get('team'))
  match_stats = parse_match_stats(player['match_stats']) \
    if 'match_stats' in player and isinstance(player['match_stats'],
                                              dict) else None
  state = parse_player_state(player['state']) \
    if 'state' in player and isinstance(player['state'], dict) else None

  weapons = parse_weapons(
    player['weapons']) if 'weapons' in player and isinstance(player['weapons'],
                                                             dict) else None

  return game_state_pb2.ThinPlayer(
    steam_id=int(steam_id),
    name=player.get('name'),
    observer_slot=player.get('observer_slot'),
    clan=player.get('clan'),
    team=team,
    match_stats=match_stats,
    state=state,
    weapons=weapons,
  )


def parse_previously(previously: dict) -> game_state_pb2.Previously:
  oneof_fields = {}

  if previously.get('allplayers') is True:
    oneof_fields['allplayers_present'] = True
  elif isinstance(previously.get('allplayers'), dict):
    # Handle allplayers entries in the previously section, including clan info
    oneof_fields['allplayers'] = game_state_pb2.PreviousAllPlayers(allplayers=[
      parse_allplayers_entry(steam_id, allplayers_entry)
      for steam_id, allplayers_entry in previously['allplayers'].items()
    ])

  if previously.get('round') is True:
    oneof_fields['round_present'] = True
  elif isinstance(previously.get('round'), dict):
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
    player = parse_player(gs_json.get('player'))
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
