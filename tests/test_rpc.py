import datetime

import pytest

from truescrub.rpc import parse_timezone


class TestParseTimezone:
  def test_positive_offset(self):
    tz = parse_timezone('+05:00')
    assert tz.utcoffset(None) == datetime.timedelta(hours=5)

  def test_negative_offset(self):
    tz = parse_timezone('-05:00')
    assert tz.utcoffset(None) == datetime.timedelta(hours=-5)

  def test_zero_offset(self):
    tz = parse_timezone('+00:00')
    assert tz.utcoffset(None) == datetime.timedelta(0)

  def test_invalid_raises(self):
    with pytest.raises(ValueError):
      parse_timezone('invalid')

  def test_partial_offset_accepted(self):
    """strptime %z handles partial offsets correctly."""
    tz = parse_timezone('+05:30')
    assert tz.utcoffset(None) == datetime.timedelta(hours=5, minutes=30)
