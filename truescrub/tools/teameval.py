import argparse
import itertools
import math
import operator
import random
import sqlite3
from typing import (
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    TypeVar,
)

import trueskill
from trueskill import Rating

from truescrub.db import get_season_players, get_skill_db
from truescrub.matchmaking import win_probability
from truescrub.models import Player

# Define generic type for tournament simulator
T = TypeVar("T", bound=List[Rating])

# Type alias for tournament simulator return type
TournamentSimulator = Generator[Optional[float], Tuple[List[Rating], List[Rating]], None]

# Type definition for team information
class TeamInfo(TypedDict):
    """Information about a team including average MMR and player list."""
    average_mmr: float
    players: List[Player]


def get_assignment_quality(teams: List[List[Rating]]) -> float:
    """
    Calculate overall quality for multiple teams.

    Args:
        teams: List of team skills, each team represented as list of player Ratings

    Returns:
        A quality score (0-1) for the overall assignment

    Raises:
        ValueError: If teams list is empty
    """
    if not teams:
        raise ValueError("cannot compute assignment quality for no teams")
    quality = 0.0
    pow = 0
    for team_a, team_b in itertools.combinations(teams, 2):
        quality += math.log(trueskill.quality((team_a, team_b)))
        pow += 1
    return math.pow(math.exp(quality), 1.0 / pow)


def mmr_sum(team: List[Rating]) -> float:
    """
    Calculate the total MMR for a team, accounting for uncertainty.

    Args:
        team: List of player Ratings

    Returns:
        The sum of MMRs (mu - 2*sigma) for all players in the team
    """
    result: float = 0.0
    for skill in team:
        result += skill.mu - 2 * skill.sigma
    return result


def run_match(team_a: List[Rating], team_b: List[Rating]) -> List[Rating]:
    """
    Simulate a match between two teams based on skill ratings.

    Args:
        team_a: First team's player ratings
        team_b: Second team's player ratings

    Returns:
        The winning team's ratings (either team_a or team_b)
    """
    if random.random() <= win_probability(trueskill.global_env(), team_a, team_b):
        return team_a
    return team_b


TRIAL_COUNT = 3


def tournament_simulator() -> TournamentSimulator:
    """
    Generator that simulates a tournament, calculating overall match quality.

    Yields:
        Current quality score (0-1) or None for first yield

    Receives:
        Tuple of (team1, team2) ratings for each match

    Returns:
        Generator that tracks tournament quality over multiple matches
    """
    matches = 0
    raw_quality = 0.0
    quality: Optional[float] = None

    while True:
        team1, team2 = yield quality
        raw_quality += math.log(trueskill.quality((team1, team2)))
        matches += 1
        quality = math.pow(math.exp(raw_quality), 1.0 / matches)


def three_team_single_elimination(
    tournament: TournamentSimulator,
    teams: List[List[Rating]],
) -> float:
    """
    Simulate a 3-team single elimination tournament.

    Args:
        tournament: Tournament simulator generator
        teams: List of 3 teams, each represented as a list of player Ratings

    Returns:
        Final quality score for the tournament

    Raises:
        ValueError: If teams list doesn't contain exactly 3 teams
    """
    if len(teams) != 3:
        raise ValueError("must supply 3 teams")

    quality = next(tournament)
    for _ in range(TRIAL_COUNT):
        # Semifinals
        tournament.send((teams[1], teams[2]))
        sf_winner = run_match(teams[1], teams[2])

        # Grand Finals
        quality = tournament.send((teams[0], sf_winner))

    assert quality is not None, "Quality should not be None after tournament"
    return quality


