import argparse
import functools
import itertools
import json
import multiprocessing
import pathlib
import random
import shlex
from dataclasses import dataclass, replace
from typing import Tuple, List, Iterable, Set

import deap.algorithms
import deap.base
import deap.tools
import numpy

from truescrub.db import get_skill_db
from truescrub.tools.teameval import \
    tournament_eval, print_match, get_players_with_overrides
from truescrub.models import Player


class FitnessMax(deap.base.Fitness):
    weights = (1.0,)


@dataclass(frozen=True)
class Individual:
    players: List[Player]
    team_size: int
    inp: float
    fitness: FitnessMax

    @classmethod
    def create_random(cls, players: List[Player], team_size: int, inp: float):
        """Compute an 'individual' for the genetic algorithm: an assignment
        of players to teams."""

        players = list(players)
        random.shuffle(players)

        return cls(players, team_size, inp, FitnessMax())

    def teams(self, sentinel=object()):
        args = [iter(self.players)] * self.team_size
        return [[player for player in team if player is not sentinel]
                for team in itertools.zip_longest(*args, fillvalue=sentinel)]

    def quality(self) -> Tuple[float]:
        team_skills = [
            [player.skill for player in team]
            for team in self.teams()
        ]
        return (tournament_eval(team_skills),)

    def cross(self, other):
        # Based on cxUniformPartialyMatched
        child1: List[Player] = list(self.players)
        child2: List[Player] = list(other.players)

        size = min(len(child1), len(child2))
        p1 = {}
        p2 = {}

        # Initialize the position of each indices in the individuals
        for i in range(size):
            p1[child1[i]] = i
            p2[child2[i]] = i

        for i in range(size):
            if random.random() < self.inp:
                # Keep track of the selected values
                temp1 = child1[i]
                temp2 = child2[i]
                # Swap the matched value
                child1[i], child1[p1[temp2]] = temp2, temp1
                child2[i], child2[p2[temp1]] = temp1, temp2
                # Position bookkeeping
                p1[temp1], p1[temp2] = p1[temp2], p1[temp1]
                p2[temp1], p2[temp2] = p2[temp2], p2[temp1]

        ind1 = replace(self, players=child1, fitness=FitnessMax())
        ind2 = replace(other, players=child2, fitness=FitnessMax())

        return ind1, ind2

    def mutate(self):
        mutated: List[Player] = list(self.players)
        for i in range(len(self.players) - 1):
            j = random.randint(i, len(self.players) - 1)
            if random.random() < self.inp:
                mutated[i], mutated[j] = mutated[j], mutated[i]
        return (replace(self, players=mutated, fitness=FitnessMax()),)

    def to_match(self):
        return {
            'team_size': self.team_size,
            'quality': self.fitness.values[0],
            'teams': self.teams(),
        }


def compute_matches_genetic(
    pool: multiprocessing.Pool, players: Iterable[Player], seed: int,
    popsize: int, generations: int, cxp: float, mutp: float, inp: float,
    results: int, team_size: int) -> Iterable[Individual]:

    random.seed(seed)
    new_individual = functools.partial(
        Individual.create_random, players=players,
        team_size=team_size, inp=inp)

    population = deap.tools.initRepeat(
        list, new_individual, popsize)

    toolbox = deap.base.Toolbox()
    toolbox.register('mate', Individual.cross)
    toolbox.register('mutate', Individual.mutate)
    toolbox.register('select', deap.tools.selNSGA2)
    toolbox.register('evaluate', Individual.quality)
    toolbox.register('map', pool.map)

    hof = deap.tools.HallOfFame(maxsize=results)
    stats = deap.tools.Statistics(lambda ind: ind.fitness.values)
    stats.register('avg', numpy.mean, axis=0)
    stats.register('std', numpy.std, axis=0)
    stats.register('min', numpy.min, axis=0)
    stats.register('max', numpy.max, axis=0)

    deap.algorithms.eaSimple(
        population=population,
        toolbox=toolbox,
        cxpb=cxp,
        mutpb=mutp,
        ngen=generations,
        stats=stats,
        halloffame=hof,
    )
    return hof


def parse_players_json(players_path: pathlib.Path) \
        -> Tuple[List[int], List[Player]]:
    with players_path.open() as f:
        players_json = json.load(f)
        overrides = [
            Player(**override)
            for override in players_json['overrides']
        ]
        return players_json['player_ids'], overrides


def format_overrides(overrides) -> Iterable[str]:
    return itertools.chain(*(
        ('-o', f'{player.player_id}:{player.steam_name}:'
               f'{player.skill.mu}:{player.skill.sigma}')
        for player in overrides
    ))


def print_eval(
    overrides: List[Player], season: int, seed: int,
    teams: Iterable[List[Player]], quality: float, team_size: int):
    teams = list(teams)

    skill_var = numpy.std([
        sum(player.mmr for player in team)
        for team in teams
    ])
    print(f'Quality: {100.0 * quality:.2f}%, '
          f'Team Skill Stdev: {skill_var:.2f}')
    args = [
        'truescrub.teameval',
        '--season', str(season),
        '--seed', str(seed),
        '--method', 's',
    ]
    for override_arg in format_overrides(overrides):
        args.append(shlex.quote(override_arg))
    for team_no, team in enumerate(teams):
        args.append(','.join(str(player.player_id) for player in team))
        print('    Team {}: {}'.format(
            team_no + 1,
            ', '.join(player.steam_name for player in team),
            ))

    print(' '.join(args))
    print()


def make_arg_parser():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--seed', type=int, default=1337,
                            help='random seed')
    arg_parser.add_argument('--season', type=int,
                            default=4, help='use skills from this season')
    arg_parser.add_argument('--popsize', type=int, default=64,
                            help='initial population size')
    arg_parser.add_argument('--generations', type=int, default=200,
                            help='number of generations to run')
    arg_parser.add_argument('--cxp', type=float, default=0.5,
                            help='crossover probability')
    arg_parser.add_argument('--mutp', type=float, default=0.2,
                            help='mutation probability')
    arg_parser.add_argument('--inp', type=float, default=0.4,
                            help='individual probability')
    arg_parser.add_argument('--results', '-n', type=int, default=10,
                            help='show this many results')
    arg_parser.add_argument('--team-size', '-z', type=int, default=3,
                            help='players per team')
    arg_parser.add_argument('--print-eval', action='store_true')
    arg_parser.add_argument('players', type=pathlib.Path,
                            help='path to JSON file specifying players')
    return arg_parser


def main():
    opts = make_arg_parser().parse_args()
    player_ids, overrides = parse_players_json(opts.players)

    with get_skill_db() as skill_db, multiprocessing.Pool() as pool:
        season = opts.season
        seed = opts.seed

        players = get_players_with_overrides(
            skill_db, season, player_ids, overrides
        ).values()
        do_print_eval: bool = opts.print_eval

        opts = {key: val for key, val in opts.__dict__.items()
                if key not in {'season', 'print_eval', 'players'}}
        hof = compute_matches_genetic(pool, players, **opts)

        for match in hof:
            if do_print_eval:
                print_eval(overrides, season=season, seed=seed,
                           **match.to_match())
            else:
                print_match(**match.to_match())


if __name__ == '__main__':
    main()
