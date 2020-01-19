import math
import operator
import itertools
from typing import Iterable

import trueskill
from trueskill import Gaussian

from .models import SKILL_MEAN, SKILL_STDEV, SKILL_GROUPS, Player

BETA = SKILL_STDEV * 2.0
TAU = SKILL_STDEV / 100.0
MAX_PLAYERS_PER_TEAM = 6

trueskill.setup(mu=SKILL_MEAN, sigma=SKILL_STDEV, beta=BETA, tau=TAU,
                draw_probability=0.0)

CONFIDENCE_LEVEL = 0.95


def confidence_interval_z(confidence_level: float) -> float:
    if confidence_level >= 1.0 or confidence_level <= 0.0:
        raise ValueError('confidence_interval {} is out of range (0, 1)'.format(
                confidence_level))
    alpha = 1 - confidence_level
    return -trueskill.global_env().ppf(alpha / 2.0)


def standard_normal_percentile_range(estimate: Gaussian) -> (float, float):
    cdf = trueskill.global_env().cdf
    z_star = confidence_interval_z(CONFIDENCE_LEVEL)

    lower_bound = cdf(estimate.mu - z_star * estimate.sigma)
    upper_bound = cdf(estimate.mu + z_star * estimate.sigma)

    return lower_bound, upper_bound


def estimated_skill_range(skill: Gaussian) -> (float, float):
    normal_mu = (skill.mu - SKILL_MEAN) / SKILL_STDEV
    normal_sigma = skill.sigma / SKILL_STDEV
    normal_estimate = Gaussian(normal_mu, normal_sigma)
    return standard_normal_percentile_range(normal_estimate)


def skill_group_ranges():
    previous_bound = None
    previous_group = None
    for lower_bound, group_name in SKILL_GROUPS:
        if previous_group is not None:
            yield previous_group, previous_bound, lower_bound
        previous_bound = lower_bound
        previous_group = group_name
    yield previous_group, previous_bound, float('inf')


def win_probability(trueskill_env, team1, team2):
    delta_mu = sum(r.mu for r in team1) - sum(r.mu for r in team2)
    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(team1, team2))
    size = len(team1) + len(team2)
    denom = math.sqrt(size * (trueskill_env.beta ** 2) + sum_sigma)
    return trueskill_env.cdf(delta_mu / denom)


def team1_win_probability(player_skills: {int: trueskill.Rating}, team1, team2):
    return win_probability(
            trueskill.global_env(),
            [player_skills[player.player_id] for player in team1],
            [player_skills[player.player_id] for player in team2])


def match_quality(
        player_skills: {int: trueskill.TrueSkill},
        team1: [Player], team2: [Player]) -> float:
    teams = (
        [player_skills[player.player_id] for player in team1],
        [player_skills[player.player_id] for player in team2],
    )
    return trueskill.quality(teams)


def suggest_teams(player_skills: {int: trueskill.Rating}):
    players = frozenset(player_skills.keys())
    max_team_size = min(len(players) // 2, MAX_PLAYERS_PER_TEAM)
    min_team_size = max(1, len(players) - MAX_PLAYERS_PER_TEAM)
    teams_seen = set()

    for r in range(min_team_size, max_team_size + 1):
        for team1 in itertools.combinations(players, r):
            team2 = tuple(players - frozenset(team1))

            if team1 in teams_seen or team2 in teams_seen:
                continue
            teams_seen.add(team1)
            teams_seen.add(team2)

            team1_skills = [player_skills[player_id] for player_id in team1]
            team2_skills = [player_skills[player_id] for player_id in team2]
            quality = trueskill.quality((team1_skills, team2_skills))
            p_win = win_probability(trueskill.global_env(),
                                    team1_skills, team2_skills)
            yield team1, team2, quality, p_win


def make_player_skills(players: [Player]) -> {int: trueskill.Rating}:
    return {
        player.player_id: player.skill
        for player in players
    }


def uniquify(matches):
    last_team1 = None
    last_team2 = None

    for match in matches:
        if match['team1'] == last_team1 and match['team2'] == last_team2 or \
                match['team1'] == last_team2 and match['team2'] == last_team1:
            continue
        yield match
        last_team1 = match['team1']
        last_team2 = match['team2']


def make_team(players_by_id, player_ids):
    team = [players_by_id[player_id] for player_id in player_ids]
    team.sort(key=operator.attrgetter('mmr'), reverse=True)
    return team


def make_match(players_by_id, team1: Iterable[int], team2: Iterable[int],
               quality: float, p_win: float):
    team1 = make_team(players_by_id, team1)
    team2 = make_team(players_by_id, team2)

    if p_win < 0.5:
        team1, team2 = team2, team1
        p_win = 1.0 - p_win

    return {
        'team1': team1,
        'team2': team2,
        'quality': quality,
        'team1_win_probability': p_win,
        'team2_win_probability': 1.0 - p_win,
    }


def compute_matches(players: [Player]):
    player_skills = make_player_skills(players)
    players_by_id = {player.player_id: player for player in players}

    matches = [make_match(players_by_id, *suggestion)
               for suggestion in suggest_teams(player_skills)]

    matches.sort(key=operator.itemgetter('quality'), reverse=True)
    return uniquify(matches)