def four_team_single_elimination(
    tournament: TournamentSimulator,
    teams: List[List[Rating]],
) -> float:
    """
    Simulate a 4-team single elimination tournament.

    Args:
        tournament: Tournament simulator generator
        teams: List of 4 teams, each represented as a list of player Ratings

    Returns:
        Final quality score for the tournament

    Raises:
        ValueError: If teams list doesn't contain exactly 4 teams
    """
    if len(teams) != 4:
        raise ValueError("must supply 4 teams")

    quality = next(tournament)
    for _ in range(TRIAL_COUNT):
        # Semifinals
        tournament.send((teams[0], teams[3]))
        sf1_winner = run_match(teams[0], teams[3])
        tournament.send((teams[1], teams[2]))
        sf2_winner = run_match(teams[1], teams[2])

        # Grand Finals
        quality = tournament.send((sf1_winner, sf2_winner))

    assert quality is not None, "Quality should not be None after tournament"
    return quality


def five_team_single_elimination(
    tournament: TournamentSimulator,
    teams: List[List[Rating]],
) -> float:
    """
    Simulate a 5-team single elimination tournament.

    Args:
        tournament: Tournament simulator generator
        teams: List of 5 teams, each represented as a list of player Ratings

    Returns:
        Final quality score for the tournament

    Raises:
        ValueError: If teams list doesn't contain exactly 5 teams
    """
    if len(teams) != 5:
        raise ValueError("must supply 5 teams")

    quality = next(tournament)
    for _ in range(TRIAL_COUNT):
        tournament.send((teams[3], teams[4]))
        qf_winner = run_match(teams[3], teams[4])

        # Semifinals
        tournament.send((teams[0], qf_winner))
        sf1_winner = run_match(teams[0], qf_winner)
        tournament.send((teams[1], teams[2]))
        sf2_winner = run_match(teams[1], teams[2])

        # Grand Finals
        quality = tournament.send((sf1_winner, sf2_winner))

    assert quality is not None, "Quality should not be None after tournament"
    return quality


def tournament_eval(teams: List[List[Rating]]) -> float:
    """
    Evaluate a tournament for a given set of teams.

    Args:
        teams: List of teams, each represented as a list of player Ratings

    Returns:
        Quality score for the tournament

    Raises:
        ValueError: If team count is not supported (must be 3, 4, or 5)
    """
    # Sort teams in place by MMR sum
    teams.sort(key=mmr_sum, reverse=True)
    tournament = tournament_simulator()

    if len(teams) == 3:
        return three_team_single_elimination(tournament, teams)
    if len(teams) == 4:
        return four_team_single_elimination(tournament, teams)
    if len(teams) == 5:
        return five_team_single_elimination(tournament, teams)

    raise ValueError(f"unsupported team count {len(teams)}")


def get_players_with_overrides(
    skill_db: sqlite3.Connection,
    season: int,
    player_ids: Set[int],
    overrides: Iterable[Player],
) -> Dict[int, Player]:
    """
    Get player data with optional overrides.

    Args:
        skill_db: Database connection
        season: Season ID to pull data from
        player_ids: Set of player IDs to include
        overrides: Player objects to override defaults

    Returns:
        Dictionary of player ID to Player object
    """
    players = {
        player.player_id: player
        for player in get_season_players(skill_db, season)
        if player.player_id in player_ids
    }
    for override in overrides:
        players[override.player_id] = override
    return players


def parse_overrides(overrides_spec: List[str]) -> Dict[int, Player]:
    """
    Parse override specifications from strings.

    Args:
        overrides_spec: List of strings in format "ID:NAME:MU:SIGMA"

    Returns:
        Dictionary of player ID to Player object

    Raises:
        ValueError: If the override specification format is invalid
    """
    overrides: Dict[int, Player] = {}
    for spec in overrides_spec:
        try:
            steamid, name, mu, sigma = spec.split(":", maxsplit=4)
            player_id = int(steamid)
            overrides[player_id] = Player(
                player_id=player_id,
                steam_name=name,
                skill_mean=float(mu),
                skill_stdev=float(sigma),
                impact_rating=0.0,
            )
        except ValueError as e:
            raise ValueError(f"Invalid override format '{spec}'. Expected ID:NAME:MU:SIGMA") from e
    return overrides


