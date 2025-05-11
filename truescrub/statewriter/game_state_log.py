import pathlib
import threading
from io import FileIO
from typing import Optional, Iterator

import riegeli
from truescrub.proto.game_state_pb2 import GameStateEntry


class ReaderWriterLock:
  def __init__(self):
    self._read_lock = threading.Condition()
    self._write_lock = threading.Condition(self._read_lock)
    self._readers = 0
    self._writer_waiting = False

  def acquire_read(self, timeout: Optional[float] = None):
    with self._read_lock:
      while self._writer_waiting:
        self._read_lock.wait(timeout=timeout)
      self._readers += 1

  def release_read(self):
    with self._read_lock:
      self._readers -= 1
      if self._readers == 0:
        self._write_lock.notify_all()

  def acquire_write(self, timeout: Optional[float] = None):
    with self._write_lock:
      self._writer_waiting = True
      while self._readers > 0:
        self._write_lock.wait(timeout=timeout)

  def release_write(self):
    with self._write_lock:
      self._writer_waiting = False
      self._write_lock.notify_all()
      self._read_lock.notify_all()


class StateLogWriter:
  def __init__(self, writer: riegeli.RecordWriter, lock: ReaderWriterLock,
               timeout: Optional[int]):
    self.writer = writer
    self.lock = lock
    self.timeout = timeout
    self._in_context = False

  @classmethod
  def create(cls, fp: FileIO, lock: ReaderWriterLock, timeout: Optional[int]):
    metadata = riegeli.RecordsMetadata()
    riegeli.set_record_type(metadata, GameStateEntry)
    record_writer = riegeli.RecordWriter(
      fp, owns_dest=True, options='transpose', metadata=metadata)
    return cls(record_writer, lock, timeout)

  def __enter__(self):
    self.lock.acquire_write(self.timeout)
    self._in_context = True
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    try:
      self.writer.close()
      self._in_context = False
    finally:
      self.lock.release_write()

  def append(self, game_state: GameStateEntry):
    if not self._in_context:
      raise RuntimeError('append() called outside of context manager')
    self.writer.write_message(game_state)


def test_fn(search_target):
  def compare(entry):
    return ((entry.game_state_id > search_target) -
            (entry.game_state_id < search_target))

  return compare


class NoSuchRecordException(Exception):
  pass


class StateLogReader:
  def __init__(self, reader: riegeli.RecordReader, lock: ReaderWriterLock,
               timeout: Optional[float]):
    self.reader = reader
    self.lock = lock
    self.timeout = timeout
    self._in_context = False

  @classmethod
  def create(cls, fp, lock, timeout):
    return cls(riegeli.RecordReader(fp, owns_src=True), lock, timeout)

  def __enter__(self):
    self.lock.acquire_read(self.timeout)
    self._in_context = True
    self.reader.check_file_format()
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    try:
      self.reader.close()
      self._in_context = False
    finally:
      self.lock.release_read()

  def __iter__(self) -> Iterator[GameStateEntry]:
    return self.fetch_all()

  def _seek_to_last(self):
    file_size = self.reader.size()
    self.reader.seek_numeric(file_size)
    if not self.reader.seek_back():
      raise NoSuchRecordException('failed to seek to last record')

  def fetch_all(self, start_id: Optional[int] = None) -> Iterator[GameStateEntry]:
    if not self._in_context:
      raise RuntimeError('fetch_all() called outside of context manager')

    if start_id is not None:
      self.reader.search_for_message(GameStateEntry, test_fn(start_id))
    return self.reader.read_messages(message_type=GameStateEntry)

  def fetch_last(self) -> GameStateEntry:
    if not self._in_context:
      raise RuntimeError('fetch_last() called outside of context manager')
    self._seek_to_last()
    return self.reader.read_message(message_type=GameStateEntry)

  def fetch(self, start_id: int,
            end_id: Optional[int] = None) -> Iterator[GameStateEntry]:
    if not self._in_context:
      raise RuntimeError('fetch() called outside of context manager')

    if end_id is None:
      end_id = start_id
    self.reader.search_for_message(GameStateEntry, test_fn(start_id))

    for record in self.reader.read_messages(message_type=GameStateEntry):
      if start_id <= record.game_state_id <= end_id:
        yield record


class GameStateLog:
  def __init__(self, log_path: pathlib.Path):
    self.log_path = log_path
    self.lock = ReaderWriterLock()

  def writer(self, timeout: Optional[float] = None):
    return StateLogWriter.create(
      FileIO(self.log_path, mode='ab'), self.lock, timeout)

  def reader(self, timeout: Optional[float] = None):
    return StateLogReader.create(
      FileIO(self.log_path, mode='rb'), self.lock, timeout)
