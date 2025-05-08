import json
import datetime

import pytest
from truescrub.proto import game_state_pb2
from google.protobuf import text_format

from truescrub.statewriter.state_serialization import DeserializationError, \
  InvalidGameStateException, parse_game_state, parse_map

SAMPLE_GAME_STATE = json.loads('''
{
    "map": {
        "round_wins": {
            "1": "ct_win_elimination"
        },
        "mode": "scrimcomp2v2",
        "name": "de_shortnuke",
        "phase": "live",
        "round": 1,
        "team_ct": {
            "score": 0,
            "consecutive_round_losses": 0,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "team_t": {
            "score": 0,
            "consecutive_round_losses": 1,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "num_matches_to_win_series": 0,
        "current_spectators": 0,
        "souvenirs_total": 0
    },
    "player": {
        "steamid": "76561197970510532",
        "name": "Defiler",
        "observer_slot": 2,
        "team": "T",
        "activity": "playing",
        "match_stats": {
            "kills": 0,
            "assists": 0,
            "deaths": 1,
            "mvps": 0,
            "score": 0
        },
        "state": {
            "health": 0,
            "armor": 0,
            "helmet": false,
            "flashed": 0,
            "smoked": 0,
            "burning": 0,
            "money": 2150,
            "round_kills": 0,
            "round_killhs": 0,
            "round_totaldmg": 0,
            "equip_value": 850
        }
    },
    "provider": {
        "name": "Counter-Strike: Global Offensive",
        "appid": 730,
        "version": 13694,
        "steamid": "76561198413889827",
        "timestamp": 1557535071
    },
    "round": {
        "phase": "over",
        "win_team": "CT"
    },
    "allplayers": {
        "76561198121510237": {
            "name": "nonverba1",
            "observer_slot": 1,
            "team": "CT",
            "match_stats": {
                "kills": 1,
                "assists": 0,
                "deaths": 0,
                "mvps": 1,
                "score": 2
            },
            "state": {
                "health": 100,
                "armor": 100,
                "helmet": false,
                "flashed": 0,
                "burning": 0,
                "money": 3200,
                "round_kills": 1,
                "round_killhs": 1,
                "round_totaldmg": 100,
                "equip_value": 850
            }
        },
        "76561197970510532": {
            "name": "Defiler",
            "observer_slot": 2,
            "team": "T",
            "match_stats": {
                "kills": 0,
                "assists": 0,
                "deaths": 1,
                "mvps": 0,
                "score": 0
            },
            "state": {
                "health": 0,
                "armor": 0,
                "helmet": false,
                "flashed": 0,
                "burning": 0,
                "money": 2150,
                "round_kills": 0,
                "round_killhs": 0,
                "round_totaldmg": 0,
                "equip_value": 850
            }
        }
    },
    "previously": {
        "map": {
            "round": 0,
            "team_t": {
                "consecutive_round_losses": 0
            }
        },
        "player": {
            "match_stats": {
                "deaths": 0
            },
            "state": {
                "health": 100,
                "armor": 100,
                "money": 150
            }
        },
        "round": {
            "phase": "live"
        },
        "allplayers": {
            "76561198121510237": {
                "match_stats": {
                    "kills": 0,
                    "mvps": 0,
                    "score": 0
                },
                "state": {
                    "money": 150,
                    "round_kills": 0,
                    "round_killhs": 0,
                    "round_totaldmg": 0
                }
            },
            "76561197970510532": {
                "match_stats": {
                    "deaths": 0
                },
                "state": {
                    "health": 100,
                    "armor": 100,
                    "money": 150
                }
            }
        }
    },
    "added": {
        "map": {
            "round_wins": true
        },
        "round": {
            "win_team": true
        }
    }
}
''')


def test_invalid_json_fails():
  with pytest.raises(InvalidGameStateException):
    parse_game_state({'map': {}})

  with pytest.raises(DeserializationError):
    parse_game_state({'provider': None})

  with pytest.raises(DeserializationError):
    parse_game_state(
        {'provider': {'appid': 730, 'steamid': '123', 'version': 1}})


