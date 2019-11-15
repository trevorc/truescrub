import itertools
import operator
import queue
import atexit
import argparse
import threading

import zmq
import logging

from .. import db
from .recalculate import recalculate, compute_rounds_and_players, \
    rate_players, rate_players_by_season
from .evaluator import evaluate_parameters


STOP = object()
zmq_socket = zmq.Context().socket(zmq.PULL)
command_queue = queue.Queue()

logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)


def recalculate_incremental(skill_db, round_range: (int, int)):
    logger.debug('recalculating for rounds between %d and %d', *round_range)
    rounds = list(db.get_all_rounds(skill_db, round_range))
    teams = db.get_all_teams(skill_db)

    player_ratings = {
        player['player_id']: player['rating']
        for player in db.get_player_overall_skills(skill_db)
    }
    ratings = rate_players(rounds, teams, player_ratings)
    db.update_player_skills(skill_db, ratings)

    rounds_by_season = {
        season_id: list(rounds)
        for season_id, rounds in itertools.groupby(
                rounds, operator.itemgetter('season_id'))
    }
    season_ratings = db.get_ratings_by_season(
            skill_db, seasons=list(rounds_by_season.keys()))
    new_season_ratings = rate_players_by_season(
            rounds_by_season, teams, season_ratings)
    db.replace_season_skills(skill_db, new_season_ratings)


def process_game_states(game_states):
    logger.debug('processing game states %s', game_states)
    with db.get_game_db() as game_db, \
            db.get_skill_db() as skill_db:
        max_processed_game_state = db.get_game_state_progress(skill_db)
        new_max_game_state = max(game_states)
        game_state_range = (max_processed_game_state + 1, new_max_game_state)
        new_rounds = compute_rounds_and_players(
                game_db, skill_db, game_state_range)[1]

        recalculate_incremental(skill_db, new_rounds)
        db.save_game_state_progress(skill_db, new_max_game_state)
        skill_db.commit()


# TODO: operate directly on ZMQ queue
def drain_queue(q):
    messages = [q.get(timeout=1.0)]
    try:
        while True:
            messages.append(q.get_nowait())
    except queue.Empty:
        return messages


def run_updater():
    while True:
        try:
            messages = drain_queue(command_queue)
            if STOP in messages:
                print('Stopping updater.')
                return
            if any(message['command'] == 'recalculate' for message in messages):
                recalculate()
                continue
            process_game_states([
                message['game_state_id']
                for message in messages
            ])
        except queue.Empty:
            pass


updater_thread = threading.Thread(
        target=run_updater, name='incremental_updater')


def shut_down():
    command_queue.put(STOP)


def start_updater_thread():
    atexit.register(shut_down)
    updater_thread.start()


def start_updater(addr: str, port: int):
    endpoint = 'tcp://{}:{}'.format(addr, port)
    print('Binding ZeroMQ to {}'.format(endpoint))
    zmq_socket.bind(endpoint)
    start_updater_thread()

    try:
        while True:
            command_queue.put(zmq_socket.recv_json())
    except KeyboardInterrupt:
        shut_down()


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-y', '--zmq-addr', metavar='HOST', default='0.0.0.0',
                        help='Bind zeromq on this address.')
arg_parser.add_argument('-z', '--zmq-port', type=int,
                        default=5555, help='Bind zeromq on this port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-r', '--use-reloader', action='store_true',
                        help='Use code reloader.')
arg_parser.add_argument('-e', '--evaluate', action='store_true',
                        help='Evaluate parameters')
arg_parser.add_argument('--beta', type=float)
arg_parser.add_argument('--tau', type=float)
arg_parser.add_argument('--sample', type=float)


def main():
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


db.initialize_dbs()


if __name__ == '__main__':
    main()
