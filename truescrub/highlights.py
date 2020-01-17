import datetime
import operator

from .db import execute_one, execute, COEFFICIENTS
from .models import Player


def get_highlights(skill_db, day: datetime.datetime) -> dict:
    round_range, rounds_played = get_round_range_for_day(skill_db, day)

    if rounds_played == 0:
        raise StopIteration

    player_ratings = get_player_ratings_between_rounds(skill_db, round_range)
    most_played_maps = get_most_played_maps_between_rounds(
            skill_db, round_range)
    skill_group_changes = [
        {
            'player_id': previous_skill.player_id,
            'steam_name': previous_skill.steam_name,
            'previous_skill': {
                'mmr': previous_skill.mmr,
                'skill_group': previous_skill.skill_group,
            },
            'next_skill': {
                'mmr': next_skill.mmr,
                'skill_group': next_skill.skill_group,
            },
        }
        for (previous_skill, next_skill)
        in get_skill_changes_between_rounds(skill_db, round_range)
    ]
    time_window = [day.isoformat(),
                   (day + datetime.timedelta(days=1)).isoformat()]
    return {
        'time_window': time_window,
        'rounds_played': rounds_played,
        'most_played_maps': most_played_maps,
        'player_ratings': player_ratings,
        'season_skill_group_changes': skill_group_changes,
    }


def get_most_played_maps_between_rounds(
        skill_db, round_range: (int, int)) -> {str: int}:
    return dict(execute(skill_db, '''
    SELECT map_name
         , COUNT(*) AS round_count
    FROM rounds
    JOIN maps ON rounds.map_id = maps.map_id
    WHERE round_id BETWEEN ? AND ?
    GROUP BY map_name
    ORDER BY round_count DESC
    ''', round_range))


def make_player_rating(player, rating_details, rounds_played, mvps):
    return {
        'player_id': player.player_id,
        'steam_name': player.steam_name,
        'impact_rating': player.impact_rating,
        'previous_skill': {
            'mmr': player.mmr,
            'skill_group': player.skill_group,
        },
        'rating_details': rating_details,
        'rounds_played': rounds_played,
        'mvps': mvps,
    }


def get_player_ratings_between_rounds(skill_db, round_range: (int, int)) \
        -> (dict, dict):
    rating_details = execute(skill_db, '''
    WITH components AS (
            SELECT rc.player_id
                 , AVG(rc.kill_rating) AS average_kills
                 , AVG(rc.death_rating) AS average_deaths
                 , AVG(rc.damage_rating) AS average_damage
                 , AVG(rc.kas_rating) AS average_kas
                 , COUNT(*) AS rounds_played
                 , SUM(rc.mvp_rating) AS total_mvps
            FROM rating_components rc
            WHERE rc.round_id BETWEEN ? AND ?
            GROUP BY rc.player_id
        ), impact_ratings AS (
            SELECT c.player_id
                 , {} * c.average_kills
                 + {} * c.average_deaths
                 + {} * c.average_damage
                 + {} * c.average_kas
                 + {} AS rating
                 , c.*
            FROM components c
        ), starting_skills AS (
            SELECT ssh.player_id
                 , ssh.skill_mean
                 , ssh.skill_stdev
            FROM season_skill_history ssh
            JOIN ( SELECT ssh2.player_id
                        , MAX(ssh2.round_id) AS max_round_id
                   FROM season_skill_history ssh2
                   WHERE ssh2.round_id < ?
                   GROUP BY ssh2.player_id
               ) ms
               ON ms.player_id = ssh.player_id
               AND ssh.round_id = ms.max_round_id
        )
    SELECT players.player_id
         , players.steam_name
         , ir.rating
         , ir.average_kills
         , -ir.average_deaths AS average_deaths
         , ir.average_damage
         , ir.average_kas
         , ir.rounds_played
         , ir.total_mvps
         , s.skill_mean
         , s.skill_stdev
    FROM players
    JOIN impact_ratings ir
    ON   players.player_id = ir.player_id
    LEFT JOIN starting_skills s
    ON   players.player_id = s.player_id
    '''.format(*COEFFICIENTS), (round_range[0], round_range[1], round_range[0]))

    player_ratings = [
        make_player_rating(
                Player(player_id, steam_name,
                       skill_mean, skill_stdev, impact_rating), {
                    'average_kills': average_kills,
                    'average_deaths': average_deaths,
                    'average_damage': average_damage,
                    'total_kills': int(average_kills * rounds_played),
                    'total_deaths': int(average_deaths * rounds_played),
                    'total_damage': int(average_damage * rounds_played),
                    'kdr': average_kills / average_deaths,
                }, rounds_played, mvps)
        for player_id, steam_name, impact_rating,
            average_kills, average_deaths, average_damage, average_kas,
            rounds_played, mvps, skill_mean, skill_stdev
        in rating_details
    ]
    player_ratings.sort(key=operator.itemgetter('impact_rating'),
                        reverse=True)

    return player_ratings


def get_skill_changes_between_rounds(skill_db, round_range: (int, int)) \
        -> [(Player, Player)]:
    skill_change_rows = execute(skill_db, '''
    SELECT players.player_id
         , players.steam_name
         , earlier_ssh.skill_mean  AS earlier_skill_mean
         , earlier_ssh.skill_stdev AS earlier_skill_stdev
         , later_ssh.skill_mean    AS later_skill_mean
         , later_ssh.skill_stdev   AS later_skill_stdev
    FROM players
    JOIN season_skill_history earlier_ssh
    ON players.player_id = earlier_ssh.player_id
    AND earlier_ssh.round_id =
        ( SELECT MAX(ssh_before.round_id)
          FROM season_skill_history ssh_before
          WHERE ssh_before.round_id < ?
          AND ssh_before.player_id = players.player_id
        )
    JOIN rounds earlier_round
    ON earlier_ssh.round_id = earlier_round.round_id
    JOIN season_skill_history later_ssh
    ON players.player_id = later_ssh.player_id
    AND later_ssh.round_id =
        ( SELECT MAX(ssh_after.round_id)
          FROM season_skill_history ssh_after
          WHERE ssh_after.round_id BETWEEN ? AND ?
          AND ssh_after.player_id = players.player_id
        )
    JOIN rounds later_round
    ON later_ssh.round_id = later_round.round_id
    AND earlier_round.season_id = later_round.season_id
    ''', (round_range[0], round_range[0], round_range[1]))

    skill_changes = [
        (
            Player(player_id, steam_name, earlier_mean, earlier_stdev, 0.0),
            Player(player_id, steam_name, later_mean, later_stdev, 0.0),
        )
        for player_id, steam_name, earlier_mean, earlier_stdev,
            later_mean, later_stdev
        in skill_change_rows
    ]
    skill_changes.sort(key=lambda change: -change[1].mmr)

    return [
        (previous_skill, next_skill)
        for previous_skill, next_skill
        in skill_changes
        if previous_skill.skill_group != next_skill.skill_group
    ]


def get_round_range_for_day(skill_db, day: datetime.datetime) \
        -> ((int, int), int):
    next_day = day + datetime.timedelta(days=1)

    first_round, last_round, round_count = execute_one(skill_db, '''
    SELECT MIN(round_id)
         , MAX(round_id)
         , COUNT(*)
    FROM rounds
    WHERE created_at BETWEEN ? AND ?
    ''', (day, next_day))

    return (first_round, last_round), round_count
