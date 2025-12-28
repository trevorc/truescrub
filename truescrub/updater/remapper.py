import configparser
from importlib.resources import files
from typing import Dict, Set


__all__ = ['apply_player_configurations', 'remap_rounds']


def parse_player_configuration(resource_string: str) \
    -> (Dict[str, Set[str]], Dict[str, str], Set[str]):
  parser = configparser.RawConfigParser()
  parser.optionxform = str
  parser.read_string(resource_string)
  roles = {}
  aliases = {}
  ignores = set()
  for key, value in parser.items('Players'):
    player_id, prop = key.split('.', 1)
    player_id = int(player_id)
    if prop == 'roles':
      roles.setdefault(player_id, set()).update(value.split(','))
    elif prop == 'aliases':
      for alias in value.split(','):
        aliases[int(alias)] = player_id
    elif prop == 'ignored':
      ignores.add(player_id)
  return roles, aliases, ignores


ROLES, ALIASES, IGNORES = parse_player_configuration(
    files(__name__).joinpath('players.ini').read_bytes().decode('UTF-8'))


def remap_player_ids(teammates):
  return tuple(sorted(
      teammate if teammate not in ALIASES else ALIASES[teammate]
      for teammate in teammates
      if teammate not in IGNORES
  ))


def remap_round_stats(round_stats: {int: dict}):
  # Assumes that a player and his aliases are in a round together
  return {
    (steam_id if steam_id not in ALIASES else ALIASES[steam_id]): stats
    for steam_id, stats in round_stats.items()
    if steam_id not in IGNORES
  }


def remap_player_state(player_state: dict) -> dict:
  player_state = player_state.copy()
  if player_state['steam_id'] in ALIASES:
    player_state['steam_id'] = ALIASES[player_state['steam_id']]
  player_state['teammates'] = remap_player_ids(player_state['teammates'])
  return player_state


def remap_round(round: dict) -> dict:
  round = round.copy()
  round['winner'] = remap_player_ids(round['winner'])
  round['loser'] = remap_player_ids(round['loser'])
  round['stats'] = remap_round_stats(round['stats'])
  round['mvp'] = None \
    if round['mvp'] in IGNORES \
    else round['mvp'] if round['mvp'] not in ALIASES \
    else ALIASES[round['mvp']]
  return round


def remap_rounds(rounds: [dict]) -> [dict]:
  new_rounds = []
  for round in rounds:
    remapped_round = remap_round(round)
    if len(remapped_round['winner']) > 0 and \
        len(remapped_round['loser']) > 0:
      new_rounds.append(remapped_round)
  return new_rounds


def apply_player_configurations(player_states) -> [dict]:
  new_player_states = [
    remap_player_state(player_state)
    for player_state in player_states
    if player_state['steam_id'] not in IGNORES
  ]
  return new_player_states
