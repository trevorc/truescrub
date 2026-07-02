import os
import pathlib

DATA_DIR = pathlib.Path(os.environ.get('TRUESCRUB_DATA_DIR', 'data'))
LOG_LEVEL = os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG')
SHARED_KEY = os.environ.get('TRUESCRUB_KEY', 'afohXaef9ighaeSh')

SQLITE_TIMEOUT = float(os.environ.get('SQLITE_TIMEOUT', '30'))
SEASONS_TOML = pathlib.Path(
  os.environ.get('TRUESCRUB_SEASONS_TOML', DATA_DIR / 'seasons.toml'))
SEASONS = os.environ.get('TRUESCRUB_SEASONS')
SEGMENT_MAX_BYTES = int(
  os.environ.get('TRUESCRUB_SEGMENT_MAX_BYTES', str(16 * 1024 * 1024)))
