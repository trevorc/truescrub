import logging
from typing import Optional, Dict

from google.protobuf.timestamp_pb2 import Timestamp

from truescrub.proto import game_state_pb2
from truescrub.proto.game_state_pb2 import Weapon

logger = logging.getLogger(__name__)


def reverse_enum(enum, prefix: str) -> Dict[int, str]:
  tr = {}
  for name, value in enum.items():
    if not name.startswith(prefix):
      raise ValueError(f'{name} did not start with {prefix}')
    tr[value] = name[len(prefix):].lower()
  return tr


TEAMS = [None, 'T', 'CT']
ACTIVITIES = reverse_enum(game_state_pb2.Player.Activity, 'ACTIVITY_')
ROUND_PHASES = reverse_enum(game_state_pb2.Round.RoundPhase, 'ROUND_PHASE_')
BOMBS = reverse_enum(game_state_pb2.Round.Bomb, 'BOMB_')
MODES = reverse_enum(game_state_pb2.Mode, 'MODE_')
MAP_PHASES = reverse_enum(game_state_pb2.MapPhase, 'MAP_PHASE_')
WIN_CONDITIONS = reverse_enum(game_state_pb2.RoundWin.WinCondition,'WIN_CONDITION_')

WEAPON_TYPES = {
  Weapon.WeaponType.WEAPON_TYPE_C4: 'C4',
  Weapon.WeaponType.WEAPON_TYPE_GRENADE: 'Grenade',
  Weapon.WeaponType.WEAPON_TYPE_KNIFE: 'Knife',
  Weapon.WeaponType.WEAPON_TYPE_PISTOL: 'Pistol',
  Weapon.WeaponType.WEAPON_TYPE_RIFLE: 'Rifle',
  Weapon.WeaponType.WEAPON_TYPE_SHOTGUN: 'Shotgun',
  Weapon.WeaponType.WEAPON_TYPE_SNIPERRIFLE: 'SniperRifle',
  Weapon.WeaponType.WEAPON_TYPE_SUBMACHINE_GUN: 'Submachine Gun',
  Weapon.WeaponType.WEAPON_TYPE_MACHINE_GUN: 'Machine Gun',
  Weapon.WeaponType.WEAPON_TYPE_FISTS: 'Fists',
  Weapon.WeaponType.WEAPON_TYPE_TABLET: 'Tablet',
  Weapon.WeaponType.WEAPON_TYPE_STACKABLEITEM: 'StackableItem',
  Weapon.WeaponType.WEAPON_TYPE_MELEE: 'Melee',
  Weapon.WeaponType.WEAPON_TYPE_BREACH_CHARGE: 'Breach Charge',
  Weapon.WeaponType.WEAPON_TYPE_BUMP_MINE: 'Bump Mine',
}


def serialize_team_state(team_state: game_state_pb2.TeamState) -> dict:
  return {
    'score': team_state.score,
    'consecutive_round_losses': team_state.consecutive_round_losses,
    'timeouts_remaining': team_state.timeouts_remaining,
    'matches_won_this_series': team_state.matches_won_this_series,
  }


def serialize_map(map_: game_state_pb2.Map) -> Optional[dict]:
  data = {
    'mode': MODES[map_.mode],
    'name': map_.name,
    'phase': MAP_PHASES[map_.phase],
    'round': map_.round,
    'num_matches_to_win_series': map_.num_matches_to_win_series,
    'round_wins': dict((str(rw.round_num), WIN_CONDITIONS[rw.win_condition])
                       for rw in map_.round_wins),
    'current_spectators': map_.current_spectators,
    'souvenirs_total': map_.souvenirs_total,
  }

  if map_.HasField('team_ct'):
    data['team_ct'] = serialize_team_state(map_.team_ct)

  if map_.HasField('team_t'):
    data['team_t'] = serialize_team_state(map_.team_t)

  return data


def serialize_match_stats(match_stats: game_state_pb2.MatchStats) -> dict:
  return {
    'kills': match_stats.kills,
    'assists': match_stats.assists,
    'deaths': match_stats.deaths,
    'mvps': match_stats.mvps,
    'score': match_stats.score,
  }


ALWAYS_SERIALIZE = {
  'armor',
  'health',
  'helmet',
  'flashed',
  'smoked',
  'burning',
  'round_kills',
  'round_killhs',
  'round_totaldmg',
}


def serialize_player_state(ps_proto: game_state_pb2.PlayerState) -> dict:
  result = {
    field: getattr(ps_proto, field)
    for field in (
      'health',
      'armor',
      'helmet',
      'flashed',
      'smoked',
      'burning',
      'money',
      'round_kills',
      'round_killhs',
      'round_totaldmg',
      'equip_value',
      'defusekit',
    )
    if field in ALWAYS_SERIALIZE or getattr(ps_proto, field)
  }
    
  return result


def serialize_player(player_proto: game_state_pb2.Player) -> Optional[dict]:
  if player_proto.steam_id == '':
    return None

  activity_name = game_state_pb2.Player.Activity.Name(player_proto.activity)
  activity_prefix = 'ACTIVITY_'
  if activity_name.startswith(activity_prefix):
    activity_name = activity_name[len(activity_prefix):]

  data = {
    'steamid': str(player_proto.steam_id),
    'name': player_proto.name,
    'activity': activity_name.lower(),
  }
  team = TEAMS[player_proto.team]
  if team is not None:
    data['team'] = team

  if player_proto.observer_slot != 0:
    data['observer_slot'] = player_proto.observer_slot

  if player_proto.HasField('match_stats'):
    data['match_stats'] = serialize_match_stats(player_proto.match_stats)

  if player_proto.HasField('state'):
    data['state'] = serialize_player_state(player_proto.state)
  if player_proto.clan:
    data['clan'] = player_proto.clan
  return data


