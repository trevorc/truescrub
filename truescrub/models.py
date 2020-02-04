import json
import bisect
import datetime
from typing import Optional

import trueskill

SKILL_MEAN = 1000.0
SKILL_STDEV = SKILL_MEAN / 4.0
SKILL_GROUP_SPACING = SKILL_STDEV * 0.5
SKILL_GROUP_NAMES = [
    'Cardboard I',
    'Cardboard II',
    'Cardboard III',
    'Cardboard IV',
    'Plastic I',
    'Plastic II',
    'Plastic III',
    'Plastic Elite',
    'Legendary Wood',
    'Garb Salad',
    'Master Garbian',
    'Master Garbian Elite',
    'Low-Key Dirty',
]
SKILL_GROUPS = ((float('-inf'), SKILL_GROUP_NAMES[0]),) + tuple(
        (SKILL_GROUP_SPACING * (i + 1), name)
        for i, name in enumerate(SKILL_GROUP_NAMES[1:])
)


def skill_group_name(mmr: float) -> str:
    group_ranks = [group[0] for group in SKILL_GROUPS]
    index = bisect.bisect(group_ranks, mmr)
    return SKILL_GROUPS[index - 1][1]


class ThinPlayer(object):
    __slots__ = ('player_id', 'steam_name')

    def __init__(self, player_id, steam_name):
        self.player_id = player_id
        self.steam_name = steam_name


class Player(object):
    __slots__ = (
        'player_id', 'steam_name', 'skill',
        'mmr', 'skill_group', 'impact_rating'
    )

    def __init__(self, player_id: int, steam_name: str,
            skill_mean: float, skill_stdev: float, impact_rating: float):
        self.player_id = int(player_id)
        self.steam_name = steam_name
        self.skill = trueskill.Rating(skill_mean, skill_stdev)
        self.mmr = int(self.skill.mu - self.skill.sigma * 2)
        self.skill_group = skill_group_name(self.mmr)
        self.impact_rating = impact_rating


class SkillHistory(object):
    __slots__ = ('round_id', 'player_id', 'skill')

    def __init__(self, round_id: int, player_id: int,
                 skill: trueskill.Rating):
        self.round_id = round_id
        self.player_id = player_id
        self.skill = skill


class RoundRow(object):
    __slots__ = ('round_id', 'created_at', 'season_id',
                 'winner', 'loser', 'mvp')

    def __init__(self, round_id: int, created_at: datetime.datetime,
                 season_id: int, winner: int, loser: int, mvp: Optional[int]):
        self.season_id = season_id
        self.created_at = created_at
        self.round_id = round_id
        self.winner = winner
        self.loser = loser
        self.mvp = mvp


class GameStateRow(object):
    __slots__ = ('game_state_id', 'map_name', 'map_phase', 'win_team',
                 'timestamp', 'allplayers', 'previous_allplayers')

    def __init__(self, game_state_id: int, map_name: str, map_phase: str,
                 win_team: str, timestamp: int, allplayers: str,
                 previous_allplayers: Optional[str]):
        self.game_state_id = game_state_id
        self.map_name = map_name
        self.map_phase = map_phase
        self.win_team = win_team
        self.timestamp = timestamp
        self.allplayers = json.loads(allplayers)
        self.previous_allplayers = {} if previous_allplayers is None \
            else json.loads(previous_allplayers)
