"""
Unit tests for truescrub.updater.state_parser.

Tests the core game-state → round-data parsing logic without any database
interaction.
"""
import datetime

import pytest

from truescrub.models import GameStateRow
from truescrub.updater.state_parser import (
  parse_round_stats,
  parse_mvp,
  parse_freezetime_transition,
  parse_roundover_transition,
  parse_game_states,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name, team, kills=0, assists=0, deaths=0, damage=0,
                 health=100, mvps=0, weapons=None):
  """Build a single allplayers entry."""
  return {
    'name': name,
    'team': team,
    'observer_slot': 1,
    'match_stats': {
      'kills': kills,
      'assists': assists,
      'deaths': deaths,
      'mvps': mvps,
      'score': kills * 2 + assists,
    },
    'state': {
      'health': health,
      'armor': 100,
      'helmet': False,
      'flashed': 0,
      'burning': 0,
      'money': 800,
      'round_kills': kills,
      'round_killhs': 0,
      'round_totaldmg': damage,
      'equip_value': 200,
    },
    'weapons': weapons or {
      '0': {'name': 'weapon_knife'},
      '1': {'name': 'weapon_glock'},
      '2': {'name': 'weapon_ak47'},
    },
  }


SEASON_IDS = {datetime.date(2020, 1, 1): 1}

# A round in January 2022, well after the only season start
_TS = int(datetime.datetime(2022, 6, 15, 12, 0, 0,
                            tzinfo=datetime.timezone.utc).timestamp())


def _roundover_state(allplayers, previous_allplayers=None, win_team='CT',
                     map_phase='live', game_state_id=1):
  """Build a GameStateRow that represents a round-over transition."""
  import json
  return GameStateRow(
    game_state_id=game_state_id,
    round_phase='over',
    map_name='de_dust2',
    map_phase=map_phase,
    win_team=win_team,
    timestamp=_TS,
    allplayers=json.dumps(allplayers),
    previous_allplayers=json.dumps(previous_allplayers)
    if previous_allplayers is not None else None,
  )


def _freezetime_state(allplayers, game_state_id=2):
  import json
  return GameStateRow(
    game_state_id=game_state_id,
    round_phase='live',
    map_name='de_dust2',
    map_phase='live',
    win_team='',
    timestamp=_TS,
    allplayers=json.dumps(allplayers),
    previous_allplayers=None,
  )


# ---------------------------------------------------------------------------
# parse_round_stats
# ---------------------------------------------------------------------------

class TestParseRoundStats:
  def test_extracts_kills_damage_survived(self):
    allplayers = {
      '111': _make_player('A', 'CT', kills=3, damage=200, health=50),
      '222': _make_player('B', 'T', kills=0, damage=30, health=0),
    }
    stats = parse_round_stats(allplayers)

    assert stats[111]['kills'] == 3
    assert stats[111]['damage'] == 200
    assert stats[111]['survived'] is True
    assert stats[222]['kills'] == 0
    assert stats[222]['damage'] == 30
    assert stats[222]['survived'] is False

  def test_match_assists_captured(self):
    allplayers = {
      '111': _make_player('A', 'CT', assists=5),
    }
    stats = parse_round_stats(allplayers)
    assert stats[111]['match_assists'] == 5


# ---------------------------------------------------------------------------
# parse_mvp
# ---------------------------------------------------------------------------

class TestParseMvp:
  def test_identifies_mvp_by_delta(self):
    allplayers = {
      '111': _make_player('A', 'CT', mvps=2),
      '222': _make_player('B', 'CT', mvps=1),
    }
    previous = {
      '111': _make_player('A', 'CT', mvps=1),
      '222': _make_player('B', 'CT', mvps=1),
    }
    state = _roundover_state(allplayers, previous)
    assert parse_mvp(state) == 111

  def test_returns_none_when_no_previous_data(self):
    allplayers = {
      '111': _make_player('A', 'CT', mvps=1),
    }
    state = _roundover_state(allplayers, previous_allplayers={})
    assert parse_mvp(state) is None

  def test_returns_none_when_no_delta(self):
    allplayers = {
      '111': _make_player('A', 'CT', mvps=1),
    }
    previous = {
      '111': _make_player('A', 'CT', mvps=1),
    }
    state = _roundover_state(allplayers, previous)
    assert parse_mvp(state) is None


# ---------------------------------------------------------------------------
# parse_freezetime_transition
# ---------------------------------------------------------------------------

