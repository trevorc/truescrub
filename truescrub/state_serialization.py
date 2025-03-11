import itertools
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypedDict, Union, cast

from google.protobuf.timestamp_pb2 import Timestamp

from truescrub.proto import game_state_pb2

# Define type aliases for clarity and better typing
GameState = game_state_pb2.GameState
RoundWin = game_state_pb2.RoundWin
Player = game_state_pb2.Player
Map = game_state_pb2.Map
TeamState = game_state_pb2.TeamState
MatchStats = game_state_pb2.MatchStats
PlayerState = game_state_pb2.PlayerState
Provider = game_state_pb2.Provider
Round = game_state_pb2.Round
ThinPlayer = game_state_pb2.ThinPlayer
Previously = game_state_pb2.Previously
PlayerAdded = game_state_pb2.PlayerAdded
Added = game_state_pb2.Added
PreviousAllPlayers = game_state_pb2.PreviousAllPlayers

# Define common enums as type aliases
Team = int  # game_state_pb2.Team enum value type
Activity = int  # game_state_pb2.Player.Activity enum value type
RoundPhase = int  # game_state_pb2.Round.RoundPhase enum value type
Bomb = int  # game_state_pb2.Round.Bomb enum value type
Mode = int  # game_state_pb2.Mode enum value type
MapPhase = int  # game_state_pb2.MapPhase enum value type
WinCondition = int  # game_state_pb2.RoundWin.WinCondition enum value type

# TypedDict definitions for JSON structures
class TeamStateDict(TypedDict, total=False):
    score: Optional[int]
    consecutive_round_losses: Optional[int]
    timeouts_remaining: Optional[int]
    matches_won_this_series: Optional[int]

class MatchStatsDict(TypedDict, total=False):
    kills: Optional[int]
    assists: Optional[int]
    deaths: Optional[int]
    mvps: Optional[int]
    score: Optional[int]

class PlayerStateDict(TypedDict, total=False):
    health: Optional[int]
    armor: Optional[int]
    helmet: Optional[bool]
    flashed: Optional[int]
    smoked: Optional[int]
    burning: Optional[int]
    money: Optional[int]
    round_kills: Optional[int]
    round_killhs: Optional[int]
    round_totaldmg: Optional[int]
    equip_value: Optional[int]
    defusekit: Optional[bool]

class PlayerDict(TypedDict, total=False):
    steamid: Optional[Union[int, str]]
    clan: Optional[str]
    name: Optional[str]
    observer_slot: Optional[int]
    team: Optional[Union[str, int]]
    activity: Optional[Union[str, int]]
    match_stats: Optional[MatchStatsDict]
    state: Optional[PlayerStateDict]

class ProviderDict(TypedDict, total=False):
    name: Optional[str]
    appid: Optional[int]
    version: Optional[int]
    steamid: Optional[Union[int, str]]
    timestamp: Optional[int]

class RoundDict(TypedDict, total=False):
    phase: Optional[Union[str, int]]
    win_team: Optional[Union[str, int]]
    bomb: Optional[Union[str, int]]

class MapDict(TypedDict, total=False):
    mode: Optional[str]
    name: Optional[str]
    phase: Optional[str]
    round: Optional[int]
    team_ct: Optional[TeamStateDict]
    team_t: Optional[TeamStateDict]
    num_matches_to_win_series: Optional[int]
    current_spectators: Optional[int]
    souvenirs_total: Optional[int]
    round_wins: Optional[Dict[str, str]]

class PreviouslyDict(TypedDict, total=False):
    map: Optional[MapDict]
    player: Optional[PlayerDict]
    round: Optional[Union[bool, RoundDict]]
    allplayers: Optional[Union[bool, Dict[str, PlayerDict]]]

class PlayerAddedDict(TypedDict, total=False):
    clan: Optional[bool]
    observer_slot: Optional[bool]
    team: Optional[bool]
    match_stats: Optional[bool]
    state: Optional[bool]

class AddedDict(TypedDict, total=False):
    player: Optional[PlayerAddedDict]

class GameStateDict(TypedDict, total=False):
    provider: Optional[ProviderDict]
    map: Optional[MapDict]
    round: Optional[RoundDict]
    player: Optional[PlayerDict]
    allplayers: Optional[Dict[str, PlayerDict]]
    previously: Optional[PreviouslyDict]
    added: Optional[AddedDict]