def serialize_provider(provider_proto: game_state_pb2.Provider) -> dict:
  return {
    'name': provider_proto.name,
    'appid': provider_proto.app_id,
    'version': provider_proto.version,
    'steamid': str(provider_proto.steam_id),
    'timestamp': provider_proto.timestamp.seconds,
  }


def serialize_round(round_proto: game_state_pb2.Round) -> Optional[dict]:
  data = {}
  win_team = TEAMS[round_proto.win_team]
  if win_team is not None:
    data['win_team'] = win_team
  if round_proto.phase != game_state_pb2.Round.ROUND_PHASE_UNSPECIFIED:
    data['phase'] = ROUND_PHASES[round_proto.phase]
  if round_proto.bomb != game_state_pb2.Round.BOMB_UNSPECIFIED:
    data['bomb'] = BOMBS[round_proto.bomb]
  return data


def serialize_weapon(weapon):
  data = {
    'name': weapon.name,
    'paintkit': weapon.paintkit,
    'state': 'active' if weapon.active else 'holstered',
  }
  if weapon.type != game_state_pb2.Weapon.WeaponType.WEAPON_TYPE_UNSPECIFIED:
    data['type'] = WEAPON_TYPES[weapon.type]
  if weapon.ammo_clip_max:
    data.update(
      ammo_clip=weapon.ammo_clip,
      ammo_clip_max=weapon.ammo_clip_max,
      ammo_reserve=weapon.ammo_reserve,
    )
  elif weapon.ammo_reserve:
    data['ammo_reserve'] = weapon.ammo_reserve
  return data


def serialize_weapons(weapons):
  return {
    field.name: serialize_weapon(getattr(weapons, field.name))
    for field in game_state_pb2.Weapons.DESCRIPTOR.fields
    if weapons.HasField(field.name)
  }


def serialize_allplayers_entry(player_proto: game_state_pb2.ThinPlayer) -> \
    tuple[str, dict]:
  data = {}
  team = TEAMS[player_proto.team]
  if team is not None:
    data['team'] = team
  if player_proto.name != '':
    data['name'] = player_proto.name
  if player_proto.HasField('match_stats'):
    data['match_stats'] = serialize_match_stats(player_proto.match_stats)
  if player_proto.HasField('state'):
    data['state'] = serialize_player_state(player_proto.state)
  if player_proto.observer_slot != 0:
    data['observer_slot'] = player_proto.observer_slot
  if player_proto.clan != '':
    data['clan'] = player_proto.clan
  if player_proto.HasField('weapons'):
    data['weapons'] = serialize_weapons(player_proto.weapons)

  return str(player_proto.steam_id), data


def serialize_previously(previously_proto: game_state_pb2.Previously) -> \
    Optional[dict]:
  data = {}
  if previously_proto.HasField('map'):
    data['map'] = serialize_map(previously_proto.map)
  if previously_proto.HasField('player'):
    data['player'] = serialize_player(previously_proto.player)

  if previously_proto.HasField(
      'allplayers') and previously_proto.allplayers.allplayers:
    data['allplayers'] = dict(serialize_allplayers_entry(p) for p in
                              previously_proto.allplayers.allplayers)
  elif (previously_proto.HasField('allplayers_present') and
        previously_proto.allplayers_present):
    data['allplayers'] = True

  if (previously_proto.HasField('round_present') and
      previously_proto.round_present):
    data['round'] = True
  elif previously_proto.HasField('round'):
    data['round'] = serialize_round(previously_proto.round)

  return data if len(data) > 0 else None


def serialize_player_added(pa_proto: game_state_pb2.PlayerAdded) -> dict:
  data = {}
  if pa_proto.observer_slot:
    data['observer_slot'] = pa_proto.observer_slot
  if pa_proto.team:
    data['team'] = pa_proto.team
  if pa_proto.match_stats:
    data['match_stats'] = True
  if pa_proto.state:
    data['state'] = True
  if pa_proto.clan:
    data['clan'] = pa_proto.clan
  return data


def serialize_added(added_proto: game_state_pb2.Added) -> Optional[dict]:
  if added_proto.HasField('player'):
    return {'player': serialize_player_added(added_proto.player)}
  return None


def serialize_game_state(gs_proto: game_state_pb2.GameState) -> dict:
  """Serialize a GameState protobuf object into the GSI JSON format."""
  data = {
    'provider': serialize_provider(gs_proto.provider),
  }
  if gs_proto.HasField('map'):
    data['map'] = serialize_map(gs_proto.map)
  if gs_proto.HasField('round'):
    data['round'] = serialize_round(gs_proto.round)
  serialized_player = serialize_player(gs_proto.player)
  if serialized_player:
    data['player'] = serialized_player
  if gs_proto.allplayers:
    data['allplayers'] = dict(
      serialize_allplayers_entry(p) for p in gs_proto.allplayers)
  if gs_proto.HasField('previously'):
    serialized_previously = serialize_previously(gs_proto.previously)
    if serialized_previously:
      data['previously'] = serialized_previously
  if gs_proto.HasField('added'):
    serialized_added = serialize_added(gs_proto.added)
    if serialized_added:
      data['added'] = serialized_added
  return data
