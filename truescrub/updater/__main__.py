"""Main module for the updater tool.

This module provides a command line interface for recalculating rankings
and evaluating TrueSkill parameters.
"""

import argparse
import logging
import os
from typing import Dict

from truescrub import db
from truescrub.updater.evaluator import evaluate_parameters
from truescrub.updater.recalculate import recalculate

logging.basicConfig(
    format="%(asctime)s.%(msecs).3dZ\t" "%(levelname)s\t%(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=os.environ.get("TRUESCRUB_LOG_LEVEL", "DEBUG"),
)
logger = logging.getLogger(__name__)


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "-c", "--recalculate", action="store_true", help="Recalculate rankings."
)
arg_parser.add_argument(
    "-e", "--evaluate", action="store_true", help="Evaluate parameters"
)
arg_parser.add_argument("--beta", type=float)
arg_parser.add_argument("--tau", type=float)
arg_parser.add_argument("--sample", type=float)


def main() -> None:
    """Main entry point for the updater tool.

    Parses command line arguments and calls the appropriate function based on
    the specified action. Exits if no action is specified.

    Raises:
        SystemExit: If no action is specified
    """
    args: argparse.Namespace = arg_parser.parse_args()
    db.initialize_dbs()

    if args.recalculate:
        recalculate()
        return
    elif args.evaluate:
        params: Dict[str, float] = {}
        if args.beta is not None:
            params["beta"] = args.beta
        if args.tau is not None:
            params["tau"] = args.tau
        if args.sample is not None:
            params["sample"] = args.sample
        evaluate_parameters(**params)
        return
    else:
        raise SystemExit("no action given")


if __name__ == "__main__":
    main()
