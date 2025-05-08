import logging

from truescrub.queue_consumer import QueueConsumer
from truescrub import db

logger = logging.getLogger(__name__)

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
