import argparse
import pathlib
import re
import struct
import sys
from google.protobuf import text_format
from truescrub.proto.game_state_pb2 import GameStateEntry

import riegeli
from truescrub.statewriter.game_state_log import StateLogWriter, \
  ReaderWriterLock


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('input_log', type=pathlib.Path,
                          help='path to corrupted riegeli game state log file')
  arg_parser.add_argument('--output', type=pathlib.Path, required=True,
                          help='path to write recovered records')
  arg_parser.add_argument('--verbose', action='store_true',
                          help='print verbose output')
  arg_parser.add_argument('--fix-dangerously', action='store_true',
                          help='attempt to fix block header hash mismatches by rewriting the file')
  return arg_parser


def run_recovery(opts):
  recovered_count = 0
  error_count = 0

  def recovery_callback(skipped_region):
    if opts.verbose:
      print(f"Skipped corrupt region: {skipped_region}", file=sys.stderr)
    nonlocal error_count
    error_count += 1
    return True

  with riegeli.RecordReader(open(opts.input_log, 'rb'),
                            recovery=recovery_callback) as reader, \
      StateLogWriter.create(open(opts.output, 'wb'), ReaderWriterLock(),
                            timeout=None) as writer:
    while True:
      try:
        record = reader.read_message(GameStateEntry)
        if record is None:
          break
        writer.append(record)
        recovered_count += 1
      except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        error_count += 1
        break

  print(f"Recovery complete.")
  print(f"Recovered {recovered_count} records.")
  print(f"Encountered {error_count} errors.")


def run_repair(opts):
  print("Starting repair pass...", file=sys.stderr)
  repair_count = 0
  current_offset = 0
  file_size = opts.input_log.stat().st_size

  while current_offset < file_size:
    restart_needed = False
    next_offset = current_offset

    def repair_callback(skipped_region):
      nonlocal repair_count
      nonlocal restart_needed
      nonlocal next_offset

      msg = str(skipped_region)
      if opts.verbose:
        print(f"Examining corrupt region at/after {current_offset}: {msg}",
              file=sys.stderr)

      match = re.search(
        r"block header hash mismatch \(computed (0x[0-9a-f]+), stored (0x[0-9a-f]+)\), block at (\d+)",
        msg)
      if match:
        computed_hex = match.group(1)
        block_offset = int(match.group(3))
        computed_val = int(computed_hex, 16)

        print(
          f"Attempting fix at offset {block_offset} with hash {computed_hex}...",
          file=sys.stderr)
        try:
          with open(opts.input_log, 'r+b') as f:
            f.seek(block_offset)
            f.write(struct.pack('<Q', computed_val))
          print("Fix applied successfully.", file=sys.stderr)
          repair_count += 1
          restart_needed = True
          next_offset = block_offset
          return False  # Stop reading to restart at this block
        except Exception as e:
          print(f"Failed to fix file: {e}", file=sys.stderr)

      # Always continue scanning
      return True

    if opts.verbose:
      print(f"Scanning from offset {current_offset}...", file=sys.stderr)

    # Open file and seek to current_offset
    f = open(opts.input_log, 'rb')
    f.seek(current_offset)

    try:
      with riegeli.RecordReader(f, recovery=repair_callback) as reader:
        # trigger callbacks
        for _ in reader.read_messages(GameStateEntry):
          pass
    except Exception:
      if not restart_needed:
        pass

    if restart_needed:
      current_offset = next_offset
      if opts.verbose:
        print(f"Resuming repair from offset {current_offset}...",
              file=sys.stderr)
    else:
      break

  print(f"Repair pass complete. Fixed {repair_count} blocks.", file=sys.stderr)


def main():
  opts = make_arg_parser().parse_args()

  if opts.fix_dangerously:
    run_repair(opts)

  run_recovery(opts)


if __name__ == '__main__':
  main()
