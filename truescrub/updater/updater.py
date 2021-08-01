import os
import queue
import logging
import argparse
import threading

from .. import db
from .recalculate import recalculate, compute_rounds_and_players, \
    recalculate_ratings
from .evaluator import evaluate_parameters


QUEUE_DONE = object()
_message_queue = queue.SimpleQueue()


logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG'))
logger = logging.getLogger(__name__)


def process_game_states(game_states):
    logger.debug('processing game states %s', game_states)
    with db.get_game_db() as game_db, \
            db.get_skill_db() as skill_db:
        max_processed_game_state = db.get_game_state_progress(skill_db)
        new_max_game_state = max(game_states)
        game_state_range = (max_processed_game_state + 1, new_max_game_state)
        new_rounds = compute_rounds_and_players(
                game_db, skill_db, game_state_range)[1]
        if new_rounds is not None:
            recalculate_ratings(skill_db, new_rounds)
        db.save_game_state_progress(skill_db, new_max_game_state)
        skill_db.commit()


def send_message(message: dict):
    _message_queue.put(message)


def drain_queue():
    messages = [_message_queue.get()]
    try:
        while True:
            messages.append(_message_queue.get_nowait())
    except queue.Empty:
        return messages


def run_updater():
    done = False

    while not done:
        messages = drain_queue()
        if QUEUE_DONE in messages:
            logger.info('got done message')
            del messages[messages.index(QUEUE_DONE):]
            if len(messages) == 0:
                return
            done = True

        logger.debug('processing %d messages', len(messages))
        if any(message['command'] == 'recalculate' for message in messages):
            recalculate()
        else:
            process_game_states([
                message['game_state_id']
                for message in messages
            ])


class UpdaterThread(threading.Thread):
    def __init__(self):
        super().__init__(name='updater')

    def run(self) -> None:
        run_updater()

    def stop(self):
        _message_queue.put(QUEUE_DONE)


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-e', '--evaluate', action='store_true',
                        help='Evaluate parameters')
arg_parser.add_argument('--beta', type=float)
arg_parser.add_argument('--tau', type=float)
arg_parser.add_argument('--sample', type=float)


def main():
    args = arg_parser.parse_args()
    db.initialize_dbs()
    if args.recalculate:
        return recalculate()
    elif args.evaluate:
        params = {}
        if args.beta:
            params['beta'] = args.beta
        if args.tau:
            params['tau'] = args.tau
        if args.sample:
            params['sample'] = args.sample
        return evaluate_parameters(**params)
    else:
        raise SystemExit('no action given')


if __name__ == '__main__':
    main()
