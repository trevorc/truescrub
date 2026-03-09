import datetime

from truescrub.proto.game_state_pb2 import GameStateEntry

import pytest
from truescrub.statewriter.game_state_log import (
  GameStateLog, Segment, segment_name)


def make_test_entry(game_state_id: int) -> GameStateEntry:
  # Using a simple empty payload with just the ID
  entry = GameStateEntry(game_state_id=game_state_id)
  entry.created_at.FromDatetime(
    datetime.datetime(2023, 1, 1) + datetime.timedelta(seconds=game_state_id))
  return entry


class TestSegmentInfo:
  def test_segment_name(self):
    assert segment_name(0x1) == '00000001.riegeli'
    assert segment_name(0xff) == '000000ff.riegeli'
    assert segment_name(0x2711) == '00002711.riegeli'

  def test_from_path(self, tmp_path):
    p = tmp_path / '00000001.riegeli'
    info = Segment.from_path(p)
    assert info is not None
    assert info.first_id == 1
    assert info.path == p

    info2 = Segment.from_path(tmp_path / '00002711.riegeli')
    assert info2.first_id == 0x2711

    assert Segment.from_path(tmp_path / 'not_a_segment.riegeli') is None


class TestGameStateLogDir:
  def test_empty_log_read(self, tmp_path):
    log = GameStateLog(tmp_path)
    with log.reader() as reader:
      assert list(reader.fetch_all()) == []

  def test_basic_write_and_read(self, tmp_path):
    log = GameStateLog(tmp_path)

    with log.writer() as writer:
      writer.append(make_test_entry(1))
      writer.append(make_test_entry(2))

    segments = list(tmp_path.glob('*.riegeli'))
    assert len(segments) == 1
    assert segments[0].name == '00000001.riegeli'

    with log.reader() as reader:
      records = list(reader.fetch_all())
      assert len(records) == 2
      assert records[0].game_state_id == 1
      assert records[1].game_state_id == 2

  def test_segment_rotation(self, tmp_path):
    log = GameStateLog(tmp_path, max_bytes=50)

    with log.writer() as writer:
      writer.append(make_test_entry(1))
      writer.append(make_test_entry(2))
      writer.append(make_test_entry(3))
      for i in range(4, 20):
        writer.append(make_test_entry(i))

    segments = sorted(list(tmp_path.glob('*.riegeli')))
    assert len(segments) > 1

    with log.reader() as reader:
      records = list(reader.fetch_all())
      assert len(records) == 19
      for i, r in enumerate(records):
        assert r.game_state_id == i + 1

  def test_fetch_last(self, tmp_path):
    log = GameStateLog(tmp_path, max_bytes=50)
    with log.writer() as writer:
      for i in range(1, 10):
        writer.append(make_test_entry(i))

    with log.reader() as reader:
      last = reader.fetch_last()
      assert last.game_state_id == 9

  def test_fetch_range(self, tmp_path):
    log = GameStateLog(tmp_path, max_bytes=50)
    with log.writer() as writer:
      for i in range(1, 20):
        writer.append(make_test_entry(i))

    with log.reader() as reader:
      records = list(reader.fetch(start_id=5, end_id=10))
      assert len(records) == 6
      assert [r.game_state_id for r in records] == [5, 6, 7, 8, 9, 10]

  def test_concurrent_write_lock(self, tmp_path):
    log1 = GameStateLog(tmp_path)
    log2 = GameStateLog(tmp_path)

    w1 = log1.writer()
    w1.__enter__()

    try:
      # log2 should fail to acquire lock
      w2 = log2.writer(timeout=0)
      with pytest.raises(TimeoutError):
        w2.__enter__()
    finally:
      w1.__exit__(None, None, None)

    # After release, log2 should be able to acquire
    w2 = log2.writer(timeout=0)
    w2.__enter__()
    w2.__exit__(None, None, None)

  def test_out_of_order_ids_during_rotation(self, tmp_path):
    """If IDs arrive out of order when a segment rotates, every record
    must still be retrievable via fetch_all()."""
    log = GameStateLog(tmp_path, max_bytes=50)

    with log.writer() as writer:
      # Write ascending IDs to fill the first segment(s)…
      for i in range(1, 6):
        writer.append(make_test_entry(i))
      # …then force a rotation by exceeding max_bytes and
      # append an ID that is *lower* than the previous entry.
      writer.append(make_test_entry(3))

    with log.reader() as reader:
      records = list(reader.fetch_all())

    # All six written records must come back, regardless of ordering.
    assert len(records) == 6

  def test_flush_makes_records_visible(self, tmp_path):
    """Calling flush() inside the writer context must persist buffered
    records so a concurrent reader can already see them."""
    log = GameStateLog(tmp_path)

    with log.writer() as writer:
      writer.append(make_test_entry(1))
      writer.append(make_test_entry(2))
      writer.flush()

      # Open a separate reader while the writer is still active.
      with log.reader() as reader:
        records = list(reader.fetch_all())

      assert len(records) == 2
      assert records[0].game_state_id == 1
      assert records[1].game_state_id == 2
