import pytest

from proto import highlights_service_pb2
from truescrub.accolades import (
  parse_high_low, parse_accolade, parse_condition, parse_accolades,
  compute_expected_rating, evaluate_conditions, compute_accolades,
  format_accolades, get_accolades
)


def test_parse_high_low():
  assert parse_high_low("highest")
  assert not parse_high_low("lowest")

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
  assert high_low


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
  player_stats = highlights_service_pb2.RatingDetails(
    average_kills=2.5,
    average_deaths=0.2,
    average_damage=150.0,
    average_assists=1.0
  )

  expected_rating = compute_expected_rating(player_stats)
  assert isinstance(expected_rating, float)
  assert expected_rating > 0


def test_test_conditions():
  player_ratings = [
    highlights_service_pb2.PlayerRating(
      player_id=1,
      steam_name='Player1',
      impact_rating=1.5,
      mvps=10,
      rating_details=highlights_service_pb2.RatingDetails(
        average_kills=2.5,
        average_deaths=0.8,
        average_damage=120.0,
        average_assists=1.0,
        total_kills=25,
        total_deaths=8,
      )
    ),
    highlights_service_pb2.PlayerRating(
      player_id=2,
      steam_name='Player2',
      impact_rating=0.8,
      mvps=2,
      rating_details=highlights_service_pb2.RatingDetails(
        average_kills=1.2,
        average_deaths=2.5,
        average_damage=80.0,
        average_assists=3.0,
        total_kills=12,
        total_deaths=25,
      )
    ),
  ]

  conditions = evaluate_conditions(player_ratings)

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

  monkeypatch.setattr("truescrub.accolades.ACCOLADES", mock_accolades)
  accolades = list(compute_accolades(triggered_conditions))

  assert len(accolades) == 2
  assert accolades[0] == ("Test Accolade 1", 1)
  assert accolades[1] == ("Test Accolade 2", 2)


def test_format_accolades(monkeypatch):
  player_ratings = [
    highlights_service_pb2.PlayerRating(
      player_id=1,
      steam_name='Player1',
      impact_rating=1.5,
      mvps=10,
      rating_details=highlights_service_pb2.RatingDetails(
        average_kills=2.5,
        average_deaths=0.8,
        average_damage=120.0,
        average_assists=1.0,
      )
    ),
    highlights_service_pb2.PlayerRating(
      player_id=2,
      steam_name='Player2',
      impact_rating=0.8,
      mvps=2,
      rating_details=highlights_service_pb2.RatingDetails(
        average_kills=1.2,
        average_deaths=2.5,
        average_damage=80.0,
        average_assists=3.0,
      )
    )
  ]

  mock_accolades = {
    "Test Accolade": {"rating": True},
    "Another Accolade": {"deaths": True}
  }

  mock_conditions = {
    ("rating", True): "{rating:.2f} Impact Rating",
    ("deaths", True): "Highest Deaths: {deaths:.2f}"
  }

  monkeypatch.setattr("truescrub.accolades.ACCOLADES", mock_accolades)
  monkeypatch.setattr("truescrub.accolades.CONDITIONS", mock_conditions)

  accolades = [("Test Accolade", 1), ("Another Accolade", 2)]
  formatted = list(format_accolades(accolades, player_ratings))

  assert len(formatted) == 2
  assert formatted[0].accolade == "Test Accolade"
  assert formatted[0].player_id == 1
  assert formatted[0].player_name == "Player1"
  assert len(formatted[0].details) == 1
  assert "1.50 Impact Rating" in formatted[0].details[0]

  assert formatted[1].accolade == "Another Accolade"
  assert formatted[1].player_id == 2
  assert formatted[1].player_name == "Player2"
  assert len(formatted[1].details) == 1
  assert "Highest Deaths: 2.50" in formatted[1].details[0]


def test_get_accolades(monkeypatch):
  def mock_evaluate_conditions(player_ratings):
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
      highlights_service_pb2.Accolade(
        accolade="Test Accolade",
        player_id=1,
        player_name="Player1",
        details=["1.50 Impact Rating"]
      ),
      highlights_service_pb2.Accolade(
        accolade="Another Accolade",
        player_id=2,
        player_name="Player2",
        details=["Highest Deaths: 2.50"]
      )
    ]

  monkeypatch.setattr("truescrub.accolades.evaluate_conditions",
                      mock_evaluate_conditions)
  monkeypatch.setattr("truescrub.accolades.compute_accolades",
                      mock_compute_accolades)
  monkeypatch.setattr("truescrub.accolades.format_accolades",
                      mock_format_accolades)

  player_ratings = [
    highlights_service_pb2.PlayerRating(
      player_id=1,
      steam_name='Player1',
      impact_rating=1.5,
      mvps=10,
      rating_details=highlights_service_pb2.RatingDetails(average_kills=2.5)
    ),
    highlights_service_pb2.PlayerRating(
      player_id=2,
      steam_name='Player2',
      impact_rating=0.8,
      mvps=2,
      rating_details=highlights_service_pb2.RatingDetails(average_deaths=2.5)
    )
  ]

  accolades = list(get_accolades(player_ratings))

  assert len(accolades) == 2
  assert accolades[0].accolade == "Test Accolade"
  assert accolades[1].accolade == "Another Accolade"
  assert list(get_accolades([])) == []


