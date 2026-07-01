import argparse
import pathlib
import re
import struct
import sys

from google.protobuf import text_format
from truescrub.proto.game_state_pb2 import GameStateEntry
from truescrub.statewriter import GameStateLog
from truescrub.statewriter.segmented_log import list_segments


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('input_log', type=pathlib.Path,
                          help='path to corrupted riegeli game state directory or file')
  arg_parser.add_argument('--output', type=pathlib.Path, required=True,
                          help='path to write recovered records directory')
  arg_parser.add_argument('--verbose', action='store_true',
                          help='print verbose output')
  arg_parser.add_argument('--fix-dangerously', action='store_true',
                          help='attempt to fix block header hash mismatches by rewriting the file(s)')
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

  if opts.input_log.is_file():
    inputs = [opts.input_log]
  else:
    from truescrub.statewriter.game_state_log import list_segments
    inputs = [seg.path for seg in list_segments(opts.input_log)]

  from truescrub.envconfig import SEGMENT_MAX_BYTES
  output_log = GameStateLog(opts.output, max_bytes=SEGMENT_MAX_BYTES)

  with output_log.writer(timeout=0) as writer:
    for input_file in inputs:
      if opts.verbose:
        print(f"Recovering from {input_file}", file=sys.stderr)

      with riegeli.RecordReader(open(input_file, 'rb'),
                                recovery=recovery_callback) as reader:
        while True:
          try:
            record = reader.read_message(GameStateEntry)
            if record is None:
              break
            writer.append(record)
            recovered_count += 1
          except Exception as e:
            print(f"Unexpected error in {input_file}: {e}", file=sys.stderr)
            error_count += 1
            break

  print(f"Recovery complete.")
  print(f"Recovered {recovered_count} records.")
  print(f"Encountered {error_count} errors.")


def run_repair(opts):
  repair_count = 0
  if opts.input_log.is_file():
    inputs = [opts.input_log]
  else:
    inputs = [seg.path for seg in list_segments(opts.input_log)]

  for input_file in inputs:
    current_offset = 0
    file_size = input_file.stat().st_size

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
          with open(input_file, 'r+b') as f:
            f.seek(block_offset)
            f.write(struct.pack('<Q', computed_val))
          print("Fix applied successfully.", file=sys.stderr)
          repair_count += 1
          restart_needed = True
          next_offset = block_offset
          return False  # Stop reading to restart at this block
        except Exception as e:
          print(f"Failed to fix file {input_file}: {e}", file=sys.stderr)

      # Always continue scanning
      return True

    # Open file and seek to current_offset
    f = open(input_file, 'rb')
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
