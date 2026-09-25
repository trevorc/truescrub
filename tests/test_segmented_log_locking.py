"""Exclusion guarantees for StateLogWriter.

StateLogWriter relies solely on an fcntl.flock over the log's .lock file.
flock is scoped to an open file description, so a second descriptor is denied
even within the same process and thread; fcntl.lockf, the POSIX record lock,
is scoped per process and would silently permit it. These tests hold against
either mechanism where the guarantee is the same, and fail if the per-
description scope is lost.

They are single-threaded or handshake-synchronised, so no assertion depends
on how threads happen to interleave.
"""
import datetime
import fcntl
import subprocess
import sys
import textwrap
import time

import pytest

from truescrub.proto.game_state_pb2 import GameStateEntry
from truescrub.statewriter import GameStateLog


def make_test_entry(game_state_id: int) -> GameStateEntry:
  entry = GameStateEntry(game_state_id=game_state_id)
  entry.created_at.FromDatetime(
    datetime.datetime(2023, 1, 1) + datetime.timedelta(seconds=game_state_id))
  return entry


class TestSameProcessExclusion:
  def test_second_writer_context_is_refused(self, tmp_path):
    log = GameStateLog(tmp_path)

    with log.writer() as first:
      first.append(make_test_entry(1))

      with pytest.raises(TimeoutError):
        with log.writer(timeout=0):
          pass

  def test_writer_is_available_again_after_release(self, tmp_path):
    log = GameStateLog(tmp_path)

    with log.writer() as first:
      first.append(make_test_entry(1))

    with log.writer(timeout=0) as second:
      second.append(make_test_entry(2))

    with log.reader() as reader:
      assert [r.game_state_id for r in reader.fetch_all()] == [1, 2]

  def test_release_survives_a_failed_append(self, tmp_path):
    log = GameStateLog(tmp_path)

    with log.writer() as writer:
      writer.append(make_test_entry(5))
      with pytest.raises(Exception):
        writer.append(make_test_entry(1))

    with log.writer(timeout=0) as writer:
      writer.append(make_test_entry(6))

    with log.reader() as reader:
      assert [r.game_state_id for r in reader.fetch_all()] == [5, 6]


HOLDER = textwrap.dedent('''
    import pathlib
    import sys
    import time

    from truescrub.statewriter import GameStateLog

    log_dir, acquired, release = (pathlib.Path(p) for p in sys.argv[1:4])
    with GameStateLog(log_dir).writer():
        acquired.touch()
        while not release.exists():
            time.sleep(0.01)
''')


class TestCrossProcessExclusion:
  """The flock is the only thing protecting against a second process.

  The in-process lock this replaced never covered this case at all.
  """

  def test_writer_held_by_another_process_is_refused(self, tmp_path):
    log_dir = tmp_path / 'log'
    acquired = tmp_path / 'acquired'
    release = tmp_path / 'release'
    script = tmp_path / 'holder.py'
    script.write_text(HOLDER)

    holder = subprocess.Popen(
      [sys.executable, str(script), str(log_dir), str(acquired), str(release)])
    try:
      deadline = time.monotonic() + 30.0
      while not acquired.exists():
        assert holder.poll() is None, 'holder exited before acquiring'
        assert time.monotonic() < deadline, 'holder never acquired the lock'
        time.sleep(0.01)

      with pytest.raises(TimeoutError):
        with GameStateLog(log_dir).writer(timeout=0):
          pass
    finally:
      release.touch()
      holder.wait(timeout=30)

    assert holder.returncode == 0

    with GameStateLog(log_dir).writer(timeout=0) as writer:
      writer.append(make_test_entry(1))


class TestExclusionIsLoadBearing:
  def test_without_flock_two_contexts_interleave_and_break_the_log(
      self, tmp_path, monkeypatch):
    """Without the lock, concurrent writers do not produce a readable log.

    Asserts only that the two records do not round-trip, not how riegeli
    fails, since that depends on its chunking.
    """
    monkeypatch.setattr(fcntl, 'flock', lambda fd, op: None)
    log = GameStateLog(tmp_path)

    with log.writer() as first:
      first.append(make_test_entry(1))
      first.flush()
      with log.writer(timeout=0) as second:
        second.append(make_test_entry(2))
        second.flush()
        first.append(make_test_entry(3))
        first.flush()
        second.append(make_test_entry(4))
        second.flush()

    try:
      with log.reader() as reader:
        recovered = [r.game_state_id for r in reader.fetch_all()]
    except Exception:
      return

    assert recovered != [1, 2, 3, 4], (
      'interleaved writers round-tripped cleanly, so this test no longer '
      'demonstrates what the lock prevents')


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xv", __file__]))
