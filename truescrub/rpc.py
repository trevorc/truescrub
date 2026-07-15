import datetime
import itertools
import operator
import re
from typing import Tuple, List, Iterable, Set

import grpc
from proto import common_pb2
from proto import highlights_service_pb2
from proto import highlights_service_pb2_grpc
from proto import leaderboard_service_pb2
from proto import leaderboard_service_pb2_grpc
from proto import matchmaking_service_pb2
from proto import matchmaking_service_pb2_grpc
from proto import profile_service_pb2
from proto import profile_service_pb2_grpc
from proto import season_service_pb2
from proto import season_service_pb2_grpc
from truescrub import achievements, db, highlights, models
from truescrub.interceptors import grpc_db_conn
from truescrub.matchmaking import compute_matches, estimated_skill_range, \
  MAX_PLAYERS_PER_TEAM

MAX_MATCHES = 50
TIMEZONE_PATTERN = re.compile(r'([+-])(\d\d):(\d\d)$')


def parse_timezone(tz: str) -> datetime.timezone:
  match = TIMEZONE_PATTERN.match(tz)
  if match is None:
    raise ValueError(f"Invalid timezone {tz}")

  plusminus, hours, minutes = match.groups()
  offset_signum = 1 if plusminus == '+' else -1
  offset = datetime.timedelta(
    hours=offset_signum * int(hours),
    minutes=offset_signum * int(minutes)
  )
  return datetime.timezone(offset=offset)


class SeasonServiceServicer(season_service_pb2_grpc.SeasonServiceServicer):
  def GetAvailableSeasons(self, request, context: grpc.ServicerContext):
    conn = grpc_db_conn.get()
    seasons = db.get_season_range(conn)
    return season_service_pb2.GetAvailableSeasonsResponse(
      available_seasons=seasons
    )


def _get_timezone(request, context: grpc.ServicerContext) -> datetime.timezone:
  timezone = request.timezone or "-05:00"
  try:
    return parse_timezone(timezone)
  except ValueError:
    return context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         f"Invalid timezone {request.timezone}")


def _get_day(request, context: grpc.ServicerContext) -> datetime.datetime:
  try:
    return datetime.datetime(
      request.date.year, request.date.month, request.date.day,
      tzinfo=_get_timezone(request, context)
    )
  except ValueError:
    return context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid date")


def _make_date(year: int, month: int, day: int) -> common_pb2.Date:
  return common_pb2.Date(year=year, month=month, day=day)


def _date_to_pb2(dt: datetime.date) -> common_pb2.Date:
  return common_pb2.Date(year=dt.year, month=dt.month, day=dt.day)


class HighlightsServiceServicer(
  highlights_service_pb2_grpc.HighlightsServiceServicer):

  def ListMatchDays(self, request, context: grpc.ServicerContext):
    return highlights_service_pb2.ListMatchDaysResponse(
      match_days=[
        _date_to_pb2(day) for day in db.get_match_days(
          grpc_db_conn.get(), _get_timezone(request, context))
      ])

  def GetDailyHighlights(self, request, context: grpc.ServicerContext):
    try:
      return highlights.get_highlights(
        grpc_db_conn.get(), _get_day(request, context), request.read_mask)
    except StopIteration:
      context.abort(grpc.StatusCode.NOT_FOUND, "No rounds on this date")


def compute_matchmaking(conn, season_id, selected_players) \
    -> Tuple[List[models.Player], Iterable[models.Match]]:
  max_players = MAX_PLAYERS_PER_TEAM * 2
  if len(selected_players) > max_players:
    raise ValueError(
      f'Cannot compute matches for more than {max_players} players')
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

  def ComputeMatchmaking(self, request, context: grpc.ServicerContext):
    season_id = request.season_id \
      if request.HasField('season_id') and request.season_id > 0 \
      else None

    conn = grpc_db_conn.get()
    selected_players: Set[int] = set()

    match request.WhichOneof('selection'):
      case 'round_selection':
        selected_players = db.get_players_in_last_round(conn)
        if season_id is None:
          seasons = db.get_season_range(conn)
          if seasons:
            season_id = seasons[-1]
      case 'player_selection':
        selected_players = set(request.player_selection.player_ids)

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


class LeaderboardServiceServicer(
  leaderboard_service_pb2_grpc.LeaderboardServiceServicer):

  def GetLeaderboard(self, request, context: grpc.ServicerContext):
    season_id = request.season_id \
      if request.HasField('season_id') and request.season_id > 0 \
      else None

    conn = grpc_db_conn.get()
    players = db.get_all_players(conn) \
      if season_id is None \
      else db.get_season_players(conn, season_id)
    players.sort(key=operator.attrgetter('mmr'), reverse=True)

    return leaderboard_service_pb2.GetLeaderboardResponse(
      leaderboard=[p.to_message() for p in players]
    )


