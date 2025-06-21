import os
import pathlib

DATA_DIR = pathlib.Path(os.environ.get('TRUESCRUB_DATA_DIR', 'data'))
LOG_LEVEL = os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG')
SHARED_KEY = os.environ.get('TRUESCRUB_KEY', 'afohXaef9ighaeSh')
TRUESCRUB_BRAND = os.environ.get('TRUESCRUB_BRAND', 'TrueScrub™')
SQLITE_TIMEOUT = float(os.environ.get('SQLITE_TIMEOUT', '30'))
SEASONS_TOML = pathlib.Path(
  os.environ.get('TRUESCRUB_SEASONS_TOML', DATA_DIR / 'seasons.toml'))
