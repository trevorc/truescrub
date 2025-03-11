import sqlite3
from typing import Dict, FrozenSet, List

import trueskill

from truescrub.db import get_all_rounds, get_all_teams, get_skill_db
from truescrub.matchmaking import win_probability
from truescrub.models import BETA, SKILL_MEAN, SKILL_STDEV, TAU, RoundRow
from truescrub.updater.recalculate import compute_player_skills

__all__ = ["evaluate_parameters"]


def run_evaluation(
    connection: sqlite3.Connection,
    beta: float,
    tau: float,
    sample: float
) -> float:
    """
    Evaluate TrueSkill parameters by calculating the likelihood of match outcomes
    in a test set using ratings from a training set.

    Args:
        connection: Database connection to fetch teams and rounds
        beta: TrueSkill beta parameter (skill variability)
        tau: TrueSkill tau parameter (dynamic factor)
        sample: Fraction of data to use for training (0.0-1.0)

    Returns:
        float: Geometric mean of prediction accuracy
    """
    teams: Dict[int, FrozenSet[int]] = get_all_teams(connection)
    # Passing an empty tuple as round_range instead of None
    rounds: List[RoundRow] = get_all_rounds(connection, (0, 999999))

    offset: int = int(len(rounds) * sample)
    training_sample: List[RoundRow] = rounds[:offset]
    testing_sample: List[RoundRow] = rounds[offset:]
    environment: trueskill.TrueSkill = trueskill.TrueSkill(SKILL_MEAN, SKILL_STDEV, beta, tau, 0.0)

    ratings: Dict[int, trueskill.Rating] = compute_player_skills(training_sample, teams)[0]

    total: float = 1.0

    for round_data in testing_sample:
        winning_team: List[trueskill.Rating] = [ratings[player_id] for player_id in teams[round_data.winner]]
        losing_team: List[trueskill.Rating] = [ratings[player_id] for player_id in teams[round_data.loser]]
        probability: float = win_probability(environment, winning_team, losing_team)
        total *= probability

    # Calculate the geometric mean
    result: float = total ** (1 / float(len(testing_sample)))
    return result


def evaluate_parameters(beta: float = BETA, tau: float = TAU, sample: float = 0.5) -> None:
    """
    Run parameter evaluation with the given TrueSkill parameters and print the result.

    Args:
        beta: TrueSkill beta parameter (default is from models.BETA)
        tau: TrueSkill tau parameter (default is from models.TAU)
        sample: Fraction of data to use for training (default is 0.5)
    """
    with get_skill_db() as skill_db:
        result = run_evaluation(skill_db, beta, tau, sample)
        print(result)