class ProfileServiceServicer(profile_service_pb2_grpc.ProfileServiceServicer):

  def GetProfile(self, request, context: grpc.ServicerContext):
    conn = grpc_db_conn.get()

    try:
      player, overall_record = db.get_player_profile(conn, request.player_id)
    except StopIteration:
      return context.abort(grpc.StatusCode.NOT_FOUND, "No such player")

    skills_by_season = db.get_player_skills_by_season(conn, request.player_id)
    season_skills = {}
    for season_id, season_player in skills_by_season.items():
      lower_bound, upper_bound = estimated_skill_range(season_player.skill)
      season_skills[season_id] = profile_service_pb2.SeasonSkill(
        skill=common_pb2.SkillInfo(
          mmr=season_player.mmr,
          mu=season_player.skill.mu,
          sigma=season_player.skill.sigma,
        ),
        lower_bound=lower_bound,
        upper_bound=upper_bound,
      )

    overall_components = db.get_player_round_stat_averages(
      conn, request.player_id)
    overall_rating = profile_service_pb2.RatingComponents(
      mvp_rating=overall_components['average_mvps'],
      kill_rating=overall_components['average_kills'],
      death_rating=overall_components['average_deaths'],
      damage_rating=overall_components['average_damage'],
      kas_rating=overall_components['average_kas'],
      impact_rating=player.impact_rating,
    )

    season_ratings = {}
    for season_id, components in db.get_player_round_stat_averages_by_season(
        conn, request.player_id).items():
      season_ratings[season_id] = profile_service_pb2.RatingComponents(
        mvp_rating=components['average_mvps'],
        kill_rating=components['average_kills'],
        death_rating=components['average_deaths'],
        damage_rating=components['average_damage'],
        kas_rating=components['average_kas'],
        impact_rating=skills_by_season[season_id].impact_rating,
      )

    player_achievements = achievements.get_achievements(conn, request.player_id)
    achievement_progress = [
      profile_service_pb2.AchievementProgress(
        achievement_id=a['id'],
        current_value=a['current']
      )
      for a in player_achievements
    ]

    return profile_service_pb2.GetProfileResponse(
      player=player.to_message(),
      rounds_won=overall_record['rounds_won'],
      rounds_lost=overall_record['rounds_lost'],
      season_skills=season_skills,
      overall_rating=overall_rating,
      season_ratings=season_ratings,
      achievements=achievement_progress,
    )

  def GetSkillHistory(self, request, context: grpc.ServicerContext):
    conn = grpc_db_conn.get()
    timezone = _get_timezone(request, context)
    season_id = request.season_id if request.HasField(
      'season_id') and request.season_id > 0 else None

    if season_id is None:
      skill_history = db.get_overall_skill_history(
        conn, request.player_id, timezone)
      rating_history = db.get_impact_ratings_by_day(
        conn, request.player_id, timezone)
    else:
      skill_history = db.get_season_skill_history(
        conn, season_id, request.player_id, timezone)
      rating_history = db.get_impact_ratings_by_day(conn, request.player_id,
                                                    timezone, season_id)

    history_points = []
    for date_str, player_history in skill_history.items():
      year, month, day = map(int, date_str.split('-'))
      history_points.append(profile_service_pb2.SkillHistoryPoint(
        date=_make_date(year, month, day),
        skill=common_pb2.SkillInfo(
          mmr=player_history.mmr,
          mu=player_history.skill.mu,
          sigma=player_history.skill.sigma,
        ),
        impact_rating=rating_history.get(date_str)
      ))

    return profile_service_pb2.GetSkillHistoryResponse(history=history_points)

  def GetPlayerRounds(self, request, context: grpc.ServicerContext):
    conn = grpc_db_conn.get()
    rounds = db.get_player_rounds(conn, request.player_id)
    return profile_service_pb2.GetPlayerRoundsResponse(rounds=[
      profile_service_pb2.RoundRecord(
        created_at=_date_to_pb2(
          datetime.datetime.fromisoformat(rnd['created_at']).date()),
        winning_team_names=rnd['winning_team'],
        losing_team_names=rnd['losing_team'])
      for rnd in rounds
    ])

  def GetPlayerTeamRecords(self, request, context: grpc.ServicerContext):
    records = db.get_player_team_records(grpc_db_conn.get(), request.player_id)

    team_records = [
      profile_service_pb2.TeamRecord(
        team_members=rec['team_members'],
        rounds_won=rec['rounds_won'],
        rounds_lost=rec['rounds_lost']
      )
      for rec in records
    ]

    team_records.sort(
      key=lambda r: r.rounds_won + r.rounds_lost,
      reverse=True)

    return profile_service_pb2.GetPlayerTeamRecordsResponse(
      team_records=team_records)
