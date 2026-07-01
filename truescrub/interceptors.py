import contextvars
import logging
import time

import grpc
from truescrub import db

grpc_db_conn = contextvars.ContextVar('grpc_db_conn')
logger = logging.getLogger(__name__)


class TimerInterceptor(grpc.ServerInterceptor):
  """Measures execution time and injects x-processing-time trailing metadata."""

  def intercept_service(self, continuation, handler_call_details):
    handler = continuation(handler_call_details)
    if handler is None or handler.request_streaming or handler.response_streaming:
      return handler

    def wrap_behavior(behavior):
      def new_behavior(request, context):
        start = time.perf_counter()
        try:
          return behavior(request, context)
        finally:
          elapsed_ms = (time.perf_counter() - start) * 1000
          context.set_trailing_metadata((
            ('x-processing-time', f'{elapsed_ms:.2f}ms'),
          ))

      return new_behavior

    return grpc.unary_unary_rpc_method_handler(
      wrap_behavior(handler.unary_unary),
      request_deserializer=handler.request_deserializer,
      response_serializer=handler.response_serializer
    )


class DatabaseInterceptor(grpc.ServerInterceptor):
  """Automatically opens, commits/rollbacks, and closes a database connection."""

  def intercept_service(self, continuation, handler_call_details):
    handler = continuation(handler_call_details)
    if handler is None or handler.request_streaming or handler.response_streaming:
      return handler

    def wrap_behavior(behavior):
      def new_behavior(request, context):
        conn = db.get_skill_db()
        token = grpc_db_conn.set(conn)
        try:
          response = behavior(request, context)
          conn.commit()
          return response
        except Exception as e:
          conn.rollback()
          logger.exception("RPC failed, rolled back database transaction.")
          context.abort(
            grpc.StatusCode.INTERNAL,
            "An internal error occurred during processing."
          )
        finally:
          conn.close()
          grpc_db_conn.reset(token)

      return new_behavior

    return grpc.unary_unary_rpc_method_handler(
      wrap_behavior(handler.unary_unary),
      request_deserializer=handler.request_deserializer,
      response_serializer=handler.response_serializer
    )
