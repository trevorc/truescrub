import abc
import argparse
import logging
import pathlib
import struct

from google.protobuf import text_format
from google.protobuf.timestamp_pb2 import Timestamp
import json
from tqdm import tqdm
from truescrub.proto import game_state_pb2
from truescrub.statewriter import GameStateLog

from truescrub.statewriter.state_serialization import parse_game_state, InvalidGameStateException
from truescrub.db import get_game_db, get_raw_game_states, get_game_state_count

logger = logging.getLogger(__name__)

class ConcatWriter(abc.ABC):
  def __init__(self, path):
    self.path = path

  def __enter__(self):
    self.fp = self.path.open('ab')
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.fp.close()

  def append(self, gs_proto: game_state_pb2.GameState):
    self.serialize(gs_proto, self.fp)

  @abc.abstractmethod
  def serialize(self, gs_proto, fp):
    pass


class TextProtoWriter(ConcatWriter):
  def serialize(self, gs_proto, fp):
    serialized = text_format.MessageToString(gs_proto)
    fp.write(f'{len(serialized)}\n'.encode('UTF-8'))
    fp.write(serialized.encode('UTF-8'))


class ProtosWriter:
  def serialize(self, gs_proto, fp):
    serialized = gs_proto.SerializeToString()
    fp.write(struct.pack('<l', len(serialized)))
    fp.write(serialized)


def RiegeliWriter(path):
  log = GameStateLog(path)
  return log.writer(0.0)


FORMATS = {
  'textpb': TextProtoWriter,
  'protos': ProtosWriter,
  'riegeli': RiegeliWriter,
}

def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('-o', '--output',
                          default='game_states.protos', type=pathlib.Path,
                          help='write delimited protos to this file')
  arg_parser.add_argument('-f', '--format', choices=FORMATS.keys(),
                          default='protos')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()

  with get_game_db() as game_db, \
       FORMATS[opts.format](opts.output) as writer:
    total = get_game_state_count(game_db=game_db)
    game_states = get_raw_game_states(game_db=game_db)
    for game_state_id, created_at, game_state in tqdm(game_states, total=total):
      try:
        gs_proto = parse_game_state(game_state)
      except InvalidGameStateException as e:
        logger.warning('skipping invalid round (reason: %s): %s',
                       e, json.dumps(game_state))
        continue
      timestamp = Timestamp()
      timestamp.FromSeconds(created_at)
      gs_entry = game_state_pb2.GameStateEntry(
          game_state_id=game_state_id,
          created_at=timestamp,
          game_state=gs_proto)
      writer.append(gs_entry)


if __name__ == '__main__':
  main()
