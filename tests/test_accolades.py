import pytest
import sys

from truescrub.accolades import (
  parse_high_low, parse_accolade, parse_condition, parse_accolades,
  compute_expected_rating, evaluate_conditions, compute_accolades,
  format_accolades, get_accolades
)


def test_parse_high_low():
  assert parse_high_low("highest") == True
  assert parse_high_low("lowest") == False

  with pytest.raises(ValueError):
    parse_high_low("invalid")


def test_parse_accolade():
  accolade_spec = "highest mvps and lowest deaths"
  parsed = parse_accolade(accolade_spec)

  assert parsed == {
    "mvps": True,
    "deaths": False
  }


def test_parse_condition():
  condition = "highest rating"
  attribute, high_low = parse_condition(condition)

  assert attribute == "rating"
  assert high_low == True


def test_parse_accolades():
  config_string = """
[Accolades]
Test Accolade = highest rating and lowest deaths
Another Accolade = highest mvps

[Conditions]
highest rating = {rating:.2f} Impact Rating
highest mvps = {mvps:d} MVPs
lowest deaths = {deaths:.2f} Deaths
"""
  accolades, conditions = parse_accolades(config_string)

  assert len(accolades) == 2
  assert "Test Accolade" in accolades
  assert "Another Accolade" in accolades

  assert accolades["Test Accolade"] == {"rating": True, "deaths": False}
  assert accolades["Another Accolade"] == {"mvps": True}

  assert len(conditions) == 3
  assert ("rating", True) in conditions
  assert ("mvps", True) in conditions
  assert ("deaths", False) in conditions


def test_calculate_expected_rating():
  player_stats = {
    'rating_details': {
      'average_kills': 2.5,
      'average_deaths': 0.2,
      'average_damage': 150.0,
      'average_assists': 1.0
    }
  }

  expected_rating = compute_expected_rating(player_stats['rating_details'])
  assert isinstance(expected_rating, float)
  assert expected_rating > 0


def test_test_conditions():
  player_ratings = [
    {
      'player_id': 1,
      'steam_name': 'Player1',
      'impact_rating': 1.5,
      'mvps': 10,
      'rating_details': {
        'average_kills': 2.5,
        'average_deaths': 0.8,
        'average_damage': 120.0,
        'average_assists': 1.0,
        'total_kills': 25,
        'total_deaths': 8,
      }
    },
    {
      'player_id': 2,
      'steam_name': 'Player2',
      'impact_rating': 0.8,
      'mvps': 2,
      'rating_details': {
        'average_kills': 1.2,
        'average_deaths': 2.5,
        'average_damage': 80.0,
        'average_assists': 3.0,
        'total_kills': 12,
        'total_deaths': 25,
      }
    },
  ]

  conditions = evaluate_conditions(player_ratings)

  assert 1 in conditions
  assert 2 in conditions

  assert conditions[1]['mvps']
  assert conditions[1]['rating']
  assert conditions[1]['kills']

  assert conditions[2]['deaths']
  assert conditions[2]['assists']


def test_compute_accolades(monkeypatch):
  mock_accolades = {
    "Test Accolade 1": {"mvps": True, "rating": True},
    "Test Accolade 2": {"deaths": True, "assists": True},
    "Test Accolade 3": {"mvps": True}
  }

  triggered_conditions = {
    1: {"mvps": True, "rating": True, "kills": True},
    2: {"deaths": True, "assists": True, "total_deaths": True}
  }

  # Patch the ACCOLADES global
  monkeypatch.setattr("truescrub.accolades.ACCOLADES", mock_accolades)

  # Run compute_accolades
  accolades = list(compute_accolades(triggered_conditions))

  assert len(accolades) == 2
  assert accolades[0] == ("Test Accolade 1", 1)
  assert accolades[1] == ("Test Accolade 2", 2)


def test_format_accolades(monkeypatch):
  player_ratings = [
    {
      'player_id': 1,
      'steam_name': 'Player1',
      'impact_rating': 1.5,
      'mvps': 10,
      'rating_details': {
        'average_kills': 2.5,
        'average_deaths': 0.8,
        'average_damage': 120.0,
        'average_assists': 1.0,
      }
    },
    {
      'player_id': 2,
      'steam_name': 'Player2',
      'impact_rating': 0.8,
      'mvps': 2,
      'rating_details': {
        'average_kills': 1.2,
        'average_deaths': 2.5,
        'average_damage': 80.0,
        'average_assists': 3.0,
      }
    }
  ]

  mock_accolades = {
    "Test Accolade": {"rating": True},
    "Another Accolade": {"deaths": True}
  }

  mock_conditions = {
    ("rating", True): "{rating:.2f} Impact Rating",
    ("deaths", True): "Highest Deaths: {deaths:.2f}"
  }

  # Patch the globals
  monkeypatch.setattr("truescrub.accolades.ACCOLADES", mock_accolades)
  monkeypatch.setattr("truescrub.accolades.CONDITIONS", mock_conditions)

  # Format accolades
  accolades = [("Test Accolade", 1), ("Another Accolade", 2)]
  formatted = list(format_accolades(accolades, player_ratings))

  # Verify results
  assert len(formatted) == 2
  assert formatted[0]['accolade'] == "Test Accolade"
  assert formatted[0]['player_id'] == 1
  assert formatted[0]['player_name'] == "Player1"
  assert len(formatted[0]['details']) == 1
  assert "1.50 Impact Rating" in formatted[0]['details'][0]

  assert formatted[1]['accolade'] == "Another Accolade"
  assert formatted[1]['player_id'] == 2
  assert formatted[1]['player_name'] == "Player2"
  assert len(formatted[1]['details']) == 1
  assert "Highest Deaths: 2.50" in formatted[1]['details'][0]


def test_get_accolades(monkeypatch):
  def mock_test_conditions(player_ratings):
    if not player_ratings:
      return {}
    return {
      1: {"mvps": True, "rating": True},
      2: {"deaths": True, "assists": True}
    }

  def mock_compute_accolades(triggered_conditions):
    if not triggered_conditions:
      return []
    return [("Test Accolade", 1), ("Another Accolade", 2)]

  def mock_format_accolades(accolades, player_ratings):
    if not accolades:
      return []
    return [
      {
        'accolade': "Test Accolade",
        'player_id': 1,
        'player_name': "Player1",
        'details': ["1.50 Impact Rating"]
      },
      {
        'accolade': "Another Accolade",
        'player_id': 2,
        'player_name': "Player2",
        'details': ["Highest Deaths: 2.50"]
      }
    ]

  # Patch the functions
  monkeypatch.setattr("truescrub.accolades.evaluate_conditions",
                      mock_test_conditions)
  monkeypatch.setattr("truescrub.accolades.compute_accolades",
                      mock_compute_accolades)
  monkeypatch.setattr("truescrub.accolades.format_accolades",
                      mock_format_accolades)

  player_ratings = [
    {
      'player_id': 1,
      'steam_name': 'Player1',
      'impact_rating': 1.5,
      'mvps': 10,
      'rating_details': {'average_kills': 2.5}
    },
    {
      'player_id': 2,
      'steam_name': 'Player2',
      'impact_rating': 0.8,
      'mvps': 2,
      'rating_details': {'average_deaths': 2.5}
    }
  ]

  accolades = list(get_accolades(player_ratings))

  assert len(accolades) == 2
  assert accolades[0]['accolade'] == "Test Accolade"
  assert accolades[1]['accolade'] == "Another Accolade"
  assert list(get_accolades([])) == []


if __name__ == "__main__":
  sys.exit(pytest.main(["-xvs", __file__]))
