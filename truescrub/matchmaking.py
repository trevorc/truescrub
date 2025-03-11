import itertools
import math
import operator
from typing import Dict, Iterable, List, Optional, Tuple

import trueskill
from trueskill import Gaussian

from truescrub.models import (
    SKILL_MEAN,
    SKILL_STDEV,
    Match,
    Player,
    setup_trueskill,
    skill_groups,
)

MAX_PLAYERS_PER_TEAM = 6

setup_trueskill()

CONFIDENCE_LEVEL = 0.95


def confidence_interval_z(confidence_level: float) -> float:
    if confidence_level >= 1.0 or confidence_level <= 0.0:
        raise ValueError(
            f"confidence_interval {confidence_level} is out of range (0, 1)"
        )
    alpha = 1 - confidence_level
    return float(-trueskill.global_env().ppf(alpha / 2.0))


def standard_normal_percentile_range(estimate: Gaussian) -> Tuple[float, float]:
    cdf = trueskill.global_env().cdf
    z_star = confidence_interval_z(CONFIDENCE_LEVEL)

    lower_bound = cdf(estimate.mu - z_star * estimate.sigma)
    upper_bound = cdf(estimate.mu + z_star * estimate.sigma)

    return lower_bound, upper_bound


def estimated_skill_range(skill: Gaussian) -> Tuple[float, float]:
    normal_mu = (skill.mu - SKILL_MEAN) / SKILL_STDEV
    normal_sigma = skill.sigma / SKILL_STDEV
    normal_estimate = Gaussian(normal_mu, normal_sigma)
    return standard_normal_percentile_range(normal_estimate)


def skill_group_ranges() -> Iterable[Tuple[str, Optional[float], float]]:
    previous_bound = None
    previous_group = None
    for lower_bound, group_name in skill_groups():
        if previous_group is not None:
            yield previous_group, previous_bound, lower_bound
        previous_bound = lower_bound
        previous_group = group_name
    if previous_group is not None:
        yield previous_group, previous_bound, float("inf")


def win_probability(
    trueskill_env: trueskill.TrueSkill, team1: List[trueskill.Rating], team2: List[trueskill.Rating]
) -> float:
    delta_mu = sum(r.mu for r in team1) - sum(r.mu for r in team2)
    sum_sigma = sum(r.sigma**2 for r in itertools.chain(team1, team2))
    size = len(team1) + len(team2)
    denom = math.sqrt(size * (trueskill_env.beta**2) + sum_sigma)
    return float(trueskill_env.cdf(delta_mu / denom))


def team1_win_probability(
    player_skills: Dict[int, trueskill.Rating], team1: List[Player], team2: List[Player]
) -> float:
    return win_probability(
        trueskill.global_env(),
        [player_skills[player.player_id] for player in team1],
        [player_skills[player.player_id] for player in team2],
    )


def match_quality(
    player_skills: Dict[int, trueskill.Rating], team1: List[Player], team2: List[Player]
) -> float:
    teams = (
        [player_skills[player.player_id] for player in team1],
        [player_skills[player.player_id] for player in team2],
    )
    return float(trueskill.quality(teams))


def suggest_teams(
    player_skills: Dict[int, trueskill.Rating],
) -> Iterable[Tuple[Tuple[int, ...], Tuple[int, ...], float, float]]:
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
            p_win = win_probability(trueskill.global_env(), team1_skills, team2_skills)
            yield team1, team2, quality, p_win


def make_player_skills(players: List[Player]) -> Dict[int, trueskill.Rating]:
    return {player.player_id: player.skill for player in players}


def uniquify(matches: Iterable[Match]) -> Iterable[Match]:
    last_team1 = None
    last_team2 = None

    for match in matches:
        if (
            match.team1 == last_team1
            and match.team2 == last_team2
            or match.team1 == last_team2
            and match.team2 == last_team1
        ):
            continue
        yield match
        last_team1 = match.team1
        last_team2 = match.team2


def make_team(
    players_by_id: Dict[int, Player], player_ids: Iterable[int]
) -> List[Player]:
    team = [players_by_id[player_id] for player_id in player_ids]
    team.sort(key=operator.attrgetter("mmr"), reverse=True)
    return team


def make_match(
    players_by_id: Dict[int, Player],
    team1_ids: Optional[Tuple[int, ...]] = None,
    team2_ids: Optional[Tuple[int, ...]] = None,
    quality: float = 0.0,
    p_win: float = 0.5,
    team1: Optional[Iterable[int]] = None,
    team2: Optional[Iterable[int]] = None,
) -> Match:
    # Support both old and new parameter names for backward compatibility
    if team1 is not None:
        team1_ids = tuple(team1)
    if team2 is not None:
        team2_ids = tuple(team2)

    # Convert to tuple if any other iterable was passed
    if team1_ids is not None and not isinstance(team1_ids, tuple):
        team1_ids = tuple(team1_ids)
    if team2_ids is not None and not isinstance(team2_ids, tuple):
        team2_ids = tuple(team2_ids)

    # Default values
    if team1_ids is None:
        team1_ids = ()
    if team2_ids is None:
        team2_ids = ()

    team1_players = make_team(players_by_id, team1_ids)
    team2_players = make_team(players_by_id, team2_ids)

    if p_win < 0.5:
        team1_players, team2_players = team2_players, team1_players
        p_win = 1.0 - p_win

    return Match(team1_players, team2_players, quality, p_win)


def compute_matches(players: List[Player]) -> Iterable[Match]:
    player_skills = make_player_skills(players)
    players_by_id = {player.player_id: player for player in players}

    matches = [
        make_match(players_by_id, *suggestion)
        for suggestion in suggest_teams(player_skills)
    ]

    matches.sort(key=operator.attrgetter("quality"), reverse=True)
    return uniquify(matches)
