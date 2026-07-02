import datetime
import operator
import itertools
from typing import List, Tuple, Dict, NamedTuple, Optional

from google.protobuf.field_mask_pb2 import FieldMask
from google.protobuf.timestamp_pb2 import Timestamp

from proto import common_pb2
from proto import highlights_service_pb2
from truescrub.accolades import get_accolades
from truescrub.db import execute_one, execute, COEFFICIENTS_DICT
from truescrub.models import Player, SKILL_STDEV, SKILL_MEAN


class PlayerRatingRow(NamedTuple):
  player_id: int
  steam_name: str
  impact_rating: float
  average_kills: float
  average_deaths: float
  average_damage: float
  average_kas: float
  average_assists: float
  rounds_played: int
  total_mvps: Optional[float]
  average_headshots: float
  starting_skill_mean: Optional[float]
  starting_skill_stdev: Optional[float]
  current_skill_mean: float
  current_skill_stdev: float


class SkillChangeRow(NamedTuple):
  player_id: int
  steam_name: str
  earlier_skill_mean: Optional[float]
  earlier_skill_stdev: Optional[float]
  later_skill_mean: float
  later_skill_stdev: float


def get_highlights(
    skill_db, day: datetime.datetime,
    read_mask: Optional[FieldMask] = None
) -> highlights_service_pb2.GetDailyHighlightsResponse:
  round_range, rounds_played = get_round_range_for_day(skill_db, day)

  if rounds_played == 0:
    raise StopIteration

  include_accolades = True
  if read_mask is not None and read_mask.paths:
    include_accolades = "players.accolades" in read_mask.paths or "players" in read_mask.paths

  player_ratings = get_player_ratings_between_rounds(skill_db, round_range)
  most_played_maps = get_most_played_maps_between_rounds(
    skill_db, round_range)

  if include_accolades:
    accolades_dict = get_accolades(player_ratings)
    for p in player_ratings:
      if p.player.player_id in accolades_dict:
        p.accolades.append(accolades_dict[p.player.player_id])

  start_ts = Timestamp()
  start_ts.FromDatetime(day)

  end_ts = Timestamp()
  end_ts.FromDatetime(day + datetime.timedelta(days=1))

  time_window = highlights_service_pb2.TimeWindow(
    start_inclusive=start_ts,
    end_exclusive=end_ts
  )

  result = highlights_service_pb2.GetDailyHighlightsResponse(
    time_windows=[time_window],
    rounds_played=rounds_played,
    players=player_ratings,
  )

  skill_group_changes = get_skill_changes_between_rounds(skill_db, round_range)
  result.season_skill_group_changes.extend(skill_group_changes)

  for k, v in most_played_maps.items():
    result.most_played_maps[k] = v

  return result


def get_most_played_maps_between_rounds(
    skill_db, round_range: Tuple[int, int]) -> Dict[str, int]:
  return dict(execute(
    skill_db,
    '''
    SELECT map_name
         , COUNT(*) AS round_count
    FROM rounds
    JOIN maps ON rounds.map_id = maps.map_id
    WHERE round_id BETWEEN ? AND ?
    GROUP BY map_name
    ORDER BY round_count DESC
    ''', round_range))


