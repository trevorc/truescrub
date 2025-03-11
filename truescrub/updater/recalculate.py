import itertools
import logging
import operator
import sqlite3
import time
from concurrent.futures import Future
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import trueskill
from trueskill import Rating

from truescrub import db
from truescrub.models import RoundRow, SkillHistory, setup_trueskill
from truescrub.updater.remapper import apply_player_configurations, remap_rounds
from truescrub.updater.state_parser import parse_game_states

# Type aliases
RoundDict = Dict[str, Any]
PlayerState = Dict[str, Any]
TeamMembers = Tuple[int, ...]
TeamID = int
RoundRange = Tuple[int, int]
TeamSet = FrozenSet[int]

logger = logging.getLogger(__name__)
setup_trueskill()


class NoRounds(Exception):
    """Raised when no rounds are found in the database."""

    pass


# Rating2 = 0.2778*Kills - 0.2559*Deaths + 0.00651*ADR + 0.00633*KAST + 0.18377


def load_seasons(game_db: sqlite3.Connection, skill_db: sqlite3.Connection) -> None:
    """
    Load seasons from the game database into the skill database.

    Args:
        game_db: Connection to the game database
        skill_db: Connection to the skill database
    """
    db.replace_seasons(skill_db, db.get_season_rows(game_db))


def replace_teams(
    skill_db: sqlite3.Connection, round_teams: Set[TeamMembers]
) -> Dict[TeamMembers, TeamID]:
    """
    Replace teams in the skill database, adding any missing teams.

    Args:
        skill_db: Connection to the skill database
        round_teams: Set of team member tuples

    Returns:
        Dictionary mapping team members to team IDs
    """
    cursor = skill_db.cursor()
    memberships = {
        tuple(sorted(members)): team_id
        for team_id, members in db.get_all_teams(skill_db).items()
    }
    missing_teams: Set[TeamMembers] = set()

    for team in round_teams:
        if team not in memberships:
            missing_teams.add(team)

    for team in missing_teams:
        cursor.execute("INSERT INTO teams DEFAULT VALUES")
        team_id = cursor.lastrowid
        if team_id is None:
            raise RuntimeError("Failed to get lastrowid from teams insert")

        placeholders = str.join(",", ["(?, ?)"] * len(team))
        params = [param for player_id in team for param in (team_id, player_id)]
        cursor.execute(
            f"""
        INSERT INTO team_membership (team_id, player_id)
        VALUES {placeholders}
        """,
            params,
        )
        memberships[team] = team_id

    return memberships


def insert_players(
    skill_db: sqlite3.Connection, player_states: List[PlayerState]
) -> None:
    """
    Insert players from player states into the skill database.

    Args:
        skill_db: Connection to the skill database
        player_states: List of player state dictionaries
    """
    if len(player_states) == 0:
        return

    players = {int(state["steam_id"]): state["steam_name"] for state in player_states}

    db.upsert_player_names(skill_db, players)


def extract_game_states(
    game_db: sqlite3.Connection, game_state_range: Optional[RoundRange]
) -> Tuple[List[RoundDict], List[PlayerState], int]:
    """
    Extract game states from the game database.

    Args:
        game_db: Connection to the game database
        game_state_range: Optional tuple of (min, max) game state IDs

    Returns:
        Tuple of (rounds, player_states, max_game_state_id)
    """
    season_ids = db.get_seasons_by_start_date(game_db)
    game_states = db.get_game_states(game_db, game_state_range)

    return parse_game_states(game_states, season_ids)


def compute_assists(rounds: List[RoundDict]) -> None:
    """
    Compute assists for each player in each round.

    Args:
        rounds: List of round dictionaries
    """
    last_assists: Dict[str, int] = {}

    # Assumes that players aren't in concurrent matches
    for rnd in rounds:
        for player_id, round_stats in rnd["stats"].items():
            assists = round_stats["match_assists"] - last_assists.get(player_id, 0)
            round_stats["assists"] = assists
            last_assists[player_id] = round_stats["match_assists"]
        if rnd["last_round"]:
            last_assists = {}


