#!/usr/bin/env python3
import datetime
import itertools
import json
import logging
import math
import operator
import os
import re
import time
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
)

import flask
import jinja2
from flask import g, request

import truescrub
from truescrub import db
from truescrub.highlights import get_highlights
from truescrub.matchmaking import (
    MAX_PLAYERS_PER_TEAM,
    compute_matches,
    estimated_skill_range,
    skill_group_ranges,
)
from truescrub.models import Match, Player, skill_group_name, skill_groups


# TypedDict definitions for view models
class ThinPlayerViewModel(TypedDict):
    """Simplified player information for API responses."""
    player_id: int
    steam_name: str
    skill_group: str
    mmr: int


class MatchViewModel(TypedDict):
    """Match information for API responses."""
    team1: List[ThinPlayerViewModel]
    team2: List[ThinPlayerViewModel]
    quality: float
    team1_win_probability: float
    team2_win_probability: float


class PlayerViewModel(TypedDict):
    """Complete player information for API responses."""
    player_id: int
    steam_name: str
    skill: Any  # trueskill.Rating
    skill_group: str
    special_skill_group: str
    mmr: int
    rating_offset: float
    rating_width: float
    lower_bound: str
    upper_bound: str
    impact_rating: str


class SkillPointViewModel(TypedDict):
    """Skill data point for history charts."""
    skill_mean: float
    skill_stdev: float


class RatingComponentViewModel(TypedDict):
    """Component ratings for player performance."""
    mvp_rating: str
    kill_rating: str
    death_rating: str
    damage_rating: str
    kas_rating: str
    impact_rating: str


class SkillGroupViewModel(TypedDict):
    """Skill group information for UI."""
    name: str
    lower_bound: Union[int, str]
    upper_bound: Union[int, str]

app = flask.Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True

jinja2_env = jinja2.Environment(loader=jinja2.PackageLoader(truescrub.__name__))


TRUESCRUB_BRAND = os.environ.get("TRUESCRUB_BRAND", "TrueScrub™")
SHARED_KEY = os.environ.get("TRUESCRUB_KEY", "afohXaef9ighaeSh")
TIMEZONE_PATTERN = re.compile(r"([+-])(\d\d):00")
MAX_MATCHES = 50

logger = logging.getLogger(__name__)


def render_template(template_name: str, **context: Any) -> str:
    return jinja2_env.get_template(template_name).render(**context)


@app.before_request
def start_timer() -> None:
    g.start_time = time.time()


@app.after_request
def end_timer(response: flask.Response) -> flask.Response:
    response_time = "%.2fms" % (1000 * (time.time() - g.start_time))
    response.headers["X-Processing-Time"] = response_time
    return response


@app.before_request
def db_connect() -> None:
    g.conn = db.get_skill_db()


@app.after_request
def db_commit(response: flask.Response) -> flask.Response:
    g.conn.commit()
    return response


@app.teardown_request
def db_close(exc: Optional[Exception]) -> None:
    if hasattr(g, "conn"):
        g.conn.close()


@app.route("/", methods={"GET"})
def index() -> str:
    """
    Render the index page of the application.

    Returns:
        Rendered HTML template for the index page
    """
    seasons = len(db.get_season_range(g.conn))
    season_path = f"/season/{seasons}" if seasons > 1 else ""
    return render_template("index.html", brand=TRUESCRUB_BRAND, season_path=season_path)


@app.route("/api/game_state", methods={"POST"})
def game_state() -> flask.Response:
    """
    Receive and process a game state update from the game.

    Returns:
        HTTP response with success or error status
    """
    logger.debug("accepting game state")
    state_json = request.get_json(force=True)
    if state_json.get("auth", {}).get("token") != SHARED_KEY:
        return flask.make_response("Invalid auth token\n", 403)
    del state_json["auth"]
    state = json.dumps(state_json)
    app.state_writer.send_message(game_state=state)
    return flask.make_response("<h1>OK</h1>\n", 200)


def parse_timezone(tz: str) -> datetime.timezone:
    match = TIMEZONE_PATTERN.match(tz)
    if match is None:
        raise ValueError

    plusminus, offset = match.groups()
    offset_signum = 1 if plusminus == "+" else -1
    offset = datetime.timedelta(hours=offset_signum * int(offset))
    return datetime.timezone(offset=offset)


@app.route(
    "/api/highlights/"
    "<int:year>-<int:month>-<int:day>T"
    "<int:hour>:<int:minute>:<int:second>"
    "<string:tz>",
    methods={"GET"},
)
def highlights(
    year: int, month: int, day: int, hour: int, minute: int, second: int, tz: str
) -> flask.Response:
    try:
        timezone = parse_timezone(tz)
    except ValueError:
        return flask.make_response(f"Invalid timezone {tz}", 404)
    date = datetime.datetime(
        year, month, day, hour, minute, second, tzinfo=timezone
    ).astimezone(timezone.utc)
    try:
        return flask.jsonify(get_highlights(g.conn, date))  # type: ignore
    except StopIteration:
        return flask.make_response(f"No rounds on {date.isoformat()}\n", 404)


