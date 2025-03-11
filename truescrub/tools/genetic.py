import argparse
import functools
import itertools
import json
import multiprocessing.pool
import os
import pathlib
import random
import shlex
from dataclasses import dataclass, replace
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    cast,
)

import deap.algorithms
import deap.base
import deap.tools
import numpy

from truescrub.db import get_skill_db
from truescrub.models import Player
from truescrub.tools.teameval import (
    get_players_with_overrides,
    print_match,
    tournament_eval,
)


class FitnessMax(deap.base.Fitness):
    weights = (1.0,)


@dataclass(frozen=True)
class Individual:
    """
    Represents an individual in the genetic algorithm - an assignment of players to teams.
    """

    players: List[Player]
    team_size: int
    inp: float
    fitness: FitnessMax

    @classmethod
    def create_random(
        cls, players: List[Player], team_size: int, inp: float
    ) -> "Individual":
        """
        Compute an 'individual' for the genetic algorithm: an assignment
        of players to teams.

        Args:
            players: List of players to assign to teams
            team_size: Number of players per team
            inp: Individual probability for mutation/crossover

        Returns:
            A new Individual with randomly assigned players
        """
        players = list(players)
        random.shuffle(players)

        return cls(players, team_size, inp, FitnessMax())

    def teams(self, sentinel: Any = None) -> List[List[Player]]:
        """
        Split players into teams of size team_size.

        Args:
            sentinel: Optional sentinel value for grouping

        Returns:
            List of teams (each team is a list of players)
        """
        if sentinel is None:
            sentinel = object()
        args = [iter(self.players)] * self.team_size
        return [
            [player for player in team if player is not sentinel]
            for team in itertools.zip_longest(*args, fillvalue=sentinel)
        ]

    def quality(self) -> Tuple[float]:
        """
        Calculate the quality of this team assignment.

        Returns:
            A tuple containing a single float: the team assignment quality
        """
        team_skills = [[player.skill for player in team] for team in self.teams()]
        return (tournament_eval(team_skills),)

    def cross(self, other: "Individual") -> Tuple["Individual", "Individual"]:
        """
        Perform crossover with another individual.
        Based on cxUniformPartialyMatched algorithm.

        Args:
            other: The other individual to cross with

        Returns:
            A tuple of two new individuals resulting from the crossover
        """
        # Based on cxUniformPartialyMatched
        child1: List[Player] = list(self.players)
        child2: List[Player] = list(other.players)

        size = min(len(child1), len(child2))
        p1: Dict[Player, int] = {}
        p2: Dict[Player, int] = {}

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

    def mutate(self) -> Tuple["Individual"]:
        """
        Perform mutation on this individual.

        Returns:
            A tuple containing a single new individual resulting from mutation
        """
        mutated: List[Player] = list(self.players)
        for i in range(len(self.players) - 1):
            j = random.randint(i, len(self.players) - 1)
            if random.random() < self.inp:
                mutated[i], mutated[j] = mutated[j], mutated[i]
        return (replace(self, players=mutated, fitness=FitnessMax()),)

    def to_match(self) -> Dict[str, Any]:
        """
        Convert this individual to a match dictionary format.

        Returns:
            A dictionary with team_size, quality, and teams
        """
        return {
            "team_size": self.team_size,
            "quality": self.fitness.values[0],
            "teams": self.teams(),
        }


def compute_matches_genetic(
    pool: multiprocessing.pool.Pool,
    players: Iterable[Player],
    seed: int,
    popsize: int,
    generations: int,
    cxp: float,
    mutp: float,
    inp: float,
    results: int,
    team_size: int,
) -> List[Individual]:
    """
    Run a genetic algorithm to compute optimal team compositions.

    Args:
        pool: Multiprocessing pool for parallel evaluation
        players: Players to split into teams
        seed: Random seed for reproducibility
        popsize: Size of the population
        generations: Number of generations to run
        cxp: Crossover probability
        mutp: Mutation probability
        inp: Individual probability
        results: Number of best results to return
        team_size: Number of players per team

    Returns:
        List of Individual objects representing the best team arrangements found
    """
    random.seed(seed)
    player_list = list(players)
    new_individual = functools.partial(
        Individual.create_random, players=player_list, team_size=team_size, inp=inp
    )

    population = deap.tools.initRepeat(list, new_individual, popsize)

    toolbox = deap.base.Toolbox()
    toolbox.register("mate", Individual.cross)
    toolbox.register("mutate", Individual.mutate)
    toolbox.register("select", deap.tools.selNSGA2)
    toolbox.register("evaluate", Individual.quality)
    toolbox.register("map", pool.map)

    hof = deap.tools.HallOfFame(maxsize=results)
    stats = deap.tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", numpy.mean, axis=0)
    stats.register("std", numpy.std, axis=0)
    stats.register("min", numpy.min, axis=0)
    stats.register("max", numpy.max, axis=0)

    deap.algorithms.eaSimple(
        population=population,
        toolbox=toolbox,
        cxpb=cxp,
        mutpb=mutp,
        ngen=generations,
        stats=stats,
        halloffame=hof,
    )
    return cast(List[Individual], hof)


