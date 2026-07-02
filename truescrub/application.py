import abc
import argparse
import concurrent.futures
import functools
import json
import logging
import os
import threading
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Callable, Tuple

from grpc_health.v1 import health
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc
from grpc_reflection.v1alpha import reflection

import grpc
from proto import highlights_service_pb2_grpc
from proto import leaderboard_service_pb2_grpc
from proto import matchmaking_service_pb2_grpc
from proto import profile_service_pb2_grpc
from proto import season_service_pb2_grpc
from truescrub import db
from truescrub.envconfig import LOG_LEVEL, SHARED_KEY
from truescrub.interceptors import TimerInterceptor, DatabaseInterceptor
from truescrub.queue_consumer import QueueConsumer
from truescrub.rpc import (
  SeasonServiceServicer,
  MatchmakingServiceServicer,
  HighlightsServiceServicer,
  LeaderboardServiceServicer,
  ProfileServiceServicer
)
from truescrub.statewriter.state_writer import GameStateWriter, \
  RiegeliGameStateWriter
from truescrub.updater import Updater
from truescrub.updater.recalculate import load_seasons
from truescrub.updater.state_loader import (
  DatabaseStateLoader, RiegeliStateLoader, StateLoader)

logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(name)s\t%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=LOG_LEVEL)
logger = logging.getLogger(__name__)

GAME_STATE_BACKENDS: Dict[str, Tuple[
  Callable[[], StateLoader], Callable[[QueueConsumer], QueueConsumer]
]] = {
  'sqlite': (DatabaseStateLoader, GameStateWriter),
  'riegeli': (RiegeliStateLoader.from_env, RiegeliGameStateWriter.from_env),
}

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-a', '--addr', metavar='HOST', default='0.0.0.0',
                        help='Bind to this address.')
arg_parser.add_argument('-p', '--port', metavar='PORT', type=int,
                        default=9000, help='Listen on this TCP port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-b', '--game-state-backend',
                        choices=GAME_STATE_BACKENDS, default='sqlite',
                        help='Store game states using this provider.')
arg_parser.add_argument('-P', '--grpc-port', metavar='PORT', type=int,
                        default=9900,
                        help='Listen for gRPC connections on this TCP port.')


class Service(metaclass=abc.ABCMeta):
  @abc.abstractmethod
  def stop(self):
    pass

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    logger.info('stopping %s', self)
    return self.stop()

  def __str__(self):
    return type(self).__name__


class QueueConsumerService(Service):
  def __init__(self, consumer):
    self.consumer = consumer

  def __call__(self):
    logger.info('running %s', self)
    self.consumer.run()

  def stop(self):
    self.consumer.stop()

  def __str__(self):
    return type(self.consumer).__name__


class GameStateHandler(BaseHTTPRequestHandler):
  def __init__(self, state_writer, shared_key, *args, **kwargs):
    self.state_writer = state_writer
    self.shared_key = shared_key
    super().__init__(*args, **kwargs)

  def do_POST(self):
    if self.path != '/api/game_state':
      self.send_response(404)
      self.end_headers()
      return

    content_length = int(self.headers.get('Content-Length', 0))
    post_data = self.rfile.read(content_length)

    try:
      state_json = json.loads(post_data)
    except ValueError:
      self.send_response(400)
      self.end_headers()
      self.wfile.write(b"Invalid JSON\n")
      return

    if state_json.get('auth', {}).get('token') != self.shared_key:
      self.send_response(403)
      self.end_headers()
      self.wfile.write(b"Invalid auth token\n")
      return

    del state_json['auth']
    self.state_writer.send_message(game_state=json.dumps(state_json))

    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"<h1>OK</h1>\n")

  def log_message(self, format, *args):
    logger.debug(f"{self.address_string()} - {format % args}")


class GsiHttpService(Service):
  def __init__(self, state_writer, shared_key, host, port):
    handler_factory = functools.partial(GameStateHandler, state_writer,
                                        shared_key)
    self.server = ThreadingHTTPServer((host, port), handler_factory)
    logger.info('listening on %s:%s', host, port)

  def __call__(self):
    logger.info('running %s', self)
    self.server.serve_forever()

  def stop(self):
    if self.server is not None:
      logger.debug('closing server')
      self.server.shutdown()
      self.server.server_close()


