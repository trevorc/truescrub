import datetime
import json
import logging

from google.protobuf.timestamp_pb2 import Timestamp
from truescrub.proto.game_state_pb2 import GameStateEntry

from truescrub import db
from truescrub.queue_consumer import QueueConsumer
from truescrub.statewriter.game_state_log import GameStateLog, \
  NoSuchRecordException
from truescrub.statewriter.state_serialization import parse_game_state

logger = logging.getLogger(__name__)


class GameStateWriter(QueueConsumer):
  def __init__(self, updater: QueueConsumer) -> None:
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


class RiegeliGameStateWriter(QueueConsumer):
  def __init__(self, log: GameStateLog, updater: QueueConsumer):
    super().__init__()
    self.log = log
    self.updater = updater
    self.max_id = self._get_last_entry_id()

  def _get_last_entry_id(self):
    with self.log.reader(timeout=0) as reader:
      try:
        return reader.fetch_last().game_state_id
      except NoSuchRecordException:
        return 0

  def process_messages(self, messages):
    logger.debug('saving %d game states', len(messages))

    with self.log.writer(timeout=0) as writer:
      created_at = datetime.datetime.utcnow()
      for message in messages:
        game_state_json = json.loads(message['game_state'])
        entry = GameStateEntry(
          game_state_id=self.max_id + 1,
          created_at=created_at,
          game_state=parse_game_state(game_state_json),
        )
        self.max_id = entry.game_state_id
        writer.write_message(entry)

      writer.flush()
    self.updater.send_message(command='process',
                              game_state_id=self.max_id)
