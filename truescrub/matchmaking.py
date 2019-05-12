import bisect
import operator
import itertools

import trueskill


SKILL_MEAN = 1000
SKILL_STDEV = 200
BETA = SKILL_STDEV / 2.0
TAU = SKILL_STDEV / 100.0

trueskill.setup(mu=SKILL_MEAN, sigma=SKILL_STDEV, beta=BETA, tau=TAU)

SKILL_GROUPS = [
    (float('-inf'), 'Scrub'),
    (0, 'Cardboard I'),
    (150, 'Cardboard II'),
    (300, 'Cardboard III'),
    (450, 'Cardboard IV'),
    (600, 'Plastic I'),
    (750, 'Plastic II'),
    (900, 'Plastic III'),
    (1050, 'Plastic Elite'),
    (1200, 'Plastic Supreme'),
    (1350, 'Wood I'),
    (1500, 'Wood II'),
    (1650, 'Aluminum'),
    (1800, 'Garb Salad'),
    (1950, 'Legendary Silver'),
    (2100, 'Low-Key Dirty'),
]


def skill_group_name(mmr: float) -> str:
    group_ranks = [group[0] for group in SKILL_GROUPS]
    index = bisect.bisect(group_ranks, mmr)
    return SKILL_GROUPS[index - 1][1]


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
    for r in range(1, len(players) // 2 + 1):
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