def compute_rounds(
    skill_db: sqlite3.Connection,
    rounds: List[RoundDict],
    player_states: List[PlayerState],
) -> RoundRange:
    """
    Compute rounds from game states and player states.

    Args:
        skill_db: Connection to the skill database
        rounds: List of round dictionaries
        player_states: List of player state dictionaries

    Returns:
        Tuple of (min_round_id, max_round_id)
    """
    insert_players(skill_db, player_states)
    round_teams = {player_state["teammates"] for player_state in player_states}
    teams_to_ids = replace_teams(skill_db, round_teams)

    db.replace_maps(skill_db, {rnd["map_name"] for rnd in rounds})

    fixed_rounds = [
        {
            "created_at": rnd["created_at"],
            "season_id": rnd["season_id"],
            "game_state_id": rnd["game_state_id"],
            "winner": teams_to_ids[rnd["winner"]],
            "loser": teams_to_ids[rnd["loser"]],
            "mvp": rnd["mvp"],
            "map_name": rnd["map_name"],
        }
        for rnd in rounds
    ]
    # Cast to expected type for type checking
    from typing import List, cast

    from truescrub.db import RoundData
    round_range = db.insert_rounds(skill_db, cast(List[RoundData], fixed_rounds))

    compute_assists(rounds)
    round_stats = {rnd["game_state_id"]: rnd["stats"] for rnd in rounds}
    db.insert_round_stats(skill_db, round_stats)

    return round_range


def compute_rounds_and_players(
    game_db: sqlite3.Connection,
    skill_db: sqlite3.Connection,
    game_state_range: Optional[RoundRange] = None,
) -> Tuple[int, Optional[RoundRange]]:
    """
    Compute rounds and players from game states.

    Args:
        game_db: Connection to the game database
        skill_db: Connection to the skill database
        game_state_range: Optional tuple of (min, max) game state IDs

    Returns:
        Tuple of (max_game_state_id, optional round range)
    """
    rounds, player_states, max_game_state_id = extract_game_states(
        game_db, game_state_range
    )
    player_states = apply_player_configurations(player_states)

    rounds = remap_rounds(rounds)
    new_rounds = (
        compute_rounds(skill_db, rounds, player_states) if len(rounds) > 0 else None
    )
    return max_game_state_id, new_rounds


# TODO: extract out history tracking for clients that don't need it
def compute_player_skills(
    rounds: List[RoundRow],
    teams: Dict[TeamID, TeamSet],
    current_ratings: Optional[Dict[int, Rating]] = None,
) -> Tuple[Dict[int, Rating], List[SkillHistory]]:
    """
    Compute player skills for a list of rounds.

    Args:
        rounds: List of round rows
        teams: Dictionary mapping team IDs to sets of player IDs
        current_ratings: Optional dictionary of current player ratings

    Returns:
        Tuple of (player_ratings, skill_history)
    """
    ratings: Dict[int, Rating] = {}
    if current_ratings is not None:
        ratings.update(current_ratings)
    skill_history: List[SkillHistory] = []

    for round_row in rounds:
        # Create rating groups for the winner and loser teams
        rating_groups = (
            {
                player_id: ratings.get(player_id, Rating())
                for player_id in teams[round_row.winner]
            },
            {
                player_id: ratings.get(player_id, Rating())
                for player_id in teams[round_row.loser]
            },
        )
        # Update ratings using the TrueSkill algorithm
        new_ratings = trueskill.rate(rating_groups)
        for rating in new_ratings:
            ratings.update(rating)
            for player_id, skill in rating.items():
                skill_history.append(
                    SkillHistory(
                        round_id=round_row.round_id, player_id=player_id, skill=skill
                    )
                )

    return ratings, skill_history


