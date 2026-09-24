"""Domain errors that servicers raise instead of calling context.abort().

context.abort() raises a bare Exception, which is indistinguishable from a bug
once it reaches an interceptor. Raising these instead lets ErrorInterceptor map
the failure to a status code, and lets servicer methods be unit tested without
a gRPC context.
"""
import grpc


class ServiceError(Exception):
  """An error with a gRPC status code the client should see."""

  status_code: grpc.StatusCode = grpc.StatusCode.UNKNOWN


class NotFound(ServiceError):
  status_code = grpc.StatusCode.NOT_FOUND


class InvalidArgument(ServiceError):
  status_code = grpc.StatusCode.INVALID_ARGUMENT