def make_thin_player_viewmodel(player: Player) -> ThinPlayerViewModel:
    """
    Create a simplified player view model for API responses.

    Args:
        player: The player object with full information

    Returns:
        A ThinPlayerViewModel with basic player information
    """
    return {
        "player_id": player.player_id,
        "steam_name": player.steam_name,
        "skill_group": skill_group_name(player.skill_group_index),
        "mmr": player.mmr,
    }


def make_match_viewmodel(match: Match) -> MatchViewModel:
    """
    Create a match view model for API responses.

    Args:
        match: The match object with teams and probabilities

    Returns:
        A MatchViewModel with teams and match quality information
    """
    return {
        "team1": [make_thin_player_viewmodel(player) for player in match.team1],
        "team2": [make_thin_player_viewmodel(player) for player in match.team2],
        "quality": match.quality,
        "team1_win_probability": match.team1_win_probability,
        "team2_win_probability": match.team2_win_probability,
    }


@app.route("/api/matchmaking/latest", methods={"GET"})
def latest_matchmaking_api() -> flask.Response:
    """
    API endpoint for getting the latest matchmaking data.

    Returns:
        JSON response with matchmaking results
    """
    try:
        limit = int(request.args.get("limit", 1))
    except ValueError:
        return flask.make_response("Invalid limit\n", 400)
    seasons = db.get_season_range(g.conn)
    if len(seasons) == 0:
        return flask.make_response("No seasons found\n", 404)
    selected_players = db.get_players_in_last_round(g.conn)
    players, matches = compute_matchmaking(seasons[-1], selected_players)

    if matches is not None:
        results = list(itertools.islice(map(make_match_viewmodel, matches), limit))
    else:
        results = []
    return cast(flask.Response, flask.jsonify(results))


@app.route("/api/leaderboard/season/<int:season>", methods={"GET"})
def leaderboard_api(season: int) -> flask.Response:
    """
    API endpoint for getting leaderboard data for a specific season.

    Args:
        season: Season ID to get leaderboard for

    Returns:
        JSON response with player leaderboard data
    """
    players = [
        make_thin_player_viewmodel(player)
        for player in db.get_season_players(g.conn, season)
    ]
    players.sort(key=operator.itemgetter("mmr"), reverse=True)
    return cast(flask.Response, flask.jsonify({"players": players}))


def make_player_viewmodel(player: Player) -> PlayerViewModel:
    """
    Create a complete player view model with all player information.

    Args:
        player: The player object with full information

    Returns:
        A PlayerViewModel with detailed player information for UI
    """
    lower_bound, upper_bound = estimated_skill_range(player.skill)
    min_width = 0.1

    left_offset = min(lower_bound, 1 - min_width)
    right_offset = max(upper_bound, 0 + min_width)

    impact_rating_str = "-" if player.impact_rating is None else f"{player.impact_rating:.2f}"

    return {
        "player_id": player.player_id,
        "steam_name": player.steam_name,
        "skill": player.skill,
        "skill_group": skill_group_name(player.skill_group_index),
        "special_skill_group": skill_group_name(player.skill_group_index, True),
        "mmr": player.mmr,
        "rating_offset": left_offset,
        "rating_width": right_offset - left_offset,
        "lower_bound": f"{lower_bound * 100.0:.1f}",
        "upper_bound": f"{upper_bound * 100.0:.1f}",
        "impact_rating": impact_rating_str,
    }


def make_skill_history_viewmodel(
    history: Dict[str, Player],
) -> Dict[str, SkillPointViewModel]:
    """
    Create a view model of a player's skill history over time.

    Args:
        history: Dictionary mapping dates to player objects

    Returns:
        Dictionary mapping dates to skill point data
    """
    return {
        skill_date: {
            "skill_mean": player.skill.mu,
            "skill_stdev": player.skill.sigma,
        }
        for skill_date, player in history.items()
    }


@app.route("/api/profiles/<int:player_id>/skill_history", methods={"GET"})
def overall_skill_history(player_id: int) -> flask.Response:
    """
    API endpoint for retrieving a player's overall skill history.

    Args:
        player_id: The player ID to get skill history for

    Returns:
        JSON response with skill history data
    """
    tz = request.args.get("tz", "+00:00")
    try:
        timezone = parse_timezone(tz)
    except ValueError:
        return flask.make_response(f"Invalid timezone {tz}", 404)

    skill_history = make_skill_history_viewmodel(
        db.get_overall_skill_history(g.conn, player_id, timezone)
    )
    rating_history = db.get_impact_ratings_by_day(g.conn, player_id, timezone)

    return cast(flask.Response, flask.jsonify(
        {
            "player_id": player_id,
            "skill_history": skill_history,
            "rating_history": rating_history,
        }
    ))


