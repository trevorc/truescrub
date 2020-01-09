import bisect

import trueskill

SKILL_MEAN = 1000.0
SKILL_STDEV = SKILL_MEAN / 4.0
SKILL_GROUP_SPACING = SKILL_STDEV * 0.3
SKILL_GROUP_NAMES = [
    'Scrub',
    'Staff Scrub',
    'Scrub First Class',
    'Cardboard I',
    'Cardboard II',
    'Cardboard III',
    'Cardboard IV',
    'Cardboard Elite',
    'Plastic I',
    'Plastic II',
    'Plastic III',
    'Plastic Elite',
    'Plastic Elite Master',
    'Legendary Wood',
    'Legendary Wood Master',
    'Supreme Legendary Wood',
    'Garb Salad',
    'Master Garbian I',
    'Master Garbian II',
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
