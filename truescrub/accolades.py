import collections
import configparser
import numbers
from importlib.resources import files
from typing import Dict, List, Tuple, Iterator, OrderedDict

from truescrub.db import KILL_COEFF, DEATH_COEFF, DAMAGE_COEFF, INTERCEPT


def parse_high_low(high_low: str) -> bool:
  """Parse 'highest' or 'lowest' strings into boolean values (True for highest, False for lowest)"""
  if high_low == 'highest':
    return True
  if high_low == 'lowest':
    return False
  raise ValueError('Invalid spec: ' + str(high_low))


def split_condition(condition: List[str]) -> Iterator[Tuple[str, bool]]:
  """Split a condition like 'highest mvps' into a (attribute, highest) tuple"""
  for token in condition:
    high_low, attribute = token.split()
    yield attribute, parse_high_low(high_low)


def parse_accolade(spec: str) -> Dict[str, bool]:
  """Parse an accolade specification into a dictionary of attribute conditions"""
  return dict(split_condition(spec.split(' and ')))


def parse_condition(label: str) -> Tuple[str, bool]:
  """Parse a condition label into an (attribute, highest) tuple"""
  high_low, attribute = label.split()
  return attribute, parse_high_low(high_low)


def parse_accolades(resource_string: str) -> Tuple[
  OrderedDict, Dict[Tuple[str, bool], str]]:
  """
  Parse the accolades.ini configuration into structured data

  Args:
      resource_string: The contents of accolades.ini

  Returns:
      A tuple of (accolades, condition_formats) where:
      - accolades is an OrderedDict mapping accolade names to condition dictionaries
      - condition_formats is a dictionary mapping (attribute, high_low) tuples to format strings
  """
  parser = configparser.RawConfigParser()
  parser.optionxform = str  # Preserve case in keys
  parser.read_string(resource_string)

  # Parse accolades in order (important as higher ones get priority)
  accolades = collections.OrderedDict()
  for key, value in parser.items('Accolades'):
    accolades[key] = parse_accolade(value)

  # Parse condition format strings
  conditions = {
    parse_condition(key): format_string
    for key, format_string in parser.items('Conditions')
  }

  return accolades, conditions


# Load the accolades configuration
ACCOLADES, CONDITIONS = parse_accolades(
  files(__name__).joinpath('accolades.ini').read_bytes().decode('UTF-8'))


def compute_expected_rating(rating_details: Dict) -> float:
  return (
      KILL_COEFF * rating_details['average_kills'] +
      DEATH_COEFF * rating_details['average_deaths'] +
      DAMAGE_COEFF * rating_details['average_damage'] +
      INTERCEPT
  )


def evaluate_conditions(player_ratings: List[Dict]) -> Dict[int, Dict[str, bool]]:
  """
  Determine which conditions each player meets, based on their performance.

  Args:
      player_ratings: List of player rating dictionaries from highlights.get_highlights()

  Returns:
      Dictionary mapping player_id to a dictionary of satisfied conditions
  """
  # Extract player stats for easier comparison
  player_stats = {}
  attribute_values = collections.defaultdict(list)

  # First pass: collect all stats and calculate derived metrics
  for player in player_ratings:
    player_id = player['player_id']
    stats = derive_player_stats(player)
    player_stats[player_id] = stats

    # Collect values for ranking
    for attr, value in stats.items():
      if isinstance(value, numbers.Number):
        attribute_values[attr].append((player_id, value))

  # Find the highest and lowest for each attribute
  attribute_rankings = {}
  for attr, values in attribute_values.items():
    if not values:
      continue

    # Get highest
    highest_id = max(values, key=lambda x: x[1])[0]
    attribute_rankings[(attr, True)] = highest_id

    # Get lowest
    lowest_id = min(values, key=lambda x: x[1])[0]
    attribute_rankings[(attr, False)] = lowest_id

  # Convert rankings to conditions for each player
  player_conditions = collections.defaultdict(dict)
  for (attr, high_low), player_id in attribute_rankings.items():
    player_conditions[player_id][attr] = high_low

  return player_conditions


def derive_player_stats(player):
  player_id = player['player_id']
  expected_rating = compute_expected_rating(player['rating_details'])
  stats = dict(player_id=player_id, rating=player['impact_rating'],
               mvps=player['mvps'], expected_rating=expected_rating,
               kills=player['rating_details']['average_kills'],
               deaths=player['rating_details']['average_deaths'],
               damage=player['rating_details']['average_damage'],
               assists=player['rating_details']['average_assists'],
               impact=player['impact_rating'])
  stats['overratedness'], stats['underratedness'] = \
    compute_rating_surprise(expected_rating, player['impact_rating'])

  return stats


def compute_rating_surprise(expected_rating, actual_rating):
  if actual_rating > expected_rating:
    # Player is underrated (better than expected)
    excess_rating = (actual_rating - expected_rating)
    return 0, 100 * excess_rating / max(0.001, expected_rating)
  else:
    # Player is overrated (worse than expected)
    excess_rating = (expected_rating - actual_rating)
    return 100 * excess_rating / max(0.001, expected_rating), 0


def compute_accolades(triggered_conditions: Dict[int, Dict[str, bool]]) -> \
    Iterator[Tuple[str, int]]:
  """
  Assign accolades to players based on which conditions they meet.
  Accolades are assigned in priority order, with each player getting at most one accolade.

  Args:
      triggered_conditions: Dictionary mapping player_id to conditions they meet

  Returns:
      Iterator of (accolade_name, player_id) pairs
  """
  consumed_attributes = set()
  assigned_players = set()

  for accolade_name, accolade_spec in ACCOLADES.items():
    accolade_conditions = set(accolade_spec.items())

    if len(accolade_conditions & consumed_attributes) > 0:
      continue

    for player_id, player_conditions in triggered_conditions.items():
      if player_id in assigned_players:
        continue

      if accolade_conditions.issubset(set(player_conditions.items())):
        consumed_attributes |= accolade_conditions
        assigned_players.add(player_id)
        yield accolade_name, player_id


def format_accolades(
    accolades: Iterator[Tuple[str, int]],
    player_ratings: List[Dict]) -> Iterator[Dict]:
  """
  Format accolades for display with detailed information.

  Args:
      accolades: List of (accolade_name, player_id) pairs
      player_ratings: List of player rating dictionaries

  Returns:
      Iterator of formatted accolade dictionaries
  """

  player_map = {p['player_id']: p for p in player_ratings}
  player_stats = {
    player['player_id']: derive_player_stats(player)
    for player in player_ratings
  }

  for accolade_name, player_id in accolades:
    player = player_map[player_id]
    stats = player_stats[player_id]
    accolade_spec = ACCOLADES[accolade_name]

    details = [
      CONDITIONS[condition_key].format(**stats)
      for condition_key in accolade_spec.items()
      if condition_key in CONDITIONS
    ]

    yield {
      'accolade': accolade_name,
      'player_id': player_id,
      'player_name': player['steam_name'],
      'details': details
    }


def get_accolades(player_ratings: List[Dict]) -> Iterator[dict]:
  """
  Generate accolades based on player ratings from highlights.get_highlights().

  Args:
      player_ratings: List of player rating dictionaries from the highlights module

  Returns:
      List of accolade dictionaries with formatting for display
  """

  triggered_conditions = evaluate_conditions(player_ratings)
  awarded_accolades = compute_accolades(triggered_conditions)
  return format_accolades(awarded_accolades, player_ratings)
