"""Server interceptors for the application's gRPC services.

Invariant: ErrorInterceptor is the only interceptor that may call
context.abort(). abort() raises a bare Exception, so a second interceptor that
catches Exception and aborts again silently replaces the first status with its
own. Interceptors that need to react to a failure must re-raise, as
DatabaseInterceptor does. The status-code cases in
tests/test_integration_real_data.py fail if this is ever violated.
"""
import contextvars
import logging
import time

import grpc
from truescrub import db
from truescrub.errors import ServiceError

grpc_db_conn = contextvars.ContextVar('grpc_db_conn')
logger = logging.getLogger(__name__)

# gRPC's own health and reflection services. They are not ours to instrument:
# they have no use for an application database connection, and reflection is
# bidirectionally streaming.
_PASSTHROUGH_PREFIXES = ('/grpc.health.', '/grpc.reflection.')


def _wrap_unary_unary(handler, method, wrap_behavior):
  """Rebuild an application handler with its behavior wrapped.

  Infrastructure services are returned untouched. Every application RPC is
  unary-unary today; a streaming one fails here rather than silently skipping
  error mapping and transaction handling, which is what a quiet passthrough
  would do.
  """
  if handler is None or method.startswith(_PASSTHROUGH_PREFIXES):
    return handler

  if handler.request_streaming or handler.response_streaming:
    raise NotImplementedError(
      f'{method}: the interceptor stack only supports unary-unary RPCs. '
      'Add streaming support to truescrub.interceptors before serving one.')

  return grpc.unary_unary_rpc_method_handler(
    wrap_behavior(handler.unary_unary),
    request_deserializer=handler.request_deserializer,
    response_serializer=handler.response_serializer,
  )


class TimerInterceptor(grpc.ServerInterceptor):
  """Measures execution time and injects x-processing-time trailing metadata."""

  def intercept_service(self, continuation, handler_call_details):
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

    return _wrap_unary_unary(
      continuation(handler_call_details),
      handler_call_details.method,
      wrap_behavior)


class ErrorInterceptor(grpc.ServerInterceptor):
  """Maps exceptions to gRPC statuses.

  A ServiceError carries the status the client should see. Anything else is a
  bug: it is logged with a traceback and reported as INTERNAL, without leaking
  the message. Per the module invariant, this is the only interceptor that
  calls context.abort().
  """

  def intercept_service(self, continuation, handler_call_details):
    def wrap_behavior(behavior):
      def new_behavior(request, context):
        try:
          return behavior(request, context)
        except ServiceError as e:
          context.abort(e.status_code, str(e))
        except Exception:
          logger.exception('RPC %s failed', handler_call_details.method)
          context.abort(
            grpc.StatusCode.INTERNAL,
            'An internal error occurred during processing.',
          )

      return new_behavior

    return _wrap_unary_unary(
      continuation(handler_call_details),
      handler_call_details.method,
      wrap_behavior)


class DatabaseInterceptor(grpc.ServerInterceptor):
  """Opens a database connection and commits or rolls it back per RPC.

  Never converts a failure into a status: it re-raises so ErrorInterceptor,
  which sits outside it, decides the code.
  """

  def intercept_service(self, continuation, handler_call_details):
    def wrap_behavior(behavior):
      def new_behavior(request, context):
        conn = db.get_skill_db()
        token = grpc_db_conn.set(conn)
        try:
          response = behavior(request, context)
          conn.commit()
          return response
        except BaseException:
          conn.rollback()
          raise
        finally:
          conn.close()
          grpc_db_conn.reset(token)

      return new_behavior

    return _wrap_unary_unary(
      continuation(handler_call_details),
      handler_call_details.method,
      wrap_behavior)
