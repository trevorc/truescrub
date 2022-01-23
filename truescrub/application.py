import os
import abc
import argparse
import logging
import threading
import concurrent.futures

from werkzeug.middleware.shared_data import SharedDataMiddleware
import waitress.server

import truescrub
from truescrub import db
from truescrub.api import app
from truescrub.queue_consumer import QueueConsumer
from truescrub.updater import Updater


LOG_LEVEL = os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG')
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
  def run(self):
    pass

  @abc.abstractmethod
  def stop(self):
    pass

  def __call__(self):
    logger.info('running %s', self)
    self.run()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    logger.info('stopping %s', self)
    return self.stop()

  def __str__(self):
    return type(self).__name__


class GameStateWriter(QueueConsumer):
  def __init__(self, updater):
    super().__init__()
    self.updater = updater

  def process_messages(self, messages):
    max_game_state = 0
    with db.get_game_db() as game_db:
      logger.debug('saving %d game states', len(messages))
      for message in messages:
        game_state_id = db.insert_game_state(game_db, message['game_state'])
        logger.debug('saved game_state with id %d', game_state_id)
        max_game_state = max(game_state_id, max_game_state)
      game_db.commit()
      self.updater.send_message(command='process',
                                game_state_id=max_game_state)


class StateWriterService(Service):
  def __init__(self, state_writer):
    super().__init__()
    self.state_writer = state_writer

  def run(self):
    self.state_writer.run()

  def stop(self):
    self.state_writer.stop()


class UpdaterService(Service):
  def __init__(self, updater):
    super().__init__()
    self.updater = updater

  def run(self):
    self.updater.run()

  def stop(self):
    self.updater.stop()


class WaitressService(Service):
  def __init__(self, app, host, port):
    self.app = app
    self.host = host
    self.port = port
    self.server = None

  def run(self):
    self.server = waitress.server.create_server(
        self.app, host=self.host, port=self.port)
    self.server.run()

  def stop(self):
    if self.server is not None:
      logger.debug('closing server')
      self.server.close()


class Watchdog:
  def __init__(self, interval: float):
    self.timer = threading.Timer(interval, self.shutdown)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    if exc_type is not None:
      logger.info('triggering watchdog timer due to %s', exc_type.__name__)
      self.timer.start()

  def cancel(self):
    logger.info('canceling watchdog timer')
    self.timer.cancel()

  @staticmethod
  def shutdown():
    logger.error('forcibly exiting process')
    os._exit(-1)


def main():
  args = arg_parser.parse_args()
  executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
  futures = {}
  updater = Updater()
  state_writer = GameStateWriter(updater)
  db.initialize_dbs()

  if args.recalculate:
    updater.send_message(command='recalculate')
    updater.stop()
    updater.run()
    return
  if args.serve_htdocs:
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
      '/htdocs': (truescrub.__name__, 'htdocs'),
    }, cache_timeout=3600 * 24 * 14)

  try:
    with UpdaterService(updater) as updater_service, \
        WaitressService(app, host=args.addr, port=args.port) \
            as waitress_service, \
        StateWriterService(state_writer) as state_writer_service, \
        Watchdog(interval=8.0) as watchdog:

      logger.info('listening on %s:%s', args.addr, args.port)
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
  finally:
    for future in futures:
      future.cancel()
    logger.debug('waiting on remaining futures')
    done, not_done = concurrent.futures.wait(futures, timeout=4.0)
    if len(not_done) == 0:
      watchdog.cancel()
    else:
      logger.warning('some futures did not complete: %s',
                     [str(futures[future]) for future in not_done])
  logger.info('exiting')
