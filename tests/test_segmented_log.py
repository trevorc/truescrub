import pathlib
import pytest
import tempfile
import unittest
from google.protobuf import text_format
from truescrub.proto.game_state_pb2 import GameStateEntry
from unittest import mock

from truescrub.statewriter import GameStateLog
from truescrub.statewriter.segmented_log import NoSuchRecordException
from truescrub.statewriter.segmented_log import Segment

SAMPLE_GAME_STATE_ENTRY = text_format.Parse('''
game_state_id: 1
created_at {
    seconds: 1557535071
}
game_state {
    provider {
        name: "Counter-Strike: Global Offensive"
        app_id: 730
        version: 13694
        steam_id: 76561198413889827
        timestamp {
            seconds: 1557535071
        }
    }
    map {
        mode: MODE_SCRIMCOMP2V2
        name: "de_shortnuke"
        phase: MAP_PHASE_LIVE
        round: 1
        team_t {
            score: 0
            consecutive_round_losses: 1
            timeouts_remaining: 1
            matches_won_this_series: 0
        }
        team_ct {
            score: 0
            consecutive_round_losses: 0
            timeouts_remaining: 1
            matches_won_this_series: 0
        }
    }
}
''', GameStateEntry())


class TestGameStateLog(unittest.TestCase):
  def setUp(self):
    self.temp_dir = tempfile.TemporaryDirectory()
    self.game_state_log = GameStateLog(pathlib.Path(self.temp_dir.name))

  def tearDown(self):
    self.temp_dir.cleanup()

  def test_write_and_read_game_state(self):
    with self.game_state_log.writer() as writer:
      writer.append(SAMPLE_GAME_STATE_ENTRY)

    with self.game_state_log.reader() as reader:
      read_entries = [entry for entry in reader.fetch(1)]

    self.assertEqual(len(read_entries), 1)
    self.assertEqual(
      read_entries[0].game_state.provider.name,
      "Counter-Strike: Global Offensive")
    self.assertEqual(
      read_entries[0].game_state.map.name,
      "de_shortnuke")

  def test_fetch_specific_id_range(self):
    with self.game_state_log.writer() as writer:
      for i in range(5):
        entry = GameStateEntry()
        entry.CopyFrom(SAMPLE_GAME_STATE_ENTRY)
        entry.game_state_id = i
        entry.game_state.map.round = i
        writer.append(entry)

    read_entries = []
    with self.game_state_log.reader() as reader:
      for state_entry in reader.fetch(2, 4):
        read_entries.append(state_entry)

    self.assertEqual(len(read_entries), 3)
    rounds = sorted([entry.game_state.map.round for entry in read_entries])
    self.assertTrue(all(1 <= r <= 4 for r in rounds))

  def test_fetch_last(self):
    with self.game_state_log.reader() as reader:
      with self.assertRaises(NoSuchRecordException):
        reader.fetch_last()

    with self.game_state_log.writer() as writer:
      entry = GameStateEntry()
      entry.CopyFrom(SAMPLE_GAME_STATE_ENTRY)
      entry.game_state_id = 10
      writer.append(entry)

    with self.game_state_log.reader() as reader:
      last_entry = reader.fetch_last()
      self.assertEqual(last_entry.game_state_id, 10)

    with self.game_state_log.writer() as writer:
      for i in range(11, 14):
        entry = GameStateEntry()
        entry.CopyFrom(SAMPLE_GAME_STATE_ENTRY)
        entry.game_state_id = i
        writer.append(entry)

    with self.game_state_log.reader() as reader:
      last_entry = reader.fetch_last()
      self.assertEqual(last_entry.game_state_id, 13)

  def test_invalid_operations(self):
    writer = self.game_state_log.writer()
    with self.assertRaises(RuntimeError):
      writer.append(SAMPLE_GAME_STATE_ENTRY)

    reader = self.game_state_log.reader()
    with self.assertRaises(RuntimeError):
      next(reader.fetch(1))


class TestStateLogInteraction(unittest.TestCase):
  def setUp(self):
    self.temp_dir = tempfile.TemporaryDirectory()
    self.game_state_log = GameStateLog(pathlib.Path(self.temp_dir.name))

  def tearDown(self):
    self.temp_dir.cleanup()

  def test_writer_create_new_file(self):
    entry1 = GameStateEntry(game_state_id=1)
    with self.game_state_log.writer() as writer:
      writer.append(entry1)

    with self.game_state_log.reader() as reader:
      entries = list(reader.fetch_all())
    self.assertSequenceEqual(entries, [entry1])

    entry2 = GameStateEntry(game_state_id=2)
    with self.game_state_log.writer() as writer:
      writer.append(entry2)
    with self.game_state_log.reader() as reader:
      entries = list(reader.fetch_all())
    self.assertSequenceEqual(entries, [entry1, entry2])

  def test_reader_fetch_all_with_none_start_id(self):
    with self.game_state_log.writer() as writer:
      for i in range(1, 4):
        writer.append(GameStateEntry(game_state_id=i))

    with self.game_state_log.reader() as reader:
      entries = list(reader.fetch_all(start_id=None))
    self.assertEqual(len(entries), 3)
    self.assertListEqual([e.game_state_id for e in entries], [1, 2, 3])

  def test_reader_fetch_start_id_greater_than_existing(self):
    with self.game_state_log.writer() as writer:
      writer.append(GameStateEntry(game_state_id=1))
      writer.append(GameStateEntry(game_state_id=2))

    with self.game_state_log.reader() as reader:
      entries = list(reader.fetch(start_id=5))
    self.assertEqual(len(entries), 0)

    with self.game_state_log.reader() as reader:
      entries = list(reader.fetch(start_id=5, end_id=10))
    self.assertEqual(len(entries), 0)

  @mock.patch('fcntl.flock')
  def test_writer_timeout_polling(self, mock_flock):
    mock_flock.side_effect = BlockingIOError

    with self.assertRaises(TimeoutError):
      with self.game_state_log.writer(timeout=0.05) as writer:
        pass

    self.assertGreater(mock_flock.call_count, 1)



  def test_lock_released_on_exception(self):
    """Writer must release both threading and fcntl locks when an exception
    is raised inside the context manager, so the next writer can proceed."""
    with self.assertRaises(RuntimeError):
      with self.game_state_log.writer() as writer:
        writer.append(GameStateEntry(game_state_id=1))
        raise RuntimeError("simulated crash")

    # A subsequent writer should acquire the lock without blocking.
    with self.game_state_log.writer(timeout=0) as writer:
      writer.append(GameStateEntry(game_state_id=2))

    with self.game_state_log.reader() as reader:
      entries = list(reader.fetch_all())

    # The entry from the crashed session was flushed before the error, so
    # we may or may not see it depending on buffering — but entry 2 must
    # be present, proving the lock was freed.
    ids = [e.game_state_id for e in entries]
    self.assertIn(2, ids)


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xv", __file__]))


