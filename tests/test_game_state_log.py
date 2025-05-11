import pathlib
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from google.protobuf import text_format
from truescrub.proto.game_state_pb2 import GameStateEntry

from truescrub.statewriter import GameStateLog
from truescrub.statewriter.game_state_log import ReaderWriterLock, \
  NoSuchRecordException

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
    self.temp_file = tempfile.NamedTemporaryFile()
    self.game_state_log = GameStateLog(pathlib.Path(self.temp_file.name))

  def tearDown(self):
    self.temp_file.close()

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
    writer.writer.close()

    reader = self.game_state_log.reader()
    with self.assertRaises(RuntimeError):
      next(reader.fetch(1))
    reader.reader.close()


class TestReaderWriterLock(unittest.TestCase):
  def setUp(self):
    self.lock = ReaderWriterLock()
    self.reader_count = 0
    self.reader_count_lock = threading.Lock()
    self.writer_active = False
    self.writer_active_lock = threading.Lock()
    self.reader_wait_count = 0
    self.reader_wait_count_lock = threading.Lock()

  def test_multiple_readers(self):
    start_barrier = threading.Barrier(5)
    max_readers = threading.Event()
    readers_done = threading.Event()

    def reader_task():
      start_barrier.wait()

      self.lock.acquire_read()
      try:
        with self.reader_count_lock:
          self.reader_count += 1
          if self.reader_count == 5:
            max_readers.set()

        self.assertTrue(max_readers.wait(timeout=1.0))
        time.sleep(0.1)
      finally:
        self.lock.release_read()
        with self.reader_count_lock:
          self.reader_count -= 1
          if self.reader_count == 0:
            readers_done.set()

    with ThreadPoolExecutor(max_workers=5) as executor:
      futures = [executor.submit(reader_task) for _ in range(5)]
      readers_done.wait(timeout=2.0)

      for future in futures:
        future.result()

    self.assertEqual(self.reader_count, 0)
    self.assertTrue(max_readers.is_set(),
                    "Not all readers acquired the lock simultaneously")

  def test_writer_exclusivity(self):
    ready_event = threading.Event()

    def writer_task():
      self.lock.acquire_write()
      try:
        with self.writer_active_lock:
          self.assertTrue(not self.writer_active)
          self.writer_active = True

        ready_event.set()

        with self.writer_active_lock:
          self.writer_active = False
      finally:
        self.lock.release_write()

    def reader_task():
      ready_event.wait()

      self.lock.acquire_read()
      try:
        with self.writer_active_lock:
          self.assertFalse(self.writer_active)
      finally:
        self.lock.release_read()

    with ThreadPoolExecutor(max_workers=6) as executor:
      writer_future = executor.submit(writer_task)
      reader_futures = [executor.submit(reader_task) for _ in range(5)]

      writer_future.result()
      for future in reader_futures:
        future.result()

  def test_writer_preference(self):
    writer_waiting = threading.Event()
    reader_start = threading.Event()
    reader_ready = threading.Event()

    def initial_reader():
      self.lock.acquire_read()
      try:
        reader_start.set()
        writer_waiting.wait(timeout=1.0)
      finally:
        self.lock.release_read()

    def writer_task():
      reader_start.wait()
      writer_waiting.set()

      self.lock.acquire_write()
      try:
        reader_ready.set()
      finally:
        self.lock.release_write()

    def new_reader_task():
      writer_waiting.wait()

      with self.reader_wait_count_lock:
        self.reader_wait_count += 1

      reader_ready.wait()

      self.lock.acquire_read()
      try:
        pass
      finally:
        self.lock.release_read()
        with self.reader_wait_count_lock:
          self.reader_wait_count -= 1

    with ThreadPoolExecutor(max_workers=7) as executor:
      initial_reader_future = executor.submit(initial_reader)
      writer_future = executor.submit(writer_task)
      reader_futures = [executor.submit(new_reader_task) for _ in range(5)]

      initial_reader_future.result()
      writer_future.result()
      for future in reader_futures:
        future.result()

    self.assertEqual(self.reader_wait_count, 0)


class TestStateLogInteraction(unittest.TestCase):
  def setUp(self):
    self.temp_file = tempfile.NamedTemporaryFile()
    self.game_state_log = GameStateLog(pathlib.Path(self.temp_file.name))

  def tearDown(self):
    self.temp_file.close()

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


if __name__ == '__main__':
  unittest.main()
