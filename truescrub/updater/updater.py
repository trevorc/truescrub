import logging
from typing import Callable

from truescrub import db
from truescrub.queue_consumer import QueueConsumer
from truescrub.updater.recalculate import recalculate, \
  compute_rounds_and_players, recalculate_ratings
from truescrub.updater.state_loader import StateLoader

logger = logging.getLogger(__name__)


def process_game_states(state_loader, game_states):
  logger.debug('processing game states %s', game_states)
  with db.get_skill_db() as skill_db:
    max_processed_game_state = db.get_game_state_progress(skill_db)
    new_max_game_state = max(game_states)
    game_state_range = (max_processed_game_state + 1, new_max_game_state)
    new_rounds = compute_rounds_and_players(
      state_loader, skill_db, game_state_range)[1]
    if new_rounds is not None:
      recalculate_ratings(skill_db, new_rounds)
    db.save_game_state_progress(skill_db, new_max_game_state)
    skill_db.commit()


class Updater(QueueConsumer):
  def __init__(self, state_loader_provider: Callable[[], StateLoader]):
    super().__init__()
    self.state_loader_provider = state_loader_provider

  def process_messages(self, messages):
    with self.state_loader_provider() as state_loader:
      if any(message['command'] == 'recalculate' for message in messages):
        logger.debug('%s processing recalculate message',
                     type(self).__name__)
        recalculate(state_loader)
      else:
        logger.debug('%s processing %d game states', type(self).__name__,
                     len(messages))
        process_game_states(state_loader, [
          message['game_state_id'] for message in messages
        ])
