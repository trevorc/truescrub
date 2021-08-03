import pytest
import datetime
from truescrub.state_serialization import DeserializationError, json_to_proto

SAMPLE_GAME_STATE = {
  'added': {'map': {'round_wins': True}, 'round': {'win_team': True}},
  'allplayers': {
    '76561197970510532': {
      'match_stats': {
        'assists': 0,
        'deaths': 1,
        'kills': 0,
        'mvps': 0,
        'score': 0},
      'name': 'Defiler',
      'observer_slot': 2,
      'state': {'armor': 0,
                'burning': 0,
                'equip_value': 850,
                'flashed': 0,
                'health': 0,
                'helmet': False,
                'money': 2150,
                'round_killhs': 0,
                'round_kills': 0,
                'round_totaldmg': 0},
      'team': 'T'},
    '76561198121510237': {
      'match_stats': {'assists': 0,
                      'deaths': 0,
                      'kills': 1,
                      'mvps': 1,
                      'score': 2},
      'name': 'nonverba1',
      'observer_slot': 1,
      'state': {'armor': 100,
                'burning': 0,
                'equip_value': 850,
                'flashed': 0,
                'health': 100,
                'helmet': False,
                'money': 3200,
                'round_killhs': 1,
                'round_kills': 1,
                'round_totaldmg': 100},
      'team': 'CT'}},
  'map': {'current_spectators': 0,
          'mode': 'scrimcomp2v2',
          'name': 'de_shortnuke',
          'num_matches_to_win_series': 0,
          'phase': 'live',
          'round': 1,
          'round_wins': {'1': 'ct_win_elimination'},
          'souvenirs_total': 0,
          'team_ct': {'consecutive_round_losses': 0,
                      'matches_won_this_series': 0,
                      'score': 0,
                      'timeouts_remaining': 1},
          'team_t': {'consecutive_round_losses': 1,
                     'matches_won_this_series': 0,
                     'score': 0,
                     'timeouts_remaining': 1}},
  'player': {'activity': 'playing',
             'match_stats': {'assists': 0,
                             'deaths': 1,
                             'kills': 0,
                             'mvps': 0,
                             'score': 0},
             'name': 'Defiler',
             'observer_slot': 2,
             'state': {'armor': 0,
                       'burning': 0,
                       'equip_value': 850,
                       'flashed': 0,
                       'health': 0,
                       'helmet': False,
                       'money': 2150,
                       'round_killhs': 0,
                       'round_kills': 0,
                       'round_totaldmg': 0,
                       'smoked': 0},
             'steamid': '76561197970510532',
             'team': 'T'},
  'previously': {
    'allplayers': {
      '76561197970510532': {'match_stats': {'deaths': 0},
                            'state': {'armor': 100,
                                      'health': 100,
                                      'money': 150}},
      '76561198121510237': {'match_stats': {'kills': 0,
                                            'mvps': 0,
                                            'score': 0},
                            'state': {'money': 150,
                                      'round_killhs': 0,
                                      'round_kills': 0,
                                      'round_totaldmg': 0}}},
    'map': {'round': 0, 'team_t': {'consecutive_round_losses': 0}},
    'player': {'match_stats': {'deaths': 0},
               'state': {'armor': 100,
                         'health': 100,
                         'money': 150}},
    'round': {'phase': 'live'}},
  'provider': {'appid': 730,
               'name': 'Counter-Strike: Global Offensive',
               'steamid': '76561198413889827',
               'timestamp': 1557535071,
               'version': 13694},
  'round': {'phase': 'over', 'win_team': 'CT'}
}


def test_invalid_json_fails():
  with pytest.raises(DeserializationError):
    json_to_proto({'map': {}})

  with pytest.raises(DeserializationError):
    json_to_proto({'provider': None})

  with pytest.raises(DeserializationError):
    json_to_proto({'provider': {'appid': 730, 'steamid': '123', 'version': 1}})


def test_json_to_proto():
  gs_proto = json_to_proto(SAMPLE_GAME_STATE)
  assert gs_proto.map.name == 'de_shortnuke'
  assert gs_proto.provider.timestamp.ToDatetime() == \
         datetime.datetime(2019, 5, 11, 0, 37, 51)


if __name__ == '__main__':
  raise SystemExit(pytest.main([__file__]))
