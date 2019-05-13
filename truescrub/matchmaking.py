import bisect
import operator
import itertools

import trueskill


SKILL_MEAN = 1000
SKILL_STDEV = 100
BETA = SKILL_STDEV / 2.0
TAU = SKILL_STDEV / 100.0
MAX_PLAYERS_PER_TEAM = 5

trueskill.setup(mu=SKILL_MEAN, sigma=SKILL_STDEV, beta=BETA, tau=TAU)

SKILL_GROUP_SPACING = 1.25 * SKILL_STDEV
SKILL_GROUP_NAMES = [
    'Scrub',
    'Cardboard I',
    'Cardboard II',
    'Cardboard III',
    'Cardboard IV',
    'Cardboard Elite',
    'Plastic I',
    'Plastic II',
    'Plastic III',
    'Plastic Elite',
    'Wood I',
    'Wood II',
    'Wood Supreme Master',
    'Aluminum',
    'Garb Salad',
    'Legendary Silver',
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


def skill_group_ranges():
    previous_bound = None
    previous_group = None
    for lower_bound, group_name in SKILL_GROUPS:
        if previous_group is not None:
            yield previous_group, previous_bound, lower_bound
        previous_bound = lower_bound
        previous_group = group_name
    yield previous_group, previous_bound, float('inf')


def match_quality(
        player_skills: {int: trueskill.TrueSkill},
        team1: [dict], team2: [dict]) -> float:
    teams = (
        [player_skills[player['player_id']] for player in team1],
        [player_skills[player['player_id']] for player in team2],
    )
    return trueskill.quality(teams)


def suggest_teams(player_skills):
    players = frozenset(player_skills.keys())
    max_team_size = min(len(players) // 2, MAX_PLAYERS_PER_TEAM)
    min_team_size = max(1, len(players) - MAX_PLAYERS_PER_TEAM)

    for r in range(min_team_size, max_team_size + 1):
        for team1 in itertools.combinations(players, r):
            team2 = players - set(team1)
            quality = trueskill.quality((
                [player_skills[player_id] for player_id in team1],
                [player_skills[player_id] for player_id in team2]
            ))
            yield team1, team2, quality


def make_player_skills(players):
    return {
        player['player_id']: trueskill.Rating(
                player['skill_mean'],
                player['skill_stdev'])
        for player in players
    }


def compute_matches(players):
    player_skills = make_player_skills(players)
    players_by_id = {player['player_id']: player for player in players}

    teams = [{
        'team1': [players_by_id[player_id] for player_id in team1],
        'team2': [players_by_id[player_id] for player_id in team2],
        'quality': quality * 100,
    } for team1, team2, quality in suggest_teams(player_skills)]

    teams.sort(key=operator.itemgetter('quality'), reverse=True)
    return teams