def test_warmup_map():
  actual = parse_map({
    'mode': 'scrimcomp2v2', 'name': 'de_shortnuke', 'phase': 'warmup',
    'round': 0,
    'team_ct': {
      'score': 0, 'consecutive_round_losses': 0, 'timeouts_remaining': 1,
      'matches_won_this_series': 0
    }, 'team_t': {
      'score': 0, 'consecutive_round_losses': 0,
      'timeouts_remaining': 1, 'matches_won_this_series': 0},
    'num_matches_to_win_series': 0, 'current_spectators': 0,
    'souvenirs_total': 0,
  })
  expected = text_format.Parse('''
  mode: MODE_SCRIMCOMP2V2
  name: "de_shortnuke"
  phase: MAP_PHASE_WARMUP
  team_t {
    score: 0
    consecutive_round_losses: 0
    timeouts_remaining: 1
    matches_won_this_series: 0
  }
  team_ct {
    score: 0
    consecutive_round_losses: 0
    timeouts_remaining: 1
    matches_won_this_series: 0
  }
  num_matches_to_win_series: 0
  current_spectators: 0
  ''', game_state_pb2.Map())
  assert text_format.MessageToString(actual) == \
         text_format.MessageToString(expected)


def test_json_to_proto():
  gs_proto = parse_game_state(SAMPLE_GAME_STATE)

  expected_map = text_format.Parse('''
  mode: MODE_SCRIMCOMP2V2
  name: "de_shortnuke"
  phase: MAP_PHASE_LIVE
  round: 1
  team_t {
    score: 0
    consecutive_round_losses: 1
    timeouts_remaining: 1
    matches_won_this_series: 0
  }
  team_ct {
    score: 0
    consecutive_round_losses: 0
    timeouts_remaining: 1
    matches_won_this_series: 0
  }
  num_matches_to_win_series: 0
  current_spectators: 0
  round_wins [{
    round_num: 1
    win_condition: WIN_CONDITION_CT_WIN_ELIMINATION
  }]
  ''', game_state_pb2.Map())
  assert text_format.MessageToString(gs_proto.map) == \
         text_format.MessageToString(expected_map)

  assert gs_proto.provider.timestamp.ToDatetime() == \
         datetime.datetime(2019, 5, 11, 0, 37, 51)
  assert gs_proto.round == game_state_pb2.Round(
      phase=game_state_pb2.Round.ROUND_PHASE_OVER,
      win_team=game_state_pb2.TEAM_CT,
  )


FREEZETIME_GAME_STATE = json.loads('''
{
    "map": {
        "mode": "scrimcomp2v2",
        "name": "de_shortnuke",
        "phase": "live",
        "round": 0,
        "team_ct": {
            "score": 0,
            "consecutive_round_losses": 0,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "team_t": {
            "score": 0,
            "consecutive_round_losses": 0,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "num_matches_to_win_series": 0,
        "current_spectators": 0,
        "souvenirs_total": 0
    },
    "player": {
        "steamid": "76561197960265729",
        "name": "Zane",
        "observer_slot": 2,
        "team": "CT",
        "activity": "playing",
        "match_stats": {
            "kills": 0,
            "assists": 0,
            "deaths": 0,
            "mvps": 0,
            "score": 0
        },
        "state": {
            "health": 100,
            "armor": 0,
            "helmet": false,
            "flashed": 0,
            "smoked": 0,
            "burning": 0,
            "money": 800,
            "round_kills": 0,
            "round_killhs": 0,
            "round_totaldmg": 0,
            "equip_value": 200
        }
    },
    "provider": {
        "name": "Counter-Strike: Global Offensive",
        "appid": 730,
        "version": 13694,
        "steamid": "76561198413889827",
        "timestamp": 1557534759
    },
    "round": {
        "phase": "freezetime"
    },
    "allplayers": {
        "76561198121510237": {
            "name": "nonverba1",
            "observer_slot": 1,
            "team": "CT",
            "match_stats": {
                "kills": 0,
                "assists": 0,
                "deaths": 0,
                "mvps": 0,
                "score": 0
            },
            "state": {
                "health": 100,
                "armor": 0,
                "helmet": false,
                "flashed": 0,
                "burning": 0,
                "money": 800,
                "round_kills": 0,
                "round_killhs": 0,
                "round_totaldmg": 0,
                "equip_value": 200
            }
        },
        "76561197970510532": {
            "name": "Defiler",
            "observer_slot": 3,
            "team": "T",
            "match_stats": {
                "kills": 0,
                "assists": 0,
                "deaths": 0,
                "mvps": 0,
                "score": 0
            },
            "state": {
                "health": 100,
                "armor": 0,
                "helmet": false,
                "flashed": 0,
                "burning": 0,
                "money": 800,
                "round_kills": 0,
                "round_killhs": 0,
                "round_totaldmg": 0,
                "equip_value": 200
            }
        },
        "76561197960265729": {
            "name": "Zane",
            "observer_slot": 2,
            "team": "CT",
            "match_stats": {
                "kills": 0,
                "assists": 0,
                "deaths": 0,
                "mvps": 0,
                "score": 0
            },
            "state": {
                "health": 100,
                "armor": 0,
                "helmet": false,
                "flashed": 0,
                "burning": 0,
                "money": 800,
                "round_kills": 0,
                "round_killhs": 0,
                "round_totaldmg": 0,
                "equip_value": 200
            }
        },
        "76561197960265730": {
            "name": "Hank",
            "observer_slot": 4,
            "team": "T",
            "match_stats": {
                "kills": 0,
                "assists": 0,
                "deaths": 0,
                "mvps": 0,
                "score": 0
            },
            "state": {
                "health": 100,
                "armor": 0,
                "helmet": false,
                "flashed": 0,
                "burning": 0,
                "money": 800,
                "round_kills": 0,
                "round_killhs": 0,
                "round_totaldmg": 0,
                "equip_value": 200
            }
        }
    },
    "previously": {
        "map": {
            "phase": "warmup"
        },
        "player": {
            "steamid": "76561198413889827",
            "name": "Gumbercules",
            "state": {
                "health": 0,
                "money": 0,
                "equip_value": 0
            }
        },
        "allplayers": {
            "76561198121510237": {
                "match_stats": {
                    "kills": 1,
                    "deaths": 1,
                    "score": 2
                },
                "state": {
                    "money": 3700
                }
            },
            "76561197970510532": {
                "match_stats": {
                    "kills": 4,
                    "score": 8
                },
                "state": {
                    "armor": 100,
                    "helmet": true,
                    "money": 4300,
                    "round_kills": 4,
                    "round_killhs": 3,
                    "equip_value": 3900
                }
            },
            "76561197960265729": {
                "match_stats": {
                    "kills": 1,
                    "assists": 1,
                    "deaths": 3,
                    "score": 3
                },
                "state": {
                    "money": 500
                }
            },
            "76561197960265730": {
                "match_stats": {
                    "assists": 1,
                    "deaths": 2,
                    "score": 1
                },
                "state": {
                    "money": 1400
                }
            }
        }
    },
    "added": {
        "player": {
            "observer_slot": true,
            "team": true
        }
    }
}
''')