def parse_players_json(players_path: pathlib.Path) -> Tuple[List[int], List[Player]]:
    """
    Parse a JSON file containing player IDs and overrides.

    Args:
        players_path: Path to the JSON file

    Returns:
        Tuple containing a list of player IDs and a list of Player objects with overrides
    """
    with players_path.open() as f:
        players_json = json.load(f)
        overrides = [Player(**override) for override in players_json["overrides"]]
        return players_json["player_ids"], overrides


def format_overrides(overrides: List[Player]) -> Iterable[str]:
    """
    Format player overrides for command-line arguments.

    Args:
        overrides: List of Player objects with override information

    Returns:
        Iterable of strings for command-line arguments
    """
    return itertools.chain(
        *(
            (
                "-o",
                f"{player.player_id}:{player.steam_name}:"
                f"{player.skill.mu}:{player.skill.sigma}",
            )
            for player in overrides
        )
    )


def print_eval(
    overrides: List[Player],
    season: int,
    seed: int,
    teams: Iterable[List[Player]],
    quality: float,
    team_size: int,
) -> None:
    """
    Print evaluation information about teams.

    Args:
        overrides: List of Player objects with override information
        season: Season ID
        seed: Random seed
        teams: List of teams (each a list of Player objects)
        quality: Quality score of the team composition
        team_size: Number of players per team
    """
    teams_list = list(teams)

    skill_var = numpy.std([sum(player.mmr for player in team) for team in teams_list])
    print(f"Quality: {100.0 * quality:.2f}%, " f"Team Skill Stdev: {skill_var:.2f}")
    args = [
        "truescrub.teameval",
        "--season",
        str(season),
        "--seed",
        str(seed),
        "--method",
        "s",
    ]
    for override_arg in format_overrides(overrides):
        args.append(shlex.quote(override_arg))
    for team_no, team in enumerate(teams_list):
        args.append(",".join(str(player.player_id) for player in team))
        print(
            "    Team {}: {}".format(
                team_no + 1,
                ", ".join(player.steam_name for player in team),
            )
        )

    print(" ".join(args))
    print()


def make_arg_parser() -> argparse.ArgumentParser:
    """
    Create an argument parser for the command-line interface.

    Returns:
        Configured ArgumentParser object
    """
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--seed", type=int, default=1337, help="random seed")
    arg_parser.add_argument(
        "--season",
        type=int,
        default=int(os.getenv("SEASON_ID", 4)),
        help="use skills from this season",
    )
    arg_parser.add_argument(
        "--popsize", type=int, default=64, help="initial population size"
    )
    arg_parser.add_argument(
        "--generations", type=int, default=200, help="number of generations to run"
    )
    arg_parser.add_argument(
        "--cxp", type=float, default=0.5, help="crossover probability"
    )
    arg_parser.add_argument(
        "--mutp", type=float, default=0.2, help="mutation probability"
    )
    arg_parser.add_argument(
        "--inp", type=float, default=0.4, help="individual probability"
    )
    arg_parser.add_argument(
        "--results", "-n", type=int, default=10, help="show this many results"
    )
    arg_parser.add_argument(
        "--team-size", "-z", type=int, default=3, help="players per team"
    )
    arg_parser.add_argument("--print-eval", action="store_true")
    arg_parser.add_argument(
        "players", type=pathlib.Path, help="path to JSON file specifying players"
    )
    return arg_parser


def main() -> None:
    """
    Main entry point for the genetic team assignment algorithm.
    """
    opts = make_arg_parser().parse_args()
    player_ids, overrides = parse_players_json(opts.players)

    with get_skill_db() as skill_db, multiprocessing.pool.Pool() as pool:
        season = opts.season
        seed = opts.seed

        player_set: Set[int] = set(player_ids)
        players = get_players_with_overrides(
            skill_db, season, player_set, overrides
        ).values()
        do_print_eval: bool = opts.print_eval

        # Extract relevant options for compute_matches_genetic
        genetic_opts = {
            key: val
            for key, val in opts.__dict__.items()
            if key not in {"season", "print_eval", "players"}
        }
        hof = compute_matches_genetic(pool, players, **genetic_opts)

        for match in hof:
            if do_print_eval:
                print_eval(overrides, season=season, seed=seed, **match.to_match())
            else:
                print_match(**match.to_match())


if __name__ == "__main__":
    main()
