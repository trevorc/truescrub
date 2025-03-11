import bisect
import datetime
import itertools
import operator
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from truescrub.models import GameStateRow


def parse_round_stats(allplayers: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    assist_counts = {
        steam_id: player["match_stats"]["assists"]
        for steam_id, player in allplayers.items()
    }

    return {
        int(steam_id): {
            "kills": player["state"]["round_kills"],
            "match_assists": assist_counts[steam_id],
            "survived": player["state"]["health"] > 0,
            "damage": player["state"]["round_totaldmg"],
        }
        for steam_id, player in allplayers.items()
    }


def parse_mvp(state: GameStateRow) -> Optional[int]:
    previous_allplayers = state.previous_allplayers

    mvp_counts = {
        steam_id: player["match_stats"]["mvps"]
        for steam_id, player in state.allplayers.items()
    }

    previous_mvps = {
        steam_id: player["match_stats"]["mvps"]
        for steam_id, player in previous_allplayers.items()
        if "mvps" in previous_allplayers.get(steam_id, {}).get("match_stats", {})
    }

    try:
        mvp = next(
            int(steam_id)
            for steam_id in mvp_counts
            if steam_id in previous_mvps
            and mvp_counts[steam_id] - previous_mvps[steam_id] > 0
        )
    except StopIteration:
        # Not sure why, but sometimes there is no MVP data in
        # the state's previously.allplayers
        mvp = None

    return mvp


PRIMARY_WEAPONS = {
    "weapon_famas",
    "weapon_ak47",
    "weapon_m4a1_silencer",
    "weapon_sawedoff",
    "weapon_ump45",
    "weapon_p90",
    "weapon_m4a1",
    "weapon_mp9",
    "weapon_nova",
    "weapon_negev",
    "weapon_g3sg1",
    "weapon_mp7",
    "weapon_mag7",
    "weapon_ssg08",
    "weapon_sg556",
    "weapon_bizon",
    "weapon_m249",
    "weapon_galilar",
    "weapon_scar20",
    "weapon_aug",
    "weapon_mac10",
    "weapon_awp",
    "weapon_xm1014",
}

SECONDARY_WEAPONS = {
    "weapon_tec9",
    "weapon_p250",
    "weapon_usp_silencer",
    "weapon_hkp2000",
    "weapon_cz75a",
    "weapon_fiveseven",
    "weapon_elite",
    "weapon_glock",
    "weapon_deagle",
    "weapon_revolver",
}

GRENADE_WEAPONS = {
    "weapon_flashbang",
    "weapon_smokegrenade",
    "weapon_hegrenade",
    "weapon_incgrenade",
    "weapon_decoy",
    "weapon_molotov",
}


def filter_weapons(
    allplayers: Dict[str, Dict[str, Any]], weapon_set: Set[str]
) -> Iterable[Tuple[int, str]]:
    for player_id, player in allplayers.items():
        for weapon in player["weapons"].values():
            if weapon["name"] in weapon_set:
                yield int(player_id), weapon["name"]


def parse_freezetime_transition(state: GameStateRow) -> Dict[int, Dict[str, Any]]:
    if state.round_phase != "live":
        raise ValueError('Expected round_phase "live"')

    round_weapons: Dict[int, Dict[str, Any]] = {}
    for player_id, player in state.allplayers.items():
        player_weapons = round_weapons.setdefault(int(player_id), {})
        for weapon in player["weapons"].values():
            weapon_name = weapon["name"]
            if weapon_name in PRIMARY_WEAPONS:
                player_weapons["primary"] = weapon_name
            elif weapon_name in SECONDARY_WEAPONS:
                player_weapons["secondary"] = weapon_name
            elif weapon_name == "weapon_taser":
                player_weapons["taser"] = True
            elif weapon_name in GRENADE_WEAPONS:
                player_weapons[weapon_name[len("weapon_") :]] = True
    return round_weapons


def parse_roundover_transition(
    season_starts: List[datetime.datetime],
    season_ids: Dict[datetime.datetime, int],
    state: GameStateRow,
) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    if state.round_phase != "over":
        raise ValueError('Expected round_phase "over"')

    allplayers = {
        steamid: player
        for steamid, player in state.allplayers.items()
        if player["name"] != "unconnected"
    }

    win_team = state.win_team
    team_steamids = [
        (player["team"], int(steamid)) for steamid, player in allplayers.items()
    ]
    team_steamids.sort()
    team_members = {
        team: tuple(sorted(item[1] for item in group))
        for team, group in itertools.groupby(team_steamids, operator.itemgetter(0))
    }
    if len(team_members) != 2:
        return None
    lose_team = next(team_name for team_name in team_members if team_name != win_team)

    mvp = parse_mvp(state)

    new_player_states = [
        {
            "teammates": team_members[player["team"]],
            "team": player["team"],
            "steam_id": int(steamid),
            "steam_name": player["name"],
            "round_won": player["team"] == win_team,
        }
        for steamid, player in allplayers.items()
    ]

    created_at = datetime.datetime.utcfromtimestamp(state.timestamp)

    season_index = bisect.bisect_left(season_starts, created_at) - 1
    season_id = season_ids[season_starts[season_index]]

    round_stats = parse_round_stats(allplayers)

    new_round = {
        "game_state_id": state.game_state_id,
        "created_at": created_at,
        "season_id": season_id,
        "winner": team_members[win_team],
        "loser": team_members[lose_team],
        "mvp": mvp,
        "map_name": state.map_name.lower(),
        "stats": round_stats,
        "last_round": state.map_phase == "gameover",
    }

    return new_round, new_player_states


def parse_game_states(
    game_states: Iterable[GameStateRow], season_ids: Dict[datetime.datetime, int]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    season_starts = list(season_ids.keys())
    player_states: List[Dict[str, Any]] = []
    rounds: List[Dict[str, Any]] = []
    max_game_state_id = 0

    for game_state in game_states:
        roundover_state = parse_roundover_transition(
            season_starts, season_ids, game_state
        )
        if roundover_state is not None:
            new_round, new_player_states = roundover_state
            rounds.append(new_round)
            player_states.extend(new_player_states)
            max_game_state_id = max(max_game_state_id, game_state.game_state_id)
    return rounds, player_states, max_game_state_id