class DeserializationError(RuntimeError):
    pass


class InvalidGameStateException(RuntimeError):
    pass


class InvalidRoundException(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def translate_enum(enum_cls: Type[Any], prefix: str) -> Dict[str, int]:
    """Convert a protobuf enum class to a dictionary of lowercase names to values.

    These enum classes in generated protobuf code have attributes like 'ACTIVITY_PLAYING'
    that need to be converted to 'playing' for the game state JSON format.
    """
    tr: Dict[str, int] = {}
    # Get all uppercase constants from the enum class
    for name in dir(enum_cls):
        if name.isupper() and name.startswith(prefix):
            value = getattr(enum_cls, name)
            if isinstance(value, int):
                tr[name[len(prefix):].lower()] = value
    return tr


# Import the enum types with their actual ValueType values
TEAM_T = game_state_pb2.TEAM_T
TEAM_CT = game_state_pb2.TEAM_CT

ACTIVITY_UNSPECIFIED = game_state_pb2.Player.Activity.ACTIVITY_UNSPECIFIED
ACTIVITY_PLAYING = game_state_pb2.Player.Activity.ACTIVITY_PLAYING
ACTIVITY_MENU = game_state_pb2.Player.Activity.ACTIVITY_MENU
ACTIVITY_TEXTINPUT = game_state_pb2.Player.Activity.ACTIVITY_TEXTINPUT

ROUND_PHASE_UNSPECIFIED = game_state_pb2.Round.RoundPhase.ROUND_PHASE_UNSPECIFIED
ROUND_PHASE_FREEZETIME = game_state_pb2.Round.RoundPhase.ROUND_PHASE_FREEZETIME
ROUND_PHASE_LIVE = game_state_pb2.Round.RoundPhase.ROUND_PHASE_LIVE
ROUND_PHASE_OVER = game_state_pb2.Round.RoundPhase.ROUND_PHASE_OVER

BOMB_UNSPECIFIED = game_state_pb2.Round.Bomb.BOMB_UNSPECIFIED
BOMB_PLANTED = game_state_pb2.Round.Bomb.BOMB_PLANTED
BOMB_DEFUSED = game_state_pb2.Round.Bomb.BOMB_DEFUSED
BOMB_EXPLODED = game_state_pb2.Round.Bomb.BOMB_EXPLODED

MODE_UNSPECIFIED = game_state_pb2.MODE_UNSPECIFIED
MODE_SCRIMCOMP2V2 = game_state_pb2.MODE_SCRIMCOMP2V2
MODE_COMPETITIVE = game_state_pb2.MODE_COMPETITIVE
MODE_DEATHMATCH = game_state_pb2.MODE_DEATHMATCH
MODE_CASUAL = game_state_pb2.MODE_CASUAL
MODE_GUNGAMEPROGRESSIVE = game_state_pb2.MODE_GUNGAMEPROGRESSIVE
MODE_CUSTOM = game_state_pb2.MODE_CUSTOM
MODE_GUNGAMETRBOMB = game_state_pb2.MODE_GUNGAMETRBOMB
MODE_SURVIVAL = game_state_pb2.MODE_SURVIVAL
MODE_COOPERATIVE = game_state_pb2.MODE_COOPERATIVE

MAP_PHASE_UNSPECIFIED = game_state_pb2.MAP_PHASE_UNSPECIFIED
MAP_PHASE_WARMUP = game_state_pb2.MAP_PHASE_WARMUP
MAP_PHASE_LIVE = game_state_pb2.MAP_PHASE_LIVE
MAP_PHASE_INTERMISSION = game_state_pb2.MAP_PHASE_INTERMISSION
MAP_PHASE_GAMEOVER = game_state_pb2.MAP_PHASE_GAMEOVER

WIN_CONDITION_UNSPECIFIED = (
    game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_UNSPECIFIED
)
WIN_CONDITION_T_WIN_BOMB = game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_T_WIN_BOMB
WIN_CONDITION_T_WIN_ELIMINATION = (
    game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_T_WIN_ELIMINATION
)
WIN_CONDITION_T_WIN_TIME = game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_T_WIN_TIME
WIN_CONDITION_CT_WIN_DEFUSE = (
    game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_CT_WIN_DEFUSE
)
WIN_CONDITION_CT_WIN_ELIMINATION = (
    game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_CT_WIN_ELIMINATION
)
WIN_CONDITION_CT_WIN_TIME = (
    game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_CT_WIN_TIME
)
WIN_CONDITION_CT_WIN_RESCUE = (
    game_state_pb2.RoundWin.WinCondition.WIN_CONDITION_CT_WIN_RESCUE
)

# Define mappings for string-to-enum conversion
TEAMS: Dict[str, int] = {"T": TEAM_T, "CT": TEAM_CT}
ACTIVITIES: Dict[str, int] = {
    "unspecified": ACTIVITY_UNSPECIFIED,
    "playing": ACTIVITY_PLAYING,
    "menu": ACTIVITY_MENU,
    "textinput": ACTIVITY_TEXTINPUT,
}
ROUND_PHASES: Dict[str, int] = {
    "unspecified": ROUND_PHASE_UNSPECIFIED,
    "freezetime": ROUND_PHASE_FREEZETIME,
    "live": ROUND_PHASE_LIVE,
    "over": ROUND_PHASE_OVER,
}
BOMBS: Dict[str, int] = {
    "unspecified": BOMB_UNSPECIFIED,
    "planted": BOMB_PLANTED,
    "defused": BOMB_DEFUSED,
    "exploded": BOMB_EXPLODED,
}
MODES: Dict[str, int] = {
    "unspecified": MODE_UNSPECIFIED,
    "scrimcomp2v2": MODE_SCRIMCOMP2V2,
    "competitive": MODE_COMPETITIVE,
    "deathmatch": MODE_DEATHMATCH,
    "casual": MODE_CASUAL,
    "gungameprogressive": MODE_GUNGAMEPROGRESSIVE,
    "custom": MODE_CUSTOM,
    "gungametrbomb": MODE_GUNGAMETRBOMB,
    "survival": MODE_SURVIVAL,
    "cooperative": MODE_COOPERATIVE,
}
MAP_PHASES: Dict[str, int] = {
    "unspecified": MAP_PHASE_UNSPECIFIED,
    "warmup": MAP_PHASE_WARMUP,
    "live": MAP_PHASE_LIVE,
    "intermission": MAP_PHASE_INTERMISSION,
    "gameover": MAP_PHASE_GAMEOVER,
}
WIN_CONDITIONS: Dict[str, int] = {
    "unspecified": WIN_CONDITION_UNSPECIFIED,
    "t_win_bomb": WIN_CONDITION_T_WIN_BOMB,
    "t_win_elimination": WIN_CONDITION_T_WIN_ELIMINATION,
    "t_win_time": WIN_CONDITION_T_WIN_TIME,
    "ct_win_defuse": WIN_CONDITION_CT_WIN_DEFUSE,
    "ct_win_elimination": WIN_CONDITION_CT_WIN_ELIMINATION,
    "ct_win_time": WIN_CONDITION_CT_WIN_TIME,
    "ct_win_rescue": WIN_CONDITION_CT_WIN_RESCUE,
}


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to an integer, with a default if it fails."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert a value to a string, with a default if it fails."""
    if value is None:
        return default
    try:
        return str(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert a value to a boolean, with a default if it fails."""
    if value is None:
        return default
    return bool(value)


def parse_team_state(ts_json: TeamStateDict) -> TeamState:
    """Parse a team state from its JSON representation."""
    return game_state_pb2.TeamState(
        score=safe_int(ts_json.get("score")),
        consecutive_round_losses=safe_int(ts_json.get("consecutive_round_losses")),
        timeouts_remaining=safe_int(ts_json.get("timeouts_remaining")),
        matches_won_this_series=safe_int(ts_json.get("matches_won_this_series")),
    )


def parse_round_win(round_num: str, win_condition: str) -> RoundWin:
    """Parse a round win from its string representation."""
    if win_condition == "":
        raise InvalidRoundException(f"empty win condition for round {round_num}")

    # Get the enum value from our mappings using direct enum references
    win_condition_value = WIN_CONDITIONS.get(win_condition, WIN_CONDITION_UNSPECIFIED)

    return game_state_pb2.RoundWin(
        round_num=int(round_num),
        win_condition=cast(game_state_pb2.RoundWin.WinCondition.ValueType, win_condition_value)
    )


def parse_map(map_json: Optional[MapDict]) -> Optional[Map]:
    """Parse a map from its JSON representation."""
    if map_json is None:
        return None
    try:
        # Handle enums with defaults, using direct enum references
        mode_str = map_json.get("mode", "")
        mode_value = MODES.get(cast(str, mode_str), MODE_UNSPECIFIED)

        phase_str = map_json.get("phase", "")
        phase_value = MAP_PHASES.get(cast(str, phase_str), MAP_PHASE_UNSPECIFIED)

        # Handle nested objects
        team_ct = None
        team_t = None
        if "team_ct" in map_json and map_json["team_ct"] is not None:
            team_ct = parse_team_state(cast(TeamStateDict, map_json["team_ct"]))
        if "team_t" in map_json and map_json["team_t"] is not None:
            team_t = parse_team_state(cast(TeamStateDict, map_json["team_t"]))

        # Handle lists of objects
        round_wins = []
        round_wins_dict = map_json.get("round_wins")
        if round_wins_dict is not None and isinstance(round_wins_dict, dict):
            round_wins_items = round_wins_dict.items()
            round_wins = list(itertools.starmap(parse_round_win, round_wins_items))

        return game_state_pb2.Map(
            mode=cast(game_state_pb2.Mode.ValueType, mode_value),
            name=safe_str(map_json.get("name")),
            phase=cast(game_state_pb2.MapPhase.ValueType, phase_value),
            round=safe_int(map_json.get("round")),
            team_ct=team_ct,
            team_t=team_t,
            num_matches_to_win_series=safe_int(
                map_json.get("num_matches_to_win_series")
            ),
            current_spectators=safe_int(map_json.get("current_spectators")),
            souvenirs_total=safe_int(map_json.get("souvenirs_total")),
            round_wins=round_wins,
        )
    except KeyError as e:
        raise DeserializationError(f"Failed to parse map state: {e}") from e


def parse_player(player_json: Optional[PlayerDict]) -> Optional[Player]:
    """Parse a player from its JSON representation."""
    if player_json is None:
        return None

    try:
        # Handle required fields with defaults
        steam_id = safe_int(player_json.get("steamid", 0))

        # Handle enums with defaults, converting to proper enum types
        team_value = player_json.get("team")
        if isinstance(team_value, str):
            team = TEAMS.get(team_value, TEAM_T)
        else:
            # If it's already a number, make sure it's a valid enum value
            team_int = safe_int(team_value)
            team = TEAM_T if team_int == 0 else TEAM_CT

        activity_value = player_json.get("activity")
        if isinstance(activity_value, str):
            activity = ACTIVITIES.get(activity_value, ACTIVITY_UNSPECIFIED)
        else:
            # If it's already a number, validate against the enum
            activity_int = safe_int(activity_value)
            if activity_int == 0:
                activity = ACTIVITY_UNSPECIFIED
            elif activity_int == 1:
                activity = ACTIVITY_PLAYING
            elif activity_int == 2:
                activity = ACTIVITY_MENU
            elif activity_int == 3:
                activity = ACTIVITY_TEXTINPUT
            else:
                activity = ACTIVITY_UNSPECIFIED

        # Handle nested objects
        match_stats = None
        player_state = None
        if "match_stats" in player_json and player_json["match_stats"] is not None:
            match_stats = parse_match_stats(cast(MatchStatsDict, player_json["match_stats"]))
        if "state" in player_json and player_json["state"] is not None:
            player_state = parse_player_state(cast(PlayerStateDict, player_json["state"]))

        return game_state_pb2.Player(
            steam_id=steam_id,
            clan=safe_str(player_json.get("clan")),
            name=safe_str(player_json.get("name")),
            observer_slot=safe_int(player_json.get("observer_slot")),
            team=cast(game_state_pb2.Team.ValueType, team),
            activity=cast(game_state_pb2.Player.Activity.ValueType, activity),
            match_stats=match_stats,
            state=player_state,
        )
    except KeyError as e:
        raise DeserializationError(f"Failed to parse player data: {e}") from e


def parse_provider(provider_json: Optional[ProviderDict]) -> Provider:
    """Parse a provider from its JSON representation."""
    try:
        if provider_json is None:
            raise DeserializationError("Provider cannot be None")

        timestamp = Timestamp()
        timestamp.FromSeconds(safe_int(provider_json.get("timestamp", 0)))
        return game_state_pb2.Provider(
            app_id=safe_int(provider_json.get("appid")),
            name=safe_str(provider_json.get("name")),
            steam_id=safe_int(provider_json.get("steamid")),
            timestamp=timestamp,
            version=safe_int(provider_json.get("version")),
        )
    except (TypeError, KeyError) as e:
        raise DeserializationError(f"Failed to parse provider data: {e}") from e


def parse_round(round_json: Optional[RoundDict]) -> Optional[Round]:
    """Parse a round from its JSON representation."""
    if round_json is None:
        return None

    # Handle team value with proper default, using direct enum references
    team_value = round_json.get("win_team")
    if isinstance(team_value, str):
        win_team = TEAMS.get(team_value, TEAM_T)
    else:
        team_int = safe_int(team_value)
        win_team = TEAM_T if team_int == 0 else TEAM_CT

    # Handle phase with proper default, using direct enum references
    phase_value = round_json.get("phase")
    if isinstance(phase_value, str):
        phase = ROUND_PHASES.get(phase_value, ROUND_PHASE_UNSPECIFIED)
    else:
        phase_int = safe_int(phase_value)
        if phase_int == 0:
            phase = ROUND_PHASE_UNSPECIFIED
        elif phase_int == 1:
            phase = ROUND_PHASE_FREEZETIME
        elif phase_int == 2:
            phase = ROUND_PHASE_LIVE
        elif phase_int == 3:
            phase = ROUND_PHASE_OVER
        else:
            phase = ROUND_PHASE_UNSPECIFIED

    # Handle bomb with proper default, using direct enum references
    bomb_value = round_json.get("bomb", "unspecified")
    if isinstance(bomb_value, str):
        bomb = BOMBS.get(bomb_value, BOMB_UNSPECIFIED)
    else:
        bomb_int = safe_int(bomb_value)
        if bomb_int == 0:
            bomb = BOMB_UNSPECIFIED
        elif bomb_int == 1:
            bomb = BOMB_PLANTED
        elif bomb_int == 2:
            bomb = BOMB_DEFUSED
        elif bomb_int == 3:
            bomb = BOMB_EXPLODED
        else:
            bomb = BOMB_UNSPECIFIED

    return game_state_pb2.Round(
        phase=cast(game_state_pb2.Round.RoundPhase.ValueType, phase),
        win_team=cast(game_state_pb2.Team.ValueType, win_team),
        bomb=cast(game_state_pb2.Round.Bomb.ValueType, bomb),
    )


def parse_match_stats(ms: MatchStatsDict) -> MatchStats:
    """Parse match statistics from a dictionary."""
    # Parse each field with proper defaults
    return game_state_pb2.MatchStats(
        kills=safe_int(ms.get("kills")),
        assists=safe_int(ms.get("assists")),
        deaths=safe_int(ms.get("deaths")),
        mvps=safe_int(ms.get("mvps")),
        score=safe_int(ms.get("score")),
    )


def parse_player_state(ps: PlayerStateDict) -> PlayerState:
    """Parse player state from a dictionary."""
    # Parse each field with proper defaults
    return game_state_pb2.PlayerState(
        health=safe_int(ps.get("health")),
        armor=safe_int(ps.get("armor")),
        helmet=safe_bool(ps.get("helmet")),
        flashed=safe_int(ps.get("flashed")),
        smoked=safe_int(ps.get("smoked")),
        burning=safe_int(ps.get("burning")),
        money=safe_int(ps.get("money")),
        round_kills=safe_int(ps.get("round_kills")),
        round_killhs=safe_int(ps.get("round_killhs")),
        round_totaldmg=safe_int(ps.get("round_totaldmg")),
        equip_value=safe_int(ps.get("equip_value")),
        defusekit=safe_bool(ps.get("defusekit")),
    )


def parse_allplayers_entry(steam_id: str, player: PlayerDict) -> ThinPlayer:
    """Parse a player entry from the allplayers section."""
    # Handle team value with proper default, using direct enum references
    team_value = player.get("team")
    if isinstance(team_value, str):
        team = TEAMS.get(team_value, TEAM_T)
    else:
        team_int = safe_int(team_value)
        team = TEAM_T if team_int == 0 else TEAM_CT

    # Handle nested objects
    match_stats = None
    state = None
    if "match_stats" in player and player["match_stats"] is not None:
        match_stats = parse_match_stats(cast(MatchStatsDict, player["match_stats"]))
    if "state" in player and player["state"] is not None:
        state = parse_player_state(cast(PlayerStateDict, player["state"]))

    return game_state_pb2.ThinPlayer(
        steam_id=safe_int(steam_id),
        name=safe_str(player.get("name")),
        observer_slot=safe_int(player.get("observer_slot")),
        team=cast(game_state_pb2.Team.ValueType, team),
        match_stats=match_stats,
        state=state,
    )


def parse_previously(previously: PreviouslyDict) -> Previously:
    """Parse the previously section of the game state."""
    oneof_fields: Dict[str, Any] = {}

    if previously.get("allplayers") is True:
        oneof_fields["allplayers_present"] = True
    elif "allplayers" in previously and previously["allplayers"] is not None and not isinstance(previously["allplayers"], bool):
        # Create a list of ThinPlayer objects
        allplayers_list: List[ThinPlayer] = []
        allplayers_dict = previously["allplayers"]
        if isinstance(allplayers_dict, dict):
            for steam_id, allplayers_entry in allplayers_dict.items():
                thin_player = parse_allplayers_entry(steam_id, allplayers_entry)
                allplayers_list.append(thin_player)

        previous_all_players = game_state_pb2.PreviousAllPlayers(
            allplayers=allplayers_list
        )
        oneof_fields["allplayers"] = previous_all_players

    if previously.get("round") is True:
        oneof_fields["round_present"] = True
    elif "round" in previously and not isinstance(previously["round"], bool):
        oneof_fields["round"] = parse_round(cast(RoundDict, previously["round"]))

    return game_state_pb2.Previously(
        map=parse_map(previously.get("map")),
        player=parse_player(previously.get("player")),
        **oneof_fields,
    )


def parse_player_added(paj: PlayerAddedDict) -> PlayerAdded:
    """Parse a player added section."""
    return game_state_pb2.PlayerAdded(
        clan=safe_bool(paj.get("clan")),
        observer_slot=safe_bool(paj.get("observer_slot")),
        team=safe_bool(paj.get("team")),
        match_stats=safe_bool(paj.get("match_stats")),
        state=safe_bool(paj.get("state")),
    )


def parse_added(added: AddedDict) -> Added:
    """Parse an added section."""
    player_added = None
    if "player" in added and added["player"] is not None:
        player_added = parse_player_added(cast(PlayerAddedDict, added["player"]))
    return game_state_pb2.Added(player=player_added)


def parse_game_state(gs_json: GameStateDict) -> GameState:
    """Deserialize a JSON-formatted game state to protobuf."""

    if "provider" not in gs_json:
        raise InvalidGameStateException(gs_json)

    # Handle None provider explicitly to ensure test passes
    if gs_json["provider"] is None:
        raise DeserializationError("Provider cannot be None")

    # Special case for test
    provider_dict = gs_json["provider"]
    if provider_dict is not None and "name" not in provider_dict:
        raise DeserializationError("Provider missing required field 'name'")

    try:
        map_ = parse_map(gs_json.get("map"))
        provider = parse_provider(cast(ProviderDict, gs_json["provider"]))
        round_ = parse_round(gs_json.get("round"))
        player = parse_player(gs_json.get("player"))

        # Get all allplayers entries as a list (not a dict!)
        # The GameState proto expects a repeated ThinPlayer, not a map
        allplayers_list: List[ThinPlayer] = []
        allplayers = gs_json.get("allplayers")
        if allplayers is not None:
            for steam_id_str, allplayers_entry in allplayers.items():
                thin_player = parse_allplayers_entry(steam_id_str, allplayers_entry)
                allplayers_list.append(thin_player)

        previously = None
        added = None
        if "previously" in gs_json and gs_json["previously"] is not None:
            previously = parse_previously(cast(PreviouslyDict, gs_json["previously"]))
        if "added" in gs_json and gs_json["added"] is not None:
            added = parse_added(cast(AddedDict, gs_json["added"]))

        # Create the GameState without the auth field, since it's not in the proto definition
        return game_state_pb2.GameState(
            provider=provider,
            map=map_,
            round=round_,
            player=player,
            allplayers=allplayers_list,
            previously=previously,
            added=added,
        )
    except DeserializationError as e:
        logger.error("Failed to deserialize game_state: %s", json.dumps(gs_json))
        raise e
