import datetime
import json
import operator
import tomllib
from typing import List, Tuple, Dict

from truescrub.envconfig import SEASONS_TOML, SEASONS


def get_seasons_by_start_date() -> Dict[datetime.date, int]:
  if SEASONS is None:
    with SEASONS_TOML.open('rb') as fp:
      season_starts = tomllib.load(fp)['season_starts']
  else:
    season_starts = [
      datetime.date.fromisoformat(d)
      for d in json.loads(SEASONS)['season_starts']
    ]

  return {
    start_date: idx + 1
    for idx, start_date in enumerate(season_starts)
  }


def get_all_seasons() -> List[Tuple[int, datetime.date]]:
  return [
    (season_id, start_date)
    for start_date, season_id in sorted(
      get_seasons_by_start_date().items(),
      key=operator.itemgetter(1),
    )
  ]
