import operator
import os
import pathlib
import tomllib
import datetime
from typing import List, Tuple, Dict

SEASONS_TOML = pathlib.Path(
  os.environ.get('TRUESCRUB_DATA_DIR', 'data')
) / 'seasons.toml'


def get_seasons_by_start_date(seasons_file: pathlib.Path = None) -> \
    Dict[datetime.date, int]:
  if seasons_file is None:
    seasons_file = SEASONS_TOML

  with seasons_file.open('rb') as fp:
    seasons = tomllib.load(fp)
    return {
      start_date: idx + 1
      for idx, start_date in enumerate(seasons['season_starts'])
    }


def get_all_seasons() -> List[Tuple[int, datetime.date]]:
  return [
    (season_id, start_date)
    for start_date, season_id in sorted(
      get_seasons_by_start_date().items(),
      key=operator.itemgetter(1),
    )
  ]