@app.route(
    "/api/profiles/<int:player_id>/skill_history/season/<int:season>", methods={"GET"}
)
def player_skill_history(player_id: int, season: int) -> flask.Response:
    """
    API endpoint for retrieving a player's skill history for a specific season.

    Args:
        player_id: The player ID to get skill history for
        season: The season ID to filter the skill history

    Returns:
        JSON response with season-specific skill history data
    """
    tz = request.args.get("tz", "+00:00")
    try:
        timezone = parse_timezone(tz)
    except ValueError:
        return flask.make_response(f"Invalid timezone {tz}", 404)

    skill_history = make_skill_history_viewmodel(
        db.get_season_skill_history(g.conn, season, player_id, timezone)
    )
    rating_history = db.get_impact_ratings_by_day(g.conn, player_id, timezone, season)

    return cast(flask.Response, flask.jsonify(
        {
            "player_id": player_id,
            "season": season,
            "skill_history": skill_history,
            "rating_history": rating_history,
        }
    ))


@app.route("/leaderboard", methods={"GET"})
def default_leaderboard() -> str:
    """
    Render the default leaderboard page with all players.

    Returns:
        Rendered HTML template with leaderboard data
    """
    players = [make_player_viewmodel(player) for player in db.get_all_players(g.conn)]
    players.sort(key=operator.itemgetter("mmr"), reverse=True)
    seasons = db.get_season_range(g.conn)
    return render_template(
        "leaderboard.html",
        brand=TRUESCRUB_BRAND,
        leaderboard=players,
        seasons=seasons,
        selected_season=None,
    )


@app.route("/leaderboard/season/<int:season>", methods={"GET"})
def leaderboard(season: int) -> str:
    """
    Render the leaderboard page for a specific season.

    Args:
        season: The season ID to filter players

    Returns:
        Rendered HTML template with season-specific leaderboard data
    """
    players = [
        make_player_viewmodel(player)
        for player in db.get_season_players(g.conn, season)
    ]
    players.sort(key=operator.itemgetter("mmr"), reverse=True)
    seasons = db.get_season_range(g.conn)
    return render_template(
        "leaderboard.html", leaderboard=players, seasons=seasons, selected_season=season
    )


def format_bound(bound: Optional[float]) -> Union[int, str]:
    """
    Format a numeric boundary value for display.

    Args:
        bound: The numeric boundary value, or None

    Returns:
        An integer for finite values, or formatted infinity symbol for infinite values,
        or "N/A" if bound is None
    """
    if bound is None:
        return "N/A"
    if math.isfinite(bound):
        return int(bound)
    if bound < 0:
        return "-∞"
    return "∞"


@app.route("/skill_groups", methods={"GET"})
def all_skill_groups() -> str:
    """
    Render the skill groups page showing all skill tiers.

    Returns:
        Rendered HTML template with skill group information
    """
    groups: List[SkillGroupViewModel] = [
        {
            "name": skill_group,
            "lower_bound": format_bound(lower_bound),
            "upper_bound": format_bound(upper_bound),
        }
        for skill_group, lower_bound, upper_bound in skill_group_ranges()
    ]
    return render_template(
        "skill_groups.html", brand=TRUESCRUB_BRAND, skill_groups=groups
    )


def make_rating_component_viewmodel(
    components: Dict[str, float], impact_rating: float
) -> RatingComponentViewModel:
    """
    Create a view model for player rating components.

    Args:
        components: Dictionary of rating component values
        impact_rating: Overall impact rating value

    Returns:
        A RatingComponentViewModel with formatted component values
    """
    return {
        "mvp_rating": f"{int(100 * components['average_mvps'])}%",
        "kill_rating": f"{components['average_kills']:.2f}",
        "death_rating": f"{components['average_deaths']:.2f}",
        "damage_rating": f"{int(components['average_damage'])}",
        "kas_rating": f"{int(100 * components['average_kas'])}%",
        "impact_rating": f"{impact_rating:.2f}",
    }


# For skill group visualization on the profile page
SKILL_GROUPS_VIEWMODEL: List[List[Union[float, str, None]]] = [
    [cutoff if math.isfinite(cutoff) else None, skill_group]
    for cutoff, skill_group in skill_groups()
]


