import argparse
import logging
import pathlib
import sys
from truescrub.proto.game_state_pb2 import GameStateEntry

import riegeli
from tqdm import tqdm
from truescrub.envconfig import SEGMENT_MAX_BYTES
from truescrub.statewriter import GameStateLog

logger = logging.getLogger(__name__)


def make_arg_parser():
  arg_parser = argparse.ArgumentParser(
    description='Compact a set of Riegeli game state logs into a segmented directory')
  arg_parser.add_argument('input_logs', type=pathlib.Path, nargs='+',
                          help='List of input riegeli files or directories')
  arg_parser.add_argument('--output-dir', type=pathlib.Path, required=True,
                          help='Target directory for segmented output')

  arg_parser.add_argument('--max-bytes', type=int, default=SEGMENT_MAX_BYTES,
                          help='Max bytes per segment')
  return arg_parser


def iter_input_records(input_logs):
  for input_path in input_logs:
    if input_path.is_file():
      files = [input_path]
    elif input_path.is_dir():
      files = sorted(input_path.glob('*.riegeli'))
    else:
      logger.warning(f"Input path {input_path} does not exist.")
      continue

    for filepath in files:
      logger.info(f"Reading from {filepath}")
      # Using native riegeli reader since we just want to drain the file sequentially
      with open(filepath, 'rb') as fp:
        reader = riegeli.RecordReader(fp, owns_src=False)
        reader.check_file_format()
        for record in reader.read_messages(message_type=GameStateEntry):
          yield record


def main():
  opts = make_arg_parser().parse_args()
  logging.basicConfig(level=logging.INFO)

  if opts.output_dir.exists() and not opts.output_dir.is_dir():
    logger.error(
      f"Output path {opts.output_dir} exists but is not a directory.")
    sys.exit(1)

  opts.output_dir.mkdir(parents=True, exist_ok=True)
  output_log = GameStateLog(opts.output_dir, max_bytes=opts.max_bytes)

  compacted_count = 0
  with output_log.writer(timeout=0) as writer:
    for record in tqdm(iter_input_records(opts.input_logs),
                       desc="Compacting records"):
      writer.append(record)
      compacted_count += 1

  logger.info(
    f"Successfully compacted {compacted_count} records into {opts.output_dir}")


if __name__ == '__main__':
  main()
