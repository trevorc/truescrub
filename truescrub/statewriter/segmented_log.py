import bisect
import contextlib
import fcntl
import logging
import operator
import pathlib
import re
import threading
from collections.abc import Callable, Iterator
from typing import Optional

from google.protobuf.message import Message

import riegeli

logger = logging.getLogger(__name__)


class Segment:
  def __init__(self, path: pathlib.Path, first_id: int):
    self.path = path
    self.first_id = first_id

  @classmethod
  def from_path(cls, path: pathlib.Path) -> Optional['Segment']:
    m = re.match(r'^([0-9a-fA-F]{8})\.riegeli$', path.name)
    if not m:
      return None
    return cls(path, int(m.group(1), 16))

  @contextlib.contextmanager
  def open(self):
    with open(self.path, 'rb') as fp:
      reader = riegeli.RecordReader(fp, owns_src=False)
      try:
        reader.check_file_format()
        yield reader
      finally:
        reader.close()


def segment_name(first_id: int) -> str:
  return f"{first_id:08x}.riegeli"


def list_segments(log_dir: pathlib.Path) -> list[Segment]:
  segments = []
  for f in log_dir.iterdir():
    info = Segment.from_path(f)
    if info:
      segments.append(info)
  segments.sort(key=operator.attrgetter('first_id'))
  return segments


class SegmentWriter:
  """Owns a single open segment file and its riegeli writer."""

  def __init__(self, path: pathlib.Path, first_id: int,
               message_type: type[Message], mode: str = 'wb'):
    self.path = path
    self.first_id = first_id
    self._fp = open(path, mode)
    metadata = riegeli.RecordsMetadata()
    riegeli.set_record_type(metadata, message_type)
    self._writer = riegeli.RecordWriter(
      self._fp, owns_dest=False, options='transpose', metadata=metadata)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()

  @classmethod
  def open_latest(cls, log_dir: pathlib.Path,
                  message_type: type[Message],
                  default_first_id: int = 1) -> 'SegmentWriter':
    """Opens the latest segment for appending, or creates the first one."""
    segments = list_segments(log_dir)
    if segments:
      seg = segments[-1]
      return cls(seg.path, seg.first_id, message_type, mode='ab')
    return cls(log_dir / segment_name(default_first_id),
               default_first_id, message_type)

  @property
  def pos(self) -> int:
    return self._fp.tell()

  def write_message(self, record: Message):
    self._writer.write_message(record)

  def flush(self):
    self._writer.flush()

  def close(self):
    self._writer.close()
    self._fp.close()


class StateLogWriter:
  def __init__(self, log_dir: pathlib.Path, max_bytes: int,
               write_lock: threading.Lock, lock_path: pathlib.Path,
               timeout: Optional[float],
               message_type: type[Message],
               id_getter: Callable[[Message], int]):
    self._log_dir = log_dir
    self._max_bytes = max_bytes
    self._write_lock = write_lock
    self._lock_path = lock_path
    self._timeout = timeout
    self._message_type = message_type
    self._id_getter = id_getter
    self._in_context = False
    self._segment: Optional[SegmentWriter] = None
    self._lock_file = None

  def __enter__(self):
    self._log_dir.mkdir(parents=True, exist_ok=True)
    lock_timeout = -1 if self._timeout is None else self._timeout
    if not self._write_lock.acquire(timeout=lock_timeout):
      raise TimeoutError("Timeout acquiring in-process write lock")

    acquired_fcntl = False
    try:
      self._acquire_fcntl()
      acquired_fcntl = True

      self._in_context = True
      self._segment = SegmentWriter.open_latest(
        self._log_dir, self._message_type)
      return self
    except Exception:
      if acquired_fcntl:
        self._release_fcntl()
      self._write_lock.release()
      raise

  def __exit__(self, exc_type, exc_val, exc_tb):
    try:
      if self._segment:
        self._segment.close()
        self._segment = None
      self._in_context = False
    finally:
      self._release_fcntl()
      self._write_lock.release()

  def _acquire_fcntl(self):
    import time
    self._lock_file = open(self._lock_path, 'a')

    if self._timeout is None or self._timeout < 0:
      fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX)
      return

    flags = fcntl.LOCK_EX | fcntl.LOCK_NB
    start_time = time.monotonic()
    while True:
      try:
        fcntl.flock(self._lock_file.fileno(), flags)
        return
      except OSError:
        if self._timeout == 0 or (
            time.monotonic() - start_time) >= self._timeout:
          self._lock_file.close()
          self._lock_file = None
          raise TimeoutError("Could not acquire fcntl write lock")
        time.sleep(0.01)

  def _release_fcntl(self):
    if self._lock_file:
      fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
      self._lock_file.close()
      self._lock_file = None

  def append(self, record: Message):
    if not self._in_context:
      raise RuntimeError('append() called outside of context manager')

    if self._segment.pos > self._max_bytes:
      record_id = self._id_getter(record)
      self._segment.close()
      self._segment = SegmentWriter(
        self._log_dir / segment_name(record_id),
        record_id, self._message_type)

    self._segment.write_message(record)

  def flush(self):
    if not self._in_context:
      raise RuntimeError('flush() called outside of context manager')
    if self._segment:
      self._segment.flush()


