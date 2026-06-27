import datetime
import grpc
from truescrub import db, highlights
from truescrub.api import parse_timezone
from proto import highlights_service_pb2
from proto import highlights_service_pb2_grpc


def _get_timezone(request, context) -> datetime.timezone:
  timezone = request.timezone or "-05:00"
  try:
    return parse_timezone(timezone)
  except ValueError:
    return context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                         f"Invalid timezone {timezone}")


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
    with db.get_skill_db() as conn:
      return highlights_service_pb2.ListMatchDaysResponse(
        match_days=[
          highlights_service_pb2.Date(
            year=day.year, month=day.month, day=day.day)
          for day in db.get_match_days(conn, _get_timezone(request, context))
        ])

  def GetDailyHighlights(self, request, context):
    with db.get_skill_db() as conn:
      try:
        day = _get_day(request, context)
        return highlights.get_highlights(conn, day, request.include_accolades)
      except StopIteration:
        context.abort(grpc.StatusCode.NOT_FOUND, "No rounds on this date")
