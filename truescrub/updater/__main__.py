import os
import logging
import argparse

from truescrub import db
from truescrub.updater.recalculate import recalculate
from truescrub.updater.evaluator import evaluate_parameters


logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG'))
logger = logging.getLogger(__name__)


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
