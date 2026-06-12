import datetime
import pathlib
import pytest

from truescrub import seasoncfg

def test_get_seasons_by_start_date_toml(monkeypatch):
    monkeypatch.setattr(seasoncfg, 'SEASONS_TOML', pathlib.Path('tests/sample_seasons.toml'))
    seasons = seasoncfg.get_seasons_by_start_date()
    assert seasons == {
        datetime.date(2022, 1, 1): 1,
        datetime.date(2022, 2, 1): 2,
    }

def test_get_seasons_by_start_date_json(monkeypatch):
    monkeypatch.setattr(seasoncfg, 'SEASONS', '{"season_starts": ["2025-01-01", "2025-02-01"]}')
    seasons = seasoncfg.get_seasons_by_start_date()
    assert seasons == {
        datetime.date(2025, 1, 1): 1,
        datetime.date(2025, 2, 1): 2,
    }


if __name__ == '__main__':
  raise SystemExit(pytest.main(['-xvs', __file__]))