class TestParseFreezetime:
  def test_detects_primary_weapons(self):
    allplayers = {
      '111': _make_player('A', 'CT', weapons={
        '0': {'name': 'weapon_knife'},
        '1': {'name': 'weapon_usp_silencer'},
        '2': {'name': 'weapon_m4a1'},
      }),
    }
    state = _freezetime_state(allplayers)
    weapons = parse_freezetime_transition(state)
    assert weapons[111]['primary'] == 'weapon_m4a1'
    assert weapons[111]['secondary'] == 'weapon_usp_silencer'

  def test_rejects_non_live_phase(self):
    import json
    state = GameStateRow(
      game_state_id=1,
      round_phase='over',
      map_name='de_dust2',
      map_phase='live',
      win_team='CT',
      timestamp=_TS,
      allplayers=json.dumps({}),
      previous_allplayers=None,
    )
    with pytest.raises(ValueError, match='Expected round_phase "live"'):
      parse_freezetime_transition(state)


# ---------------------------------------------------------------------------
# parse_roundover_transition
# ---------------------------------------------------------------------------

class TestParseRoundoverTransition:
  def _two_team_players(self):
    return {
      '100': _make_player('P1', 'CT', kills=2, damage=100),
      '200': _make_player('P2', 'CT', kills=1, damage=80),
      '300': _make_player('P3', 'T', kills=0, damage=50, health=0),
    }

  def test_basic_round_parsing(self):
    allplayers = self._two_team_players()
    previous = {
      '100': _make_player('P1', 'CT', mvps=0),
      '200': _make_player('P2', 'CT', mvps=0),
      '300': _make_player('P3', 'T', mvps=0),
    }
    state = _roundover_state(allplayers, previous, win_team='CT')
    result = parse_roundover_transition(SEASON_IDS, state)
    assert result is not None

    new_round, player_states = result
    assert new_round['winner'] == tuple(sorted([100, 200]))
    assert new_round['loser'] == (300,)
    assert new_round['map_name'] == 'de_dust2'
    assert new_round['season_id'] == 1
    assert len(player_states) == 3

  def test_returns_none_with_single_team(self):
    """If all players are on one team, the round should be skipped."""
    allplayers = {
      '100': _make_player('P1', 'CT'),
      '200': _make_player('P2', 'CT'),
    }
    state = _roundover_state(allplayers, {}, win_team='CT')
    assert parse_roundover_transition(SEASON_IDS, state) is None

  def test_filters_unconnected_players(self):
    allplayers = {
      '100': _make_player('P1', 'CT', kills=1),
      '200': _make_player('unconnected', 'T'),
      '300': _make_player('P3', 'T', kills=0),
    }
    state = _roundover_state(allplayers, {}, win_team='CT')
    result = parse_roundover_transition(SEASON_IDS, state)
    assert result is not None
    new_round, player_states = result
    # 'unconnected' should be filtered out
    player_ids = {ps['steam_id'] for ps in player_states}
    assert 200 not in player_ids

  def test_last_round_flag_gameover(self):
    allplayers = self._two_team_players()
    state = _roundover_state(allplayers, {}, win_team='CT',
                             map_phase='gameover')
    result = parse_roundover_transition(SEASON_IDS, state)
    assert result[0]['last_round'] is True

  def test_last_round_flag_live(self):
    allplayers = self._two_team_players()
    state = _roundover_state(allplayers, {}, win_team='CT',
                             map_phase='live')
    result = parse_roundover_transition(SEASON_IDS, state)
    assert result[0]['last_round'] is False


# ---------------------------------------------------------------------------
# parse_game_states (integration of above)
# ---------------------------------------------------------------------------

class TestParseGameStates:
  def test_processes_multiple_rounds(self):
    allplayers = {
      '100': _make_player('P1', 'CT', kills=1),
      '200': _make_player('P2', 'T', kills=0, health=0),
    }
    states = [
      _roundover_state(allplayers, {}, win_team='CT', game_state_id=1),
      _roundover_state(allplayers, {}, win_team='CT', game_state_id=2),
      _roundover_state(allplayers, {}, win_team='CT', game_state_id=3),
    ]
    result = parse_game_states(states, SEASON_IDS)
    assert len(result.rounds) == 3
    assert result.max_game_state_id == 3
    # 2 players × 3 rounds = 6 player-state records
    assert len(result.player_states) == 6

  def test_skips_invalid_rounds(self):
    """Single-team rounds are filtered out."""
    one_team = {
      '100': _make_player('P1', 'CT'),
      '200': _make_player('P2', 'CT'),
    }
    two_teams = {
      '100': _make_player('P1', 'CT', kills=1),
      '300': _make_player('P3', 'T', kills=0, health=0),
    }
    states = [
      _roundover_state(one_team, {}, win_team='CT', game_state_id=1),
      _roundover_state(two_teams, {}, win_team='CT', game_state_id=2),
    ]
    result = parse_game_states(states, SEASON_IDS)
    assert len(result.rounds) == 1
    assert result.rounds[0]['game_state_id'] == 2


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
