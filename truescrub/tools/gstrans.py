import argparse
import struct

from google.protobuf import text_format
from google.protobuf.timestamp_pb2 import Timestamp
from truescrub.proto import game_state_pb2

from truescrub.state_serialization import parse_game_state
from truescrub.db import get_game_db, get_raw_game_states


def write_textpb(gs_proto: game_state_pb2.GameState, output):
  serialized = text_format.MessageToString(gs_proto)
  output.write(f'{len(serialized)}\n'.encode('UTF-8'))
  output.write(serialized.encode('UTF-8'))


def write_protos(gs_proto: game_state_pb2.GameState, output):
  serialized = gs_proto.SerializeToString()
  output.write(struct.pack('<l', len(serialized)))
  output.write(serialized)


FORMATS = {
  'textpb': write_textpb,
  'protos': write_protos,
}


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('-o', '--output', default='game_states.protos',
                          help='write delimited protos to this file')
  arg_parser.add_argument('-f', '--format', choices=FORMATS.keys(),
                          default='protos')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()

  with get_game_db() as game_db, open(opts.output, 'wb') as output:
    writer = FORMATS[opts.format]
    game_states = get_raw_game_states(game_db=game_db)
    for game_state_id, created_at, game_state in game_states:
      gs_proto = parse_game_state(game_state)
      timestamp = Timestamp()
      timestamp.FromSeconds(created_at)
      gs_entry = game_state_pb2.GameStateEntry(
          game_state_id=game_state_id,
          created_at=timestamp,
          game_state=gs_proto)
      writer(gs_entry, output)


if __name__ == '__main__':
  main()
