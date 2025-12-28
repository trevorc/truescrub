import abc
import argparse
import atexit
import concurrent.futures
import importlib.resources
import logging
import os
import threading
from concurrent.futures import Future
from contextlib import ExitStack
from typing import Dict, List

import waitress.server
from werkzeug.middleware.shared_data import SharedDataMiddleware

import truescrub
from truescrub import db
from truescrub.api import app
from truescrub.envconfig import LOG_LEVEL
from truescrub.statewriter import GameStateWriter
from truescrub.updater import Updater
from truescrub.updater.recalculate import load_seasons

logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(name)s\t%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=LOG_LEVEL)
logger = logging.getLogger(__name__)

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-a', '--addr', metavar='HOST', default='0.0.0.0',
                        help='Bind to this address.')
arg_parser.add_argument('-p', '--port', metavar='PORT', type=int,
                        default=9000, help='Listen on this TCP port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-s', '--serve-htdocs', action='store_true',
                        help='Serve static files.')

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


class StateWriterService(Service):
  def __init__(self, state_writer):
    self.state_writer = state_writer

  def __call__(self):
    logger.info('running %s', self)
    self.state_writer.run()

  def stop(self):
    self.state_writer.stop()


class UpdaterService(Service):
  def __init__(self, updater):
    self.updater = updater

  def __call__(self):
    logger.info('running %s', self)
    self.updater.run()

  def stop(self):
    self.updater.stop()


class WaitressService(Service):
  def __init__(self, app, host, port):
    self.server = waitress.server.create_server(
      app, host=host, port=port, _start=False)
    logger.info('listening on %s:%s', host, port)

  def __call__(self):
    logger.info('running %s', self)
    self.server.accept_connections()
    self.server.run()

  def stop(self):
    if self.server is not None:
      logger.debug('closing server')
      self.server.close()


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

  executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
  futures = {}
  updater = Updater()
  state_writer = GameStateWriter(updater)
  db.initialize_dbs()

  with db.get_skill_db() as skill_db:
    load_seasons(skill_db)
    skill_db.commit()

  if args.recalculate:
    updater.send_message(command='recalculate')
    updater.stop()
    updater.run()
    return
  if args.serve_htdocs:
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
      '/htdocs': (truescrub.__name__, 'htdocs'),
    }, cache_timeout=3600 * 24 * 14)

  with Watchdog(futures, interval=8.0), \
      UpdaterService(updater) as updater_service, \
      WaitressService(app, host=args.addr, port=args.port) \
          as waitress_service, \
      StateWriterService(state_writer) as state_writer_service:

    app.state_writer = state_writer
    futures[executor.submit(updater_service)] = updater_service
    futures[executor.submit(state_writer_service)] = state_writer_service
    futures[executor.submit(waitress_service)] = waitress_service

    for future in concurrent.futures.as_completed(futures):
      if future.exception() is not None:
        logger.fatal('future %s failed with "%s"', futures[future],
                     future.exception())
      else:
        logger.info('future %s has completed', futures[future])
      future.result()
  logger.info('exiting')