def rate_players_by_season(
    rounds_by_season: Dict[int, List[RoundRow]],
    teams: Dict[TeamID, TeamSet],
    skills_by_season: Optional[Dict[int, Dict[int, Rating]]] = None,
) -> Tuple[Dict[Tuple[int, int], Rating], Dict[int, List[SkillHistory]]]:
    """
    Rate players by season using parallel execution.

    Args:
        rounds_by_season: Dictionary mapping season IDs to lists of round rows
        teams: Dictionary mapping team IDs to sets of player IDs
        skills_by_season: Optional dictionary mapping season IDs to dictionaries of player ratings

    Returns:
        Tuple of (player_season_ratings, history_by_season)
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    # Dictionary to store player skills keyed by (player_id, season)
    skills: Dict[Tuple[int, int], Rating] = {}
    if skills_by_season is None:
        skills_by_season = {}

    # Dictionary to store skill history by season
    history_by_season: Dict[int, List[SkillHistory]] = {}

    with ProcessPoolExecutor() as executor:
        player_skill_futures: Dict[Future, int] = {}
        for season, rounds in rounds_by_season.items():
            future = executor.submit(
                compute_player_skills, rounds, teams, skills_by_season.get(season)
            )
            player_skill_futures[future] = season

    for future in as_completed(player_skill_futures):
        new_skills, skill_history = future.result()
        season = player_skill_futures[future]
        for player_id, rating in new_skills.items():
            skills[(player_id, season)] = rating
        history_by_season[season] = skill_history
    return skills, history_by_season


def recalculate_overall_ratings(
    skill_db: sqlite3.Connection,
    all_rounds: List[RoundRow],
    teams: Dict[TeamID, TeamSet],
) -> None:
    """
    Recalculate overall player ratings from all rounds.

    Args:
        skill_db: Connection to the skill database
        all_rounds: List of all round rows
        teams: Dictionary mapping team IDs to sets of player IDs
    """
    player_ratings = db.get_overall_skills(skill_db)
    skills, skill_history = compute_player_skills(all_rounds, teams, player_ratings)
    impact_ratings = db.get_overall_impact_ratings(skill_db)
    db.update_player_skills(skill_db, skills, impact_ratings)
    db.replace_overall_skill_history(skill_db, skill_history)


def recalculate_season_ratings(
    skill_db: sqlite3.Connection,
    all_rounds: List[RoundRow],
    teams: Dict[TeamID, TeamSet],
) -> None:
    """
    Recalculate player ratings by season.

    Args:
        skill_db: Connection to the skill database
        all_rounds: List of all round rows
        teams: Dictionary mapping team IDs to sets of player IDs
    """
    # Group rounds by season
    rounds_by_season = {
        season_id: list(rounds)
        for season_id, rounds in itertools.groupby(
            all_rounds, operator.attrgetter("season_id")
        )
    }

    # Get current season skills
    current_season_skills = db.get_skills_by_season(
        skill_db, seasons=list(rounds_by_season.keys())
    )

    # Rate players by season
    new_season_skills, history_by_season = rate_players_by_season(
        rounds_by_season, teams, current_season_skills
    )

    # Get impact ratings
    season_impact_ratings = db.get_impact_ratings_by_season(skill_db)

    # Update season skills and history
    db.replace_season_skills(skill_db, new_season_skills, season_impact_ratings)
    db.replace_season_skill_history(skill_db, history_by_season)


def recalculate_ratings(skill_db: sqlite3.Connection, new_rounds: RoundRange) -> None:
    """
    Recalculate player ratings for new rounds.

    Args:
        skill_db: Connection to the skill database
        new_rounds: Tuple of (min_round_id, max_round_id)
    """
    start = time.process_time()
    logger.debug("recalculating for rounds between %d and %d", *new_rounds)

    # Get all rounds in range
    all_rounds = db.get_all_rounds(skill_db, new_rounds)
    # TODO: limit to teams in all_rounds
    teams = db.get_all_teams(skill_db)

    # Recalculate ratings
    recalculate_overall_ratings(skill_db, all_rounds, teams)
    recalculate_season_ratings(skill_db, all_rounds, teams)

    # Log performance
    end = time.process_time()
    logger.debug(
        "recalculation for %d-%d completed in %d ms",
        new_rounds[0],
        new_rounds[1],
        (1000 * (end - start)),
    )


def compute_skill_db(game_db: sqlite3.Connection, skill_db: sqlite3.Connection) -> None:
    """
    Compute the skill database from the game database.

    Args:
        game_db: Connection to the game database
        skill_db: Connection to the skill database
    """
    load_seasons(game_db, skill_db)
    max_game_state_id, new_rounds = compute_rounds_and_players(game_db, skill_db)
    if new_rounds is not None:
        recalculate_ratings(skill_db, new_rounds)
    db.save_game_state_progress(skill_db, max_game_state_id)


def recalculate() -> None:
    """
    Recalculate all skills by creating a new skill database, computing skills,
    and replacing the old database with the new one.
    """
    new_skill_db = db.SKILL_DB_NAME + ".new"
    with db.get_game_db() as game_db, db.get_skill_db(new_skill_db) as skill_db:
        db.initialize_skill_db(skill_db)
        compute_skill_db(game_db, skill_db)
        skill_db.commit()
    db.replace_skill_db(new_skill_db)
