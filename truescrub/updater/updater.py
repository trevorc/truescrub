import os
import logging
import argparse

import zmq

from .. import db
from .recalculate import recalculate, compute_rounds_and_players, \
    recalculate_ratings
from .evaluator import evaluate_parameters


zmq_socket = zmq.Context().socket(zmq.PULL)

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


def drain_queue():
    messages = [zmq_socket.recv_json()]
    try:
        while True:
            messages.append(zmq_socket.recv_json(zmq.NOBLOCK))
    except zmq.Again:
        return messages


def run_updater():
    while True:
        messages = drain_queue()
        logger.debug('processing %d messages', len(messages))
        if any(message['command'] == 'recalculate' for message in messages):
            recalculate()
        else:
            process_game_states([
                message['game_state_id']
                for message in messages
            ])


def start_updater(addr: str, port: int):
    endpoint = 'tcp://{}:{}'.format(addr, port)
    logger.info('Binding ZeroMQ to {}'.format(endpoint))
    zmq_socket.bind(endpoint)
    run_updater()


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-y', '--zmq-addr', metavar='HOST', default='0.0.0.0',
                        help='Bind zeromq on this address.')
arg_parser.add_argument('-z', '--zmq-port', type=int,
                        default=5555, help='Bind zeromq on this port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-e', '--evaluate', action='store_true',
                        help='Evaluate parameters')
arg_parser.add_argument('--beta', type=float)
arg_parser.add_argument('--tau', type=float)
arg_parser.add_argument('--sample', type=float)


def main():
    db.initialize_dbs()
    args = arg_parser.parse_args()
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
    start_updater(args.zmq_addr, args.zmq_port)


if __name__ == '__main__':
    main()
