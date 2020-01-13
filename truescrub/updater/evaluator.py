import trueskill

from ..db import get_skill_db, get_all_teams, get_all_rounds
from ..matchmaking import win_probability, BETA, TAU
from truescrub.models import SKILL_MEAN, SKILL_STDEV
from .recalculate import compute_player_skills


def run_evaluation(connection, beta, tau, sample):
    teams = get_all_teams(connection)
    rounds = get_all_rounds(connection, None)

    offset = int(len(rounds) * sample)
    training_sample = rounds[:offset]
    testing_sample = rounds[offset:]
    environment = trueskill.TrueSkill(SKILL_MEAN, SKILL_STDEV, beta, tau, 0.0)

    ratings = compute_player_skills(training_sample, teams)[0]

    total = 1.0

    for round in testing_sample:
        winning_team = [ratings[player_id]
                        for player_id in teams[round['winner']]]
        losing_team = [ratings[player_id]
                       for player_id in teams[round['loser']]]
        total *= win_probability(environment, winning_team, losing_team)

    return total ** (1 / float(len(testing_sample)))


def evaluate_parameters(beta=BETA, tau=TAU, sample=0.5):
    with get_skill_db() as skill_db:
        print(run_evaluation(skill_db, beta, tau, sample))
