import sys

from truescrub.models import SKILL_GROUP_NAMES, Player, skill_group_name


def test_skill_groups():
  assert Player(1, '', 0, 125, 0.0).skill_group_index == 0
  assert Player(1, '', -1337, 125, 0.0).skill_group_index == 0
  assert Player(1, '', sys.maxsize, 25, 0.0).skill_group_index == \
         len(SKILL_GROUP_NAMES)


def test_player():
  mean, stdev = 1379, 76
  player = Player(player_id=76561198121510237, steam_name='nonverba1',
                  skill_mean=mean, skill_stdev=stdev, impact_rating=1.02)
  assert player.mmr == mean - 2 * stdev

  assert skill_group_name(player.skill_group_index) == 'Garb Salad'


if __name__ == '__main__':
  import pytest
  raise SystemExit(pytest.main([__file__]))