def test_freezetime():
  actual = parse_game_state(FREEZETIME_GAME_STATE)

  expected = text_format.Parse('''
  phase: ROUND_PHASE_FREEZETIME
  ''', game_state_pb2.Round())
  assert text_format.MessageToString(actual.round) == \
         text_format.MessageToString(expected)


WARMUP_GAME_STATE = json.loads('''
{
    "map": {
        "mode": "scrimcomp2v2",
        "name": "de_shortnuke",
        "phase": "warmup",
        "round": 0,
        "team_ct": {
            "score": 0,
            "consecutive_round_losses": 0,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "team_t": {
            "score": 0,
            "consecutive_round_losses": 0,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "num_matches_to_win_series": 0,
        "current_spectators": 0,
        "souvenirs_total": 0
    },
    "player": {
        "steamid": "76561198413889827",
        "name": "unconnected",
        "activity": "playing",
        "match_stats": {
            "kills": 0,
            "assists": 0,
            "deaths": 0,
            "mvps": 0,
            "score": 0
        },
        "state": {
            "health": 0,
            "armor": 0,
            "helmet": false,
            "flashed": 0,
            "smoked": 0,
            "burning": 0,
            "money": 8000,
            "round_kills": 0,
            "round_killhs": 0,
            "equip_value": 0
        }
    },
    "provider": {
        "name": "Counter-Strike: Global Offensive",
        "appid": 730,
        "version": 13694,
        "steamid": "76561198413889827",
        "timestamp": 1557534710
    },
    "previously": {
        "player": {
            "name": "Gumbercules",
            "activity": "menu"
        }
    },
    "added": {
        "player": {
            "match_stats": true,
            "state": true
        }
    }
}
''')


