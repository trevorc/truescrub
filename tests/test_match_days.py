import datetime

import pytest

from tests.db_test_utils import TestDBManager, create_game_state_for_round
from truescrub.db import get_match_days


@pytest.fixture
def populated_db():
  db_manager = TestDBManager()

  ct_team = [(1, 'Player1'), (2, 'Player2')]
  t_team = [(3, 'Player3')]

  game_states = []

  # Day 1: 2022-01-15 (UTC)
  day1 = datetime.datetime(2022, 1, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
  game_states.append(create_game_state_for_round(
    timestamp=day1, map_name='de_dust2', ct_team=ct_team, t_team=t_team,
    winner='CT',
    player_stats={1: {'kills': 1, 'assists': 0, 'deaths': 0, 'damage': 100,
                      'survived': True, 'match_mvps': 1, 'mvp': True},
                  2: {'kills': 0, 'assists': 1, 'deaths': 0, 'damage': 50,
                      'survived': True, 'match_mvps': 0, 'mvp': False},
                  3: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0,
                      'survived': False, 'match_mvps': 0, 'mvp': False}}
  ))

  # Day 2: 2022-01-16 (UTC)
  day2 = datetime.datetime(2022, 1, 16, 12, 0, 0, tzinfo=datetime.timezone.utc)
  game_states.append(create_game_state_for_round(
    timestamp=day2, map_name='de_inferno', ct_team=ct_team, t_team=t_team,
    winner='T',
    player_stats={
      1: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0, 'survived': False,
          'match_mvps': 1, 'mvp': False},
      2: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0, 'survived': False,
          'match_mvps': 0, 'mvp': False},
      3: {'kills': 2, 'assists': 0, 'deaths': 0, 'damage': 200,
          'survived': True, 'match_mvps': 1, 'mvp': True}}
  ))

  # Day 3: 2022-01-17 (UTC)
  day3 = datetime.datetime(2022, 1, 17, 2, 0, 0, tzinfo=datetime.timezone.utc)
  game_states.append(create_game_state_for_round(
    timestamp=day3, map_name='de_mirage', ct_team=ct_team, t_team=t_team,
    winner='CT',
    player_stats={1: {'kills': 1, 'assists': 0, 'deaths': 0, 'damage': 100,
                      'survived': True, 'match_mvps': 2, 'mvp': True},
                  2: {'kills': 0, 'assists': 1, 'deaths': 0, 'damage': 50,
                      'survived': True, 'match_mvps': 0, 'mvp': False},
                  3: {'kills': 0, 'assists': 0, 'deaths': 1, 'damage': 0,
                      'survived': False, 'match_mvps': 1, 'mvp': False}}
  ))

  db_manager.add_game_states(game_states)
  db_manager.process_game_states()
  yield db_manager.skill_db
  db_manager.close()


def test_get_match_days_utc(populated_db):
  days = get_match_days(populated_db, datetime.timezone.utc)

  assert days == [
    datetime.date(2022, 1, 17),
    datetime.date(2022, 1, 16),
    datetime.date(2022, 1, 15),
  ]


def test_get_match_days_offset_timezone(populated_db):
  tz = datetime.timezone(datetime.timedelta(hours=-5))
  days = get_match_days(populated_db, tz)

  assert days == [
    datetime.date(2022, 1, 16),
    datetime.date(2022, 1, 15),
  ]


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