def stdev(xs: Iterable[float]) -> float:
    """
    Calculate standard deviation of values.

    Args:
        xs: Iterable of numeric values

    Returns:
        Standard deviation or 0.0 if fewer than 2 values
    """
    count = 0
    acc1 = 0.0
    acc2 = 0.0
    for x in xs:
        count += 1
        acc1 += x
        acc2 += x**2
    if count <= 1:
        return 0.0
    mean = acc1 / count
    variance = (acc2 - acc1 * mean) / count
    return math.sqrt(variance)


def print_match(teams: Iterable[List[Player]], quality: float, team_size: int) -> None:
    """
    Print match details to console.

    Args:
        teams: List of teams, each represented as a list of Player objects
        quality: Quality score for the match (0-1)
        team_size: Number of players per team
    """
    # Create structured team information
    annotated: List[TeamInfo] = [
        {
            "average_mmr": sum(player.mmr for player in team) / float(team_size),
            "players": list(team),
        }
        for team in teams
    ]
    annotated.sort(key=operator.itemgetter("average_mmr"), reverse=True)

    skill_var = stdev([team["average_mmr"] for team in annotated])
    print(f"Quality: {100.0 * quality:.2f}%, Team Skill Stdev: {skill_var:.2f}")

    for team_no, team_info in enumerate(annotated):
        players_list = team_info["players"]
        players_list.sort(key=operator.attrgetter("mmr"), reverse=True)
        print(
            "    Team {} (Avg MMR {}): {}".format(
                team_no + 1,
                int(team_info["average_mmr"]),
                ", ".join(player.steam_name for player in players_list),
            )
        )
    print()


def make_arg_parser() -> argparse.ArgumentParser:
    """
    Create and configure argument parser for command line interface.

    Returns:
        Configured ArgumentParser
    """
    arg_parser = argparse.ArgumentParser(description="Evaluate team matchups and tournaments")
    arg_parser.add_argument(
        "-s", "--season", type=int, default=4, help="get ratings from season"
    )
    arg_parser.add_argument(
        "-e", "--seed", type=int, default=1337, help="set random seed"
    )
    arg_parser.add_argument(
        "-m",
        "--method",
        choices=["c", "s"],
        default="s",
        help="c = evaluate pairwise combos, s = simulate tournament",
    )
    arg_parser.add_argument(
        "-o", "--overrides", action="append", default=[], metavar="ID:NAME:MU:SIGMA",
        help="Override player ratings with custom values"
    )
    arg_parser.add_argument(
        "teams", metavar="STEAMID,STEAMID,...", nargs="*", help="Teams as comma-separated Steam IDs"
    )
    return arg_parser


def main() -> None:
    """
    Main entry point for the team evaluation tool.

    Parses command line arguments, loads player data, and evaluates team matchups.
    """
    opts = make_arg_parser().parse_args()

    # Set random seed for reproducibility
    random.seed(opts.seed)

    # Parse team configurations from command line
    team_configurations: List[List[int]] = [
        [int(player_id) for player_id in team_spec.split(",")]
        for team_spec in opts.teams
    ]
    overrides = parse_overrides(opts.overrides)

    # Find the minimum team size and all player IDs
    team_size = min(len(team_cfg) for team_cfg in team_configurations) if team_configurations else 0
    all_player_ids: Set[int] = set(itertools.chain(*team_configurations))

    # Load player data from database
    with get_skill_db() as skill_db:
        players = get_players_with_overrides(
            skill_db, opts.season, all_player_ids, overrides.values()
        )
        teams: List[List[Player]] = [
            [players[player_id] for player_id in team_cfg]
            for team_cfg in team_configurations
        ]

    # Convert player objects to skill ratings
    skills: List[List[Rating]] = [[player.skill for player in team] for team in teams]

    # Calculate match quality based on selected method
    if opts.method == "c":
        quality = get_assignment_quality(skills)
    else:
        quality = tournament_eval(skills)

    # Display results
    print_match(teams=teams, quality=quality, team_size=team_size)


if __name__ == "__main__":
    main()