def get_player_ratings_between_rounds(
    skill_db, round_range: Tuple[int, int]
) -> List[highlights_service_pb2.DailyHighlight]:
  rating_details = execute(
    skill_db,
    '''
    WITH components AS (
            SELECT rc.player_id
                 , AVG(rc.kill_rating) AS average_kills
                 , AVG(rc.death_rating) AS average_deaths
                 , AVG(rc.damage_rating) AS average_damage
                 , AVG(rc.kas_rating) AS average_kas
                 , AVG(rc.assists_rating) AS average_assists
                 , COUNT(*) AS rounds_played
                 , SUM(rc.mvp_rating) AS total_mvps
                 , AVG(rs.headshots) AS average_headshots
            FROM rating_components rc
            JOIN round_stats rs ON rc.round_id = rs.round_id AND rc.player_id = rs.player_id
            WHERE rc.round_id BETWEEN :first_round AND :last_round
            GROUP BY rc.player_id
        ), impact_ratings AS (
            SELECT c.player_id
                 , :kill_coeff * c.average_kills
                 + :death_coeff * c.average_deaths
                 + :damage_coeff * c.average_damage
                 + :kas_coeff * c.average_kas
                 + :intercept AS rating
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
                   WHERE ssh2.round_id < :first_round
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
         , ir.average_assists
         , ir.rounds_played
         , ir.total_mvps
         , ir.average_headshots
         , s.skill_mean
         , s.skill_stdev
         , players.skill_mean
         , players.skill_stdev
    FROM players
    JOIN impact_ratings ir
    ON   players.player_id = ir.player_id
    LEFT JOIN starting_skills s
    ON   players.player_id = s.player_id
    ''', {
      **COEFFICIENTS_DICT,
      'first_round': round_range[0],
      'last_round': round_range[1]},
  )

  player_ratings = []
  for row in itertools.starmap(PlayerRatingRow, rating_details):
    current_player = Player(row.player_id, row.steam_name, row.current_skill_mean, row.current_skill_stdev,
                            row.impact_rating)
    starting_player = Player(row.player_id, row.steam_name,
                             row.starting_skill_mean,
                             row.starting_skill_stdev,
                             0.0)

    player_ratings.append(highlights_service_pb2.DailyHighlight(
      player=common_pb2.Player(
        player_id=row.player_id,
        steam_name=row.steam_name,
        skill=common_pb2.SkillInfo(
          mmr=current_player.mmr,
        ),
      ),
      impact_rating=row.impact_rating,
      starting_skill=common_pb2.SkillInfo(
        mmr=starting_player.mmr,
      ),
      rating_details=highlights_service_pb2.RatingDetails(
        average_kills=row.average_kills,
        average_deaths=row.average_deaths,
        average_damage=row.average_damage,
        average_assists=row.average_assists,
        total_kills=int(row.average_kills * row.rounds_played),
        total_deaths=int(row.average_deaths * row.rounds_played),
        total_damage=int(row.average_damage * row.rounds_played),
        total_assists=int(row.average_assists * row.rounds_played),
        kdr=(row.average_kills * row.rounds_played) /
            max(1.0, row.average_deaths * row.rounds_played),
        average_headshots=row.average_headshots,
        total_headshots=int(row.average_headshots * row.rounds_played),
      ),
      rounds_played=row.rounds_played,
      mvps=int(row.total_mvps or 0),
    ))

  player_ratings.sort(key=operator.attrgetter('impact_rating'), reverse=True)

  return player_ratings





def get_skill_changes_between_rounds(
    skill_db, round_range: Tuple[int, int]) \
    -> List[highlights_service_pb2.SkillGroupChange]:
  skill_change_rows = execute(
    skill_db,
    '''
    SELECT players.player_id
         , players.steam_name
         , earlier_ssh.skill_mean AS earlier_skill_mean
         , earlier_ssh.skill_stdev AS earlier_skill_stdev
         , later_ssh.skill_mean AS later_skill_mean
         , later_ssh.skill_stdev AS later_skill_stdev
    FROM players
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
    LEFT JOIN season_skill_history earlier_ssh
    ON players.player_id = earlier_ssh.player_id
    AND earlier_ssh.round_id =
        ( SELECT MAX(ssh_before.round_id)
          FROM season_skill_history ssh_before
          JOIN rounds rounds_before
          ON ssh_before.round_id = rounds_before.round_id
          WHERE ssh_before.round_id < ?
          AND ssh_before.player_id = players.player_id
          AND rounds_before.season_id = later_round.season_id
        )
    ''', (round_range[0], round_range[1], round_range[0]))

  skill_changes = [
    (
      Player(row.player_id, row.steam_name,
             SKILL_MEAN if row.earlier_skill_mean is None else row.earlier_skill_mean,
             SKILL_STDEV if row.earlier_skill_stdev is None else row.earlier_skill_stdev,
             0.0),
      Player(row.player_id, row.steam_name, row.later_skill_mean, row.later_skill_stdev, 0.0),
    )
    for row in itertools.starmap(SkillChangeRow, skill_change_rows)
  ]

  filtered_changes = [
    highlights_service_pb2.SkillGroupChange(
      player_id=previous_skill.player_id,
      steam_name=previous_skill.steam_name,
      previous_skill=common_pb2.SkillInfo(
        mmr=previous_skill.mmr,
      ),
      next_skill=common_pb2.SkillInfo(
        mmr=next_skill.mmr,
      ),
    )
    for previous_skill, next_skill in skill_changes
    if previous_skill.skill_group_index != next_skill.skill_group_index
  ]

  # Sort only the filtered results
  filtered_changes.sort(key=lambda change: -change.next_skill.mmr)

  return filtered_changes


def get_round_range_for_day(skill_db, day: datetime.datetime) \
    -> Tuple[Tuple[int, int], int]:
  next_day = day + datetime.timedelta(days=1)

  first_round, last_round, round_count = execute_one(
    skill_db,
    '''
    SELECT MIN(round_id)
         , MAX(round_id)
         , COUNT(*)
    FROM rounds
    WHERE created_at BETWEEN ? AND ?
    ''',
    (day, next_day))

  return (first_round, last_round), round_count