def test_warmup():
  actual = parse_game_state(WARMUP_GAME_STATE)
  expected = text_format.Parse('''
  map {
      mode: MODE_SCRIMCOMP2V2
      name: "de_shortnuke"
      phase: MAP_PHASE_WARMUP
      round: 0
      team_ct {
          score: 0
          consecutive_round_losses: 0
          timeouts_remaining: 1
          matches_won_this_series: 0
      }
      team_t {
          score: 0
          consecutive_round_losses: 0
          timeouts_remaining: 1
          matches_won_this_series: 0
      }
      num_matches_to_win_series: 0
      current_spectators: 0
      souvenirs_total: 0
  }
  player {
      steam_id: 76561198413889827
      name: "unconnected"
      activity: ACTIVITY_PLAYING
      match_stats {
          kills: 0
          assists: 0
          deaths: 0
          mvps: 0
          score: 0
      }
      state {
          health: 0
          armor: 0
          helmet: false
          flashed: 0
          smoked: 0
          burning: 0,
          money: 8000
          round_kills: 0
          round_killhs: 0
          equip_value: 0
      }
  }
  provider {
      name: "Counter-Strike: Global Offensive"
      app_id: 730
      version: 13694,
      steam_id: 76561198413889827
      timestamp {
        seconds: 1557534710
      }
  }
  previously {
      player {
          name: "Gumbercules"
          activity: ACTIVITY_MENU
      }
  }
  added {
      player {
          match_stats: true,
          state: true
      }
  }
  ''', game_state_pb2.GameState())
  assert text_format.MessageToString(actual) == \
         text_format.MessageToString(expected)


BLANK_WIN_CONDITION_GAME_STATE = json.loads('''
{
    "provider": {
        "name": "Counter-Strike: Global Offensive",
        "appid": 730,
        "version": 13844,
        "steamid": "76561198413889827",
        "timestamp": 1665097332
    },
    "player": {
        "steamid": "76561198413889827",
        "clan": "truescrub",
        "name": "Gumbercules",
        "activity": "playing",
        "state": {
            "health": 0,
            "armor": 0,
            "helmet": false,
            "flashed": 0,
            "smoked": 0,
            "burning": 0,
            "money": 800,
            "round_kills": 0,
            "round_killhs": 0,
            "equip_value": 0
        }
    },
    "map": {
        "mode": "scrimcomp2v2",
        "name": "ar_dizzy",
        "phase": "live",
        "round": 3,
        "team_ct": {
            "score": 1,
            "consecutive_round_losses": 0,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "team_t": {
            "score": 2,
            "consecutive_round_losses": 1,
            "timeouts_remaining": 1,
            "matches_won_this_series": 0
        },
        "num_matches_to_win_series": 0,
        "current_spectators": 0,
        "souvenirs_total": 0,
        "round_wins": {
            "1": "t_win_elimination",
            "2": "t_win_elimination",
            "3": ""
        }
    },
    "round": {
        "phase": "over"
    },
    "previously": {
        "map": {
            "round_wins": {
                "3": "ct_win_elimination"
            }
        },
        "round": {
            "phase": "live"
        }
    }
}
''')

def test_blank_win_condition():
  actual = parse_game_state(BLANK_WIN_CONDITION_GAME_STATE)
  expected = text_format.Parse('''
  provider {
      name: "Counter-Strike: Global Offensive"
      app_id: 730
      version: 13844,
      steam_id: 76561198413889827
      timestamp {
        seconds: 1665097332
      }
  }
  player {
      steam_id: 76561198413889827
      clan: "truescrub"
      name: "Gumbercules"
      activity: ACTIVITY_PLAYING
      state {
          health: 0
          armor: 0
          helmet: false
          flashed: 0
          smoked: 0
          burning: 0,
          money: 800
          round_kills: 0
          round_killhs: 0
          equip_value: 0
      }
  }
  map {
      mode: MODE_SCRIMCOMP2V2
      name: "ar_dizzy"
      phase: MAP_PHASE_LIVE
      round: 3
      team_ct {
          score: 1
          consecutive_round_losses: 0
          timeouts_remaining: 1
          matches_won_this_series: 0
      }
      team_t {
          score: 2
          consecutive_round_losses: 1
          timeouts_remaining: 1
          matches_won_this_series: 0
      }
      round_wins {
          round_num: 1
          win_condition: WIN_CONDITION_T_WIN_ELIMINATION
      }
      round_wins {
          round_num: 2
          win_condition: WIN_CONDITION_T_WIN_ELIMINATION
      }
      num_matches_to_win_series: 0
      current_spectators: 0
      souvenirs_total: 0
  }
  round {
      phase: ROUND_PHASE_OVER
  }
  previously {
      map {
          round_wins: {
              round_num: 3
              win_condition: WIN_CONDITION_CT_WIN_ELIMINATION
          }
      }
      round {
          phase: ROUND_PHASE_LIVE
      }
  }
  ''', game_state_pb2.GameState())
  assert text_format.MessageToString(actual) == \
         text_format.MessageToString(expected)


if __name__ == '__main__':
  raise SystemExit(pytest.main([__file__]))