def _make_player(player_id, name, impact_rating, mvps,
                 avg_kills, avg_deaths, avg_damage, avg_assists,
                 rounds_played=10, avg_headshots=0.0):
  """Helper to build a PlayerRating protobuf with all required fields."""
  total_kills = int(avg_kills * rounds_played)
  total_deaths = int(avg_deaths * rounds_played)
  total_headshots = int(avg_headshots * rounds_played)
  return highlights_service_pb2.PlayerRating(
    player_id=player_id,
    steam_name=name,
    impact_rating=impact_rating,
    mvps=mvps,
    rounds_played=rounds_played,
    rating_details=highlights_service_pb2.RatingDetails(
      average_kills=avg_kills,
      average_deaths=avg_deaths,
      average_damage=avg_damage,
      average_assists=avg_assists,
      total_kills=total_kills,
      total_deaths=total_deaths,
      total_damage=int(avg_damage * rounds_played),
      total_assists=int(avg_assists * rounds_played),
      kdr=total_kills / max(1.0, total_deaths),
      average_headshots=avg_headshots,
      total_headshots=total_headshots,
    )
  )


class TestNewAccoladesTrigger:
  """Integration tests using the real ACCOLADES config to verify
  that each new accolade can actually fire given the right stats."""

  def test_glass_cannon_triggers(self):
    """Glass Cannon = highest damage AND highest deaths.
    Player must lead in both damage and deaths simultaneously."""
    players = [
      # Glass Cannon candidate: highest damage AND highest deaths
      _make_player(1, 'GlassGuy', 0.9, 0,
                   avg_kills=1.5, avg_deaths=3.0,
                   avg_damage=200.0, avg_assists=0.5),
      # Filler: moderate stats
      _make_player(2, 'Normal', 1.0, 1,
                   avg_kills=1.0, avg_deaths=1.0,
                   avg_damage=80.0, avg_assists=1.0),
    ]
    accolades = get_accolades(players)
    names = {a.accolade for a in accolades}
    assert 'Glass Cannon' in names
    gc = next(a for a in accolades if a.accolade == 'Glass Cannon')
    assert gc.player_id == 1

  def test_decoy_triggers(self):
    """Decoy = highest deaths AND highest assists.
    Player must lead in both deaths and assists simultaneously.
    We need a 3rd player to prevent Moral Support from consuming
    the decoy candidate (Moral Support needs lowest kills + lowest
    rating + highest deaths on the SAME player)."""
    players = [
      # Decoy candidate: highest deaths AND highest assists,
      # but NOT the lowest kills or rating
      _make_player(1, 'DecoyGuy', 0.7, 0,
                   avg_kills=1.5, avg_deaths=3.0,
                   avg_damage=50.0, avg_assists=4.0),
      # Normal player
      _make_player(2, 'Normal', 1.0, 1,
                   avg_kills=2.0, avg_deaths=1.0,
                   avg_damage=100.0, avg_assists=1.0),
      # This player has lowest kills and lowest rating,
      # breaking Moral Support's match on player 1
      _make_player(3, 'Lurker', 0.5, 0,
                   avg_kills=0.2, avg_deaths=2.0,
                   avg_damage=30.0, avg_assists=0.5),
    ]
    accolades = get_accolades(players)
    names = {a.accolade for a in accolades}
    assert 'Decoy' in names
    decoy = next(a for a in accolades if a.accolade == 'Decoy')
    assert decoy.player_id == 1

  def test_efficiency_expert_triggers(self):
    """Efficiency Expert = highest kdr.
    Player 1 must have the highest KDR without also being
    the lowest-deaths or highest-rating player, so earlier
    accolades don't consume them first."""
    players = [
      # Highest KDR: 4.0 kills / 1.0 deaths = 4.0 KDR
      # NOT lowest deaths (player 2 has 0.3)
      _make_player(1, 'Efficient', 1.0, 1,
                   avg_kills=4.0, avg_deaths=1.0,
                   avg_damage=120.0, avg_assists=1.0),
      # Grand Slamma Jamma target: highest rating + mvps + lowest deaths
      # KDR = 10/3 ≈ 3.3 — lower than player 1's 4.0
      _make_player(2, 'StarPlayer', 1.5, 5,
                   avg_kills=1.0, avg_deaths=0.3,
                   avg_damage=140.0, avg_assists=2.0),
      # Low performer
      _make_player(3, 'Sloppy', 0.6, 0,
                   avg_kills=0.5, avg_deaths=2.0,
                   avg_damage=40.0, avg_assists=0.5),
    ]
    accolades = get_accolades(players)
    names = {a.accolade for a in accolades}
    assert 'Efficiency Expert' in names, (
      f"Efficiency Expert missing, got: {[a.accolade for a in accolades]}")
    ee = next(a for a in accolades if a.accolade == 'Efficiency Expert')
    assert ee.player_id == 1

  def test_headshot_hunter_triggers(self):
    """Headshot Hunter = highest headshots.
    Need 3 players to prevent greedy multi-condition accolades
    from consuming all of player 1's conditions."""
    players = [
      # High headshot rate
      _make_player(1, 'Headshotter', 1.0, 1,
                   avg_kills=2.0, avg_deaths=1.0,
                   avg_damage=100.0, avg_assists=1.0,
                   avg_headshots=1.8),
      # Star player takes mvps/rating
      _make_player(2, 'StarPlayer', 1.5, 5,
                   avg_kills=2.5, avg_deaths=0.5,
                   avg_damage=140.0, avg_assists=2.0,
                   avg_headshots=0.5),
      # Low performer
      _make_player(3, 'Noob', 0.5, 0,
                   avg_kills=0.5, avg_deaths=2.0,
                   avg_damage=40.0, avg_assists=0.5,
                   avg_headshots=0.0),
    ]
    accolades = get_accolades(players)
    names = {a.accolade for a in accolades}
    assert 'Headshot Hunter' in names, (
      f"Headshot Hunter missing, got: {[a.accolade for a in accolades]}")
    hh = next(a for a in accolades if a.accolade == 'Headshot Hunter')
    assert hh.player_id == 1

  def test_wallflower_triggers(self):
    """Wallflower = lowest assists.
    Need 3 players so the Wallflower candidate isn't also
    the match for Moral Support or another greedy accolade."""
    players = [
      # Wallflower: lowest assists, but decent kills/rating
      _make_player(1, 'LoneWolf', 1.0, 1,
                   avg_kills=2.0, avg_deaths=1.0,
                   avg_damage=100.0, avg_assists=0.0),
      # Star player
      _make_player(2, 'StarPlayer', 1.5, 5,
                   avg_kills=2.5, avg_deaths=0.5,
                   avg_damage=140.0, avg_assists=2.0),
      # Low performer
      _make_player(3, 'Noob', 0.5, 0,
                   avg_kills=0.5, avg_deaths=2.0,
                   avg_damage=40.0, avg_assists=0.5),
    ]
    accolades = get_accolades(players)
    names = {a.accolade for a in accolades}
    assert 'Wallflower' in names, (
      f"Wallflower missing, got: {[a.accolade for a in accolades]}")
    wf = next(a for a in accolades if a.accolade == 'Wallflower')
    assert wf.player_id == 1

  def test_many_accolades_in_large_lobby(self):
    """With 6 players, many accolades should fire including new ones.
    Verifies that the priority ordering allows multiple accolades
    to coexist without consuming each other's conditions."""
    players = [
      # Player 1: Glass Cannon — highest damage AND highest deaths
      _make_player(1, 'GlassGuy', 0.6, 0,
                   avg_kills=1.5, avg_deaths=4.0,
                   avg_damage=250.0, avg_assists=0.5),
      # Player 2: Efficiency Expert — best KDR
      _make_player(2, 'Efficient', 1.3, 3,
                   avg_kills=3.5, avg_deaths=0.3,
                   avg_damage=160.0, avg_assists=1.5,
                   avg_headshots=2.5),
      # Player 3: Wallflower — lowest assists
      _make_player(3, 'WallGuy', 0.9, 0,
                   avg_kills=1.0, avg_deaths=1.0,
                   avg_damage=70.0, avg_assists=0.0),
      # Player 4: moderate stats
      _make_player(4, 'Average', 1.0, 1,
                   avg_kills=1.5, avg_deaths=1.5,
                   avg_damage=90.0, avg_assists=1.0,
                   avg_headshots=0.5),
      # Player 5: Low performer
      _make_player(5, 'Noob', 0.4, 0,
                   avg_kills=0.3, avg_deaths=2.0,
                   avg_damage=30.0, avg_assists=0.5,
                   avg_headshots=0.0),
      # Player 6: Tanky support
      _make_player(6, 'Support', 0.8, 0,
                   avg_kills=0.8, avg_deaths=1.5,
                   avg_damage=60.0, avg_assists=3.5,
                   avg_headshots=0.1),
    ]
    accolades = get_accolades(players)
    names = {a.accolade for a in accolades}

    # With 6 players and diverse stats, we expect several accolades
    assert len(accolades) >= 4, (
      f"Expected at least 4 accolades from 6 players, got {len(accolades)}: "
      f"{[a.accolade for a in accolades]}")

    # Glass Cannon should fire for player 1 (highest damage + highest deaths)
    assert 'Glass Cannon' in names, (
      f"Glass Cannon missing from: {[a.accolade for a in accolades]}")

    # Efficiency Expert or Headshot Hunter should fire for player 2
    p2_accolades = {a.accolade for a in accolades if a.player_id == 2}
    assert len(p2_accolades) > 0, (
      f"Player 2 should have an accolade, got: "
      f"{[a.accolade for a in accolades]}")


if __name__ == "__main__":
  raise SystemExit(pytest.main(["-xv", __file__]))