def _make_id_comparator(target_id: int,
                        id_getter: Callable[[Message], int]
                        ) -> Callable[[Message], int]:
  def compare(entry):
    entry_id = id_getter(entry)
    return (entry_id > target_id) - (entry_id < target_id)

  return compare


class NoSuchRecordException(LookupError):
  pass


class StateLogReader:
  def __init__(self, log_dir: pathlib.Path,
               message_type: type[Message],
               id_getter: Callable[[Message], int]):
    self._log_dir = log_dir
    self._message_type = message_type
    self._id_getter = id_getter
    self._segments: list[Segment] = []
    self._in_context = False

  def __enter__(self):
    self._segments = list_segments(self._log_dir)
    self._in_context = True
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self._in_context = False

  def __iter__(self) -> Iterator[Message]:
    return self.fetch_all()

  def _find_start_idx(self, target_id: int) -> int:
    idx = bisect.bisect_right(
      self._segments, target_id, key=operator.attrgetter('first_id'))
    return max(idx - 1, 0)

  def fetch_all(self, start_id: Optional[int] = None
                ) -> Iterator[Message]:
    if not self._in_context:
      raise RuntimeError('fetch_all() called outside of context manager')

    if not self._segments:
      return

    start_idx = 0
    if start_id is not None:
      start_idx = self._find_start_idx(start_id)

    for seg in self._segments[start_idx:]:
      with seg.open() as reader:
        if start_id is not None:
          reader.search_for_message(
            self._message_type,
            _make_id_comparator(start_id, self._id_getter))
          start_id = None
        for record in reader.read_messages(
            message_type=self._message_type):
          yield record

  def fetch_last(self) -> Message:
    if not self._in_context:
      raise RuntimeError('fetch_last() called outside of context manager')

    if not self._segments:
      raise NoSuchRecordException('no segments found')

    with self._segments[-1].open() as reader:
      reader.seek_numeric(reader.size())
      if not reader.seek_back():
        raise NoSuchRecordException(
          'failed to seek back from end of last segment')
      return reader.read_message(message_type=self._message_type)

  def fetch(self, start_id: int,
            end_id: Optional[int] = None) -> Iterator[Message]:
    if not self._in_context:
      raise RuntimeError('fetch() called outside of context manager')

    if end_id is None:
      end_id = start_id

    if not self._segments:
      return

    start_idx = self._find_start_idx(start_id)
    search_id = start_id

    for seg in self._segments[start_idx:]:
      if seg.first_id > end_id:
        break

      with seg.open() as reader:
        if search_id is not None:
          reader.search_for_message(
            self._message_type,
            _make_id_comparator(search_id, self._id_getter))
          search_id = None

        for record in reader.read_messages(
            message_type=self._message_type):
          record_id = self._id_getter(record)
          if record_id > end_id:
            return
          if start_id <= record_id <= end_id:
            yield record


class SegmentedLog:
  def __init__(self, log_dir: pathlib.Path,
               message_type: type[Message],
               id_getter: Callable[[Message], int],
               max_bytes: int):
    self.log_dir = log_dir
    self.max_bytes = max_bytes
    self._message_type = message_type
    self._id_getter = id_getter
    self._write_lock = threading.Lock()
    self._lock_path = self.log_dir / '.lock'
    self.log_dir.mkdir(parents=True, exist_ok=True)
    logger.debug('Initializing SegmentedLog in %s', log_dir)

  def writer(self, timeout: Optional[float] = None) -> 'StateLogWriter':
    return StateLogWriter(
      self.log_dir, self.max_bytes, self._write_lock, self._lock_path,
      timeout, self._message_type, self._id_getter)

  def reader(self) -> 'StateLogReader':
    return StateLogReader(
      self.log_dir, self._message_type, self._id_getter)
