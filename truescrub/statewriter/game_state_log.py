import operator

from truescrub.envconfig import SEGMENT_MAX_BYTES
from truescrub.proto.game_state_pb2 import GameStateEntry
from truescrub.statewriter.segmented_log import SegmentedLog

GAME_STATE_ID_GETTER = operator.attrgetter('game_state_id')


class GameStateLog(SegmentedLog):
  """GameStateLog pre-wired with GameStateEntry message type."""

  def __init__(self, log_dir, max_bytes=SEGMENT_MAX_BYTES):
    super().__init__(log_dir, GameStateEntry, GAME_STATE_ID_GETTER,
                     max_bytes=max_bytes)
