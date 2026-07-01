import datetime
import itertools
import operator
from typing import Tuple, List, Iterable

import grpc
from proto import common_pb2
from proto import highlights_service_pb2
from proto import highlights_service_pb2_grpc
from proto import matchmaking_service_pb2
from proto import matchmaking_service_pb2_grpc
from proto import season_service_pb2
from proto import season_service_pb2_grpc
from truescrub import db, highlights, models
from truescrub.api import parse_timezone
from truescrub.interceptors import grpc_db_conn
from truescrub.matchmaking import compute_matches, MAX_PLAYERS_PER_TEAM

MAX_MATCHES = 50


class SeasonServiceServicer(season_service_pb2_grpc.SeasonServiceServicer):
  def GetAvailableSeasons(self, request, context):
    conn = grpc_db_conn.get()
    seasons = db.get_season_range(conn)
    return season_service_pb2.GetAvailableSeasonsResponse(
      available_seasons=seasons
    )


def _get_timezone(request, context) -> datetime.timezone:
  timezone = request.timezone or "-05:00"
  try:
    return parse_timezone(timezone)
  except ValueError:
    return context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         f"Invalid timezone {request.timezone}")


def _get_day(request, context) -> datetime.datetime:
  try:
    return datetime.datetime(
      request.date.year, request.date.month, request.date.day,
      tzinfo=_get_timezone(request, context)
    )
  except ValueError:
    return context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid date")


class HighlightsServiceServicer(
  highlights_service_pb2_grpc.HighlightsServiceServicer):

  def ListMatchDays(self, request, context):
    conn = grpc_db_conn.get()
    return highlights_service_pb2.ListMatchDaysResponse(
      match_days=[
        common_pb2.Date(
          year=day.year, month=day.month, day=day.day)
        for day in db.get_match_days(conn, _get_timezone(request, context))
      ])

  def GetDailyHighlights(self, request, context):
    conn = grpc_db_conn.get()
    try:
      day = _get_day(request, context)
      return highlights.get_highlights(conn, day, request.read_mask)
    except StopIteration:
      context.abort(grpc.StatusCode.NOT_FOUND, "No rounds on this date")


def compute_matchmaking(conn, season_id, selected_players) \
    -> Tuple[List[models.Player], Iterable[models.Match]]:
  max_players = MAX_PLAYERS_PER_TEAM * 2
  if len(selected_players) > max_players:
    raise ValueError('Cannot compute matches for more than '
                     '{} players'.format(max_players))
  players = db.get_all_players(conn) \
    if season_id is None \
    else db.get_season_players(conn, season_id)
  players.sort(key=operator.attrgetter('mmr'), reverse=True)

  if len(selected_players) > 0:
    matches = itertools.islice(compute_matches([
      player for player in players
      if player.player_id in selected_players
    ]), MAX_MATCHES)
  else:
    matches = []

  return players, matches


class MatchmakingServiceServicer(
  matchmaking_service_pb2_grpc.MatchmakingServiceServicer):

  def ComputeMatchmaking(self, request, context):
    season_id = request.season_id \
      if request.HasField('season_id') and request.season_id > 0 \
      else None

    conn = grpc_db_conn.get()
    if request.WhichOneof('selection') == 'round_selection':
      selected_players = db.get_players_in_last_round(conn)
      if season_id is None:
        seasons = db.get_season_range(conn)
        if seasons:
          season_id = seasons[-1]
    elif request.WhichOneof('selection') == 'player_selection':
      selected_players = set(request.player_selection.player_ids)
    else:
      selected_players = set()

    try:
      players, matches = compute_matchmaking(
        conn, season_id, selected_players)
    except ValueError as e:
      return context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

    available_players = [p.to_message() for p in players]
    proposed_matches = [
      matchmaking_service_pb2.Match(
        team1=[p.to_message() for p in match.team1],
        team2=[p.to_message() for p in match.team2],
        quality=match.quality,
        team1_win_probability=match.p_win,
        team2_win_probability=1.0 - match.p_win,
      )
      for match in matches
    ]

    return matchmaking_service_pb2.ComputeMatchmakingResponse(
      available_players=available_players,
      proposed_matches=proposed_matches,
    )
