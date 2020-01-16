import json
import bisect
import datetime
import operator
import itertools
from typing import Optional, Iterable

from ..models import GameStateRow


def parse_round_stats(state: GameStateRow) -> {int: dict}:
    assist_counts = {
        steam_id: player['match_stats']['assists']
        for steam_id, player in state.allplayers.items()
    }

    previous_assists = {
        steam_id: player['match_stats']['assists']
        for steam_id, player in state.previous_allplayers.items()
        if 'assists' in state.previous_allplayers.get(
                steam_id, {}).get('match_stats', {})
    }

    return {
        int(steam_id): {
            'kills': player['state']['round_kills'],
            'assists': assist_counts[steam_id] -
                       previous_assists.get(steam_id, 0),
            'survived': player['state']['health'] > 0,
            'damage': player['state']['round_totaldmg'],
        }
        for steam_id, player in state.allplayers.items()
    }


def parse_mvp(state: GameStateRow) -> Optional[int]:
    previous_allplayers = state.previous_allplayers

    mvp_counts = {
        steam_id: player['match_stats']['mvps']
        for steam_id, player in state.allplayers.items()
    }

    previous_mvps = {
        steam_id: player['match_stats']['mvps']
        for steam_id, player in previous_allplayers.items()
        if 'mvps' in previous_allplayers.get(steam_id, {}).get('match_stats', {})
    }

    try:
        mvp = next(
                int(steam_id)
                for steam_id in mvp_counts
                if steam_id in previous_mvps
                and mvp_counts[steam_id] - previous_mvps[steam_id] > 0)
    except StopIteration:
        # Not sure why, but sometimes there is no MVP data in
        # the state's previously.allplayers
        mvp = None

    return mvp


def parse_game_state(
        season_starts: [datetime.datetime],
        season_ids: {datetime.datetime: int},
        state: GameStateRow):
    win_team = state.win_team
    team_steamids = [(player['team'], int(steamid))
                     for steamid, player in state.allplayers.items()]
    team_steamids.sort()
    team_members = {
        team: tuple(sorted(item[1] for item in group))
        for team, group in itertools.groupby(
                team_steamids, operator.itemgetter(0))}
    if len(team_members) != 2:
        return
    lose_team = next(iter(set(team_members.keys()) - {win_team}))

    mvp = parse_mvp(state)

    new_player_states = [
        {
            'teammates': team_members[player['team']],
            'team': player['team'],
            'steam_id': steamid,
            'steam_name': player['name'],
            'round_won': player['team'] == win_team,
        }
        for steamid, player in state.allplayers.items()
    ]

    created_at = datetime.datetime.utcfromtimestamp(state.timestamp)

    season_index = bisect.bisect_left(season_starts, created_at) - 1
    season_id = season_ids[season_starts[season_index]]

    round_stats = parse_round_stats(state)

    new_round = {
        'game_state_id': state.game_state_id,
        'created_at': created_at,
        'season_id': season_id,
        'winner': team_members[win_team],
        'loser': team_members[lose_team],
        'mvp': mvp,
        'map_name': state.map_name,
        'stats': round_stats,
    }

    return new_round, new_player_states


def parse_game_states(game_states: Iterable[GameStateRow], season_ids):
    season_starts = list(season_ids.keys())
    player_states = []
    rounds = []
    max_game_state_id = 0
    for game_state in game_states:
        parsed_game_state = parse_game_state(season_starts, season_ids,
                                             game_state)
        if parsed_game_state is not None:
            new_round, new_player_states = parsed_game_state
            rounds.append(new_round)
            player_states.extend(new_player_states)
            max_game_state_id = max(max_game_state_id,
                                    game_state.game_state_id)
    return rounds, player_states, max_game_state_id
