import configparser
from typing import Any, Dict, List, Set, Tuple

import pkg_resources

__all__ = ["apply_player_configurations", "remap_rounds"]


def parse_player_configuration(
    resource_string: str,
) -> Tuple[Dict[int, Set[str]], Dict[int, int], Set[int]]:
    parser = configparser.RawConfigParser()
    # This is a function attribute that needs special handling for type checking
    parser.optionxform = str  # type: ignore
    parser.read_string(resource_string)
    roles: Dict[int, Set[str]] = {}
    aliases: Dict[int, int] = {}
    ignores: Set[int] = set()
    for key, value in parser.items("Players"):
        player_id, prop = key.split(".", 1)
        player_id_int = int(player_id)
        if prop == "roles":
            roles.setdefault(player_id_int, set()).update(value.split(","))
        elif prop == "aliases":
            for alias in value.split(","):
                aliases[int(alias)] = player_id_int
        elif prop == "ignored":
            ignores.add(player_id_int)
    return roles, aliases, ignores


ROLES, ALIASES, IGNORES = parse_player_configuration(
    pkg_resources.resource_string(__name__, "players.ini").decode("UTF-8")
)


def remap_player_ids(teammates: Tuple[int, ...]) -> Tuple[int, ...]:
    return tuple(
        sorted(
            teammate if teammate not in ALIASES else ALIASES[teammate]
            for teammate in teammates
            if teammate not in IGNORES
        )
    )


def remap_round_stats(round_stats: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    # Assumes that a player and his aliases are in a round together
    return {
        (steam_id if steam_id not in ALIASES else ALIASES[steam_id]): stats
        for steam_id, stats in round_stats.items()
        if steam_id not in IGNORES
    }


def remap_player_state(player_state: Dict[str, Any]) -> Dict[str, Any]:
    player_state = player_state.copy()
    if player_state["steam_id"] in ALIASES:
        player_state["steam_id"] = ALIASES[player_state["steam_id"]]
    player_state["teammates"] = remap_player_ids(player_state["teammates"])
    return player_state


def remap_round(round_data: Dict[str, Any]) -> Dict[str, Any]:
    round_data = round_data.copy()
    round_data["winner"] = remap_player_ids(round_data["winner"])
    round_data["loser"] = remap_player_ids(round_data["loser"])
    round_data["stats"] = remap_round_stats(round_data["stats"])
    round_data["mvp"] = (
        None
        if round_data["mvp"] in IGNORES
        else round_data["mvp"] if round_data["mvp"] not in ALIASES else ALIASES[round_data["mvp"]]
    )
    return round_data


def remap_rounds(rounds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    new_rounds = []
    for round_data in rounds:
        remapped_round = remap_round(round_data)
        if len(remapped_round["winner"]) > 0 and len(remapped_round["loser"]) > 0:
            new_rounds.append(remapped_round)
    return new_rounds


def apply_player_configurations(player_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    new_player_states = [
        remap_player_state(player_state)
        for player_state in player_states
        if player_state["steam_id"] not in IGNORES
    ]
    return new_player_states