def create_grpc_server(host, port):
  server = grpc.server(
    concurrent.futures.ThreadPoolExecutor(max_workers=10),
    interceptors=[TimerInterceptor(), DatabaseInterceptor()]
  )
  health_servicer = health.HealthServicer()
  health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
  health_servicer.set('', health_pb2.HealthCheckResponse.SERVING)
  reflection.enable_server_reflection(
    (health.SERVICE_NAME, reflection.SERVICE_NAME), server)
  server.add_insecure_port(f'{host}:{port}')
  return server


class GrpcService(Service):
  def __init__(self, host, port):
    self.server = create_grpc_server(host, port)
    logger.info('gRPC listening on %s:%s', host, port)

  def __call__(self):
    logger.info('running %s', self)
    self.server.start()
    self.server.wait_for_termination()

  def stop(self):
    if self.server is not None:
      logger.debug('closing gRPC server')
      self.server.stop(grace=5.0).wait()


def wait_on_futures(futures: Dict[Future, Service]):
  for future in futures:
    future.cancel()
  logger.debug('waiting on remaining futures')
  done, not_done = concurrent.futures.wait(futures, timeout=4.0)
  if len(not_done) == 0:
    logger.info('canceling watchdog timer')
    return True
  logger.warning('some futures did not complete: %s',
                 [str(futures[future]) for future in not_done])
  return False


class Watchdog:
  def __init__(self, futures: Dict[Future, Service], interval: float):
    self.futures = futures
    self.timer = threading.Timer(interval, self.shutdown)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    if exc_type is None:
      return

    logger.info('triggering watchdog timer due to %s', exc_type.__name__)
    self.timer.start()
    if wait_on_futures(self.futures):
      self.timer.cancel()

  @staticmethod
  def shutdown():
    logger.error('forcibly exiting process')
    os._exit(-1)


def main(args: List[str]):
  args = arg_parser.parse_args(args)
  state_loader_provider, state_writer_provider = \
    GAME_STATE_BACKENDS[args.game_state_backend]

  executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
  futures = {}
  updater = Updater(state_loader_provider)
  state_writer = state_writer_provider(updater)
  db.initialize_dbs()

  with db.get_skill_db() as skill_db:
    load_seasons(skill_db)
    skill_db.commit()

  if args.recalculate:
    updater.send_message(command='recalculate')
    updater.stop()
    updater.run()
    return

  with Watchdog(futures, interval=8.0), \
      QueueConsumerService(updater) as updater_service, \
      GsiHttpService(state_writer, SHARED_KEY, host=args.addr, port=args.port) \
          as gsi_service, \
      QueueConsumerService(state_writer) as state_writer_service, \
      GrpcService(host=args.addr, port=args.grpc_port) as grpc_service:

    highlights_service_pb2_grpc.add_HighlightsServiceServicer_to_server(
      HighlightsServiceServicer(), grpc_service.server)
    matchmaking_service_pb2_grpc.add_MatchmakingServiceServicer_to_server(
      MatchmakingServiceServicer(), grpc_service.server)
    season_service_pb2_grpc.add_SeasonServiceServicer_to_server(
      SeasonServiceServicer(), grpc_service.server)
    leaderboard_service_pb2_grpc.add_LeaderboardServiceServicer_to_server(
      LeaderboardServiceServicer(), grpc_service.server)
    profile_service_pb2_grpc.add_ProfileServiceServicer_to_server(
      ProfileServiceServicer(), grpc_service.server)

    futures[executor.submit(updater_service)] = updater_service
    futures[executor.submit(state_writer_service)] = state_writer_service
    futures[executor.submit(gsi_service)] = gsi_service
    futures[executor.submit(grpc_service)] = grpc_service

    for future in concurrent.futures.as_completed(futures):
      if future.exception() is not None:
        logger.fatal('future %s failed with "%s"', futures[future],
                     future.exception())
      else:
        logger.info('future %s has completed', futures[future])
      future.result()
  logger.info('exiting')
