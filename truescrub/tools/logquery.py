import argparse
import pathlib
import sys

from google.protobuf import text_format

from truescrub.statewriter import GameStateLog


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('--begin', type=int, help='read from this id')
  arg_parser.add_argument('--end', type=int, help='read to this id')
  arg_parser.add_argument('--last', action='store_true',
                          help='read the last entry')
  arg_parser.add_argument('--mode', choices=['print', 'count'], default='print')
  arg_parser.add_argument('game_state_log', type=pathlib.Path,
                          help='path to riegeli game state log file')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()
  log = GameStateLog(opts.game_state_log)
  count = 0
  begin = opts.begin if opts.begin else 0
  end = opts.end if opts.end else sys.maxsize

  with log.reader() as reader:
    if opts.last:
      entry = reader.fetch_last()
      print(text_format.MessageToString(entry))
      return

    for entry in reader.fetch_all(begin):
      if entry.game_state_id < begin:
        continue
      if entry.game_state_id > end:
        break
      if opts.mode == 'print':
        print(text_format.MessageToString(entry))
      elif opts.mode == 'count':
        count += 1
  if opts.mode == 'count':
    print(count)


if __name__ == '__main__':
  main()