@app.route("/profiles/<int:player_id>", methods={"GET"})
def profile(player_id: int) -> Union[str, flask.Response]:
    """
    Render the player profile page with skill and performance history.

    Args:
        player_id: ID of the player to show profile for

    Returns:
        Rendered HTML template or error response if player not found
    """
    seasons = db.get_season_range(g.conn)
    current_season = len(seasons)

    try:
        player, overall_record = db.get_player_profile(g.conn, player_id)
    except StopIteration:
        return flask.make_response("No such player", 404)

    # Get player skills by season
    skills_by_season = db.get_player_skills_by_season(g.conn, player_id)
    season_skills = [
        (season_id, make_player_viewmodel(season_skill))
        for season_id, season_skill in skills_by_season.items()
    ]
    season_skills.sort(reverse=True)

    # TODO: show percentiles of rating, DPR, KAS, ADR, MVP, KPR

    # Create rating view models
    from typing import Dict, cast
    overall_rating = make_rating_component_viewmodel(
        cast(Dict[str, float], db.get_player_round_stat_averages(g.conn, player_id)),
        player.impact_rating or 0.0  # Default to 0.0 if None
    )

    season_ratings = [
        (
            season_id,
            make_rating_component_viewmodel(
                cast(Dict[str, float], components),
                skills_by_season[season_id].impact_rating or 0.0  # Default to 0.0 if None
            ),
        )
        for season_id, components in db.get_player_round_stat_averages_by_season(
            g.conn, player_id
        ).items()
    ]
    season_ratings.sort(reverse=True)

    player_viewmodel = make_player_viewmodel(player)

    return render_template(
        "profile.html",
        seasons=seasons,
        current_season=current_season,
        player=player_viewmodel,
        overall_record=overall_record,
        overall_rating=overall_rating,
        season_skills=season_skills,
        season_ratings=season_ratings,
        skill_groups=SKILL_GROUPS_VIEWMODEL,
    )


@app.route("/matchmaking", methods={"GET"})
def default_matchmaking() -> Union[str, flask.Response]:
    """
    Render the default matchmaking page with no season filter.

    Returns:
        Rendered HTML template or error response
    """
    return matchmaking(None)


@app.route("/matchmaking/latest", methods={"GET"})
def latest_matchmaking() -> Union[str, flask.Response]:
    """
    Render the matchmaking page for the latest round of players.

    Returns:
        Rendered HTML template or error response
    """
    seasons = db.get_season_range(g.conn)
    if len(seasons) == 0:
        return flask.make_response("No seasons found", 404)
    players = db.get_players_in_last_round(g.conn)
    return matchmaking0(seasons, players, season_id=seasons[-1], latest=True)


@app.route("/matchmaking/season/<int:season_id>", methods={"GET"})
def matchmaking(season_id: Optional[int]) -> Union[str, flask.Response]:
    """
    Render the matchmaking page for a specific season.

    Args:
        season_id: Optional season ID to filter players

    Returns:
        Rendered HTML template or error response
    """
    seasons = db.get_season_range(g.conn)
    selected_players = {int(player_id) for player_id in request.args.getlist("player")}
    return matchmaking0(seasons, selected_players, season_id)


def compute_matchmaking(
    season_id: Optional[int], selected_players: Set[int]
) -> Tuple[List[Player], Optional[Iterator[Match]]]:
    """
    Compute possible matches for a set of selected players.

    Args:
        season_id: Optional season ID to get player data from
        selected_players: Set of player IDs to include in matchmaking

    Returns:
        Tuple containing the list of all players and an optional iterator of matches

    Raises:
        ValueError: If too many players are selected for matchmaking
    """
    max_players = MAX_PLAYERS_PER_TEAM * 2
    if len(selected_players) > max_players:
        raise ValueError(
            f"Cannot compute matches for more than {max_players} players"
        )

    # Get all players from the selected season or all players if no season specified
    players = (
        db.get_all_players(g.conn)
        if season_id is None
        else db.get_season_players(g.conn, season_id)
    )
    players.sort(key=operator.attrgetter("mmr"), reverse=True)

    # Compute matches only if players are selected
    if len(selected_players) > 0:
        filtered_players = [player for player in players if player.player_id in selected_players]
        matches = itertools.islice(
            compute_matches(filtered_players),
            MAX_MATCHES,
        )
    else:
        matches = None

    return players, matches


def matchmaking0(
    seasons: List[int],
    selected_players: Set[int],
    season_id: Optional[int] = None,
    latest: bool = False,
) -> Union[str, flask.Response]:
    """
    Render the matchmaking page with selected players and optional season.

    Args:
        seasons: List of all season IDs
        selected_players: Set of selected player IDs for matchmaking
        season_id: Optional season ID to filter players
        latest: Whether to display the latest matchmaking

    Returns:
        Rendered HTML template or error response
    """
    try:
        players, matches = compute_matchmaking(season_id, selected_players)
    except ValueError as e:
        return flask.make_response(e.args[0], 403)

    return render_template(
        "matchmaking.html",
        brand=TRUESCRUB_BRAND,
        seasons=seasons,
        selected_season=season_id,
        selected_players=selected_players,
        players=players,
        teams=matches,
        latest=latest,
    )
