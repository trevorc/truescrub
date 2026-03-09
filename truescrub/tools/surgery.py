'''
Purge rounds that include game states involving a given player.
Supports both SQLite and Riegeli backends.
'''
import abc
import argparse
import logging
import pathlib
import sys
from typing import Tuple

from truescrub.db import execute
from truescrub.db import execute_one
from truescrub.envconfig import SEGMENT_MAX_BYTES
from truescrub.statewriter.game_state_log import GameStateLog

logger = logging.getLogger(__name__)


class ImpactedGameStateStats:
  def __init__(self):
    self.maps: set[str] = set()
    self.min_id = sys.maxsize
    self.max_id = 0
    self.rounds = 0
    self.game_states = 0


class SurgeryBackend(abc.ABC):
  @abc.abstractmethod
  def get_impacted_stats(self, player_id: int) -> ImpactedGameStateStats:
    """Gather stats about game states containing the given player."""

  @abc.abstractmethod
  def get_expanded_range(
      self, stats: ImpactedGameStateStats) -> Tuple[int, int]:
    """Expand a tentative range to whole-round boundaries."""

  @abc.abstractmethod
  def get_range_stats(
      self, start_id: int, end_id: int) -> ImpactedGameStateStats:
    """Gather stats for game states in [start_id, end_id]."""

  @abc.abstractmethod
  def execute(self, start_id: int, end_id: int):
    """Perform the actual deletion/exclusion."""


def purge_rounds_with_player(backend: SurgeryBackend, player_id: int):
  """Shared workflow: gather stats -> expand range -> confirm -> execute."""
  tentative = backend.get_impacted_stats(player_id)
  if tentative.game_states == 0:
    logger.info('No matching game states found; exiting')
    return

  logger.info('Found %d game states including %d rounds containing player %d',
              tentative.game_states, tentative.rounds, player_id)
  logger.info('Tentative maps: %s', ', '.join(tentative.maps))

  start_id, end_id = backend.get_expanded_range(tentative)
  final = backend.get_range_stats(start_id, end_id)

  print(f'Removing {final.game_states} game states '
        f'including {final.rounds} rounds')
  logger.info('Impacted maps: %s', ', '.join(map(str, final.maps)))

  confirmation = input(
    'Confirm by typing the number of game states: ')
  if confirmation != str(final.game_states):
    print('Aborting')
    return

  backend.execute(start_id, end_id)


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------

class SqliteBackend(SurgeryBackend):
  def __init__(self, game_db):
    self.game_db = game_db

  def get_impacted_stats(self, player_id: int) -> ImpactedGameStateStats:
    return _sqlite_stats(self.game_db,
                         f"json_type(game_state, '$.allplayers.{player_id}') IS NOT NULL")

  def get_expanded_range(
      self, stats: ImpactedGameStateStats) -> Tuple[int, int]:
    round_start_id, _ = execute_one(self.game_db, '''
                                                  SELECT game_state_id
                                                       , json_extract(game_state, '$.round.phase')
                                                  FROM game_state
                                                  WHERE game_state_id =
                                                        (SELECT MAX(g2.game_state_id)
                                                         FROM game_state g2
                                                         WHERE g2.game_state_id < ? AND
                                                               json_extract(
                                                                       g2.game_state,
                                                                       '$.previously.round.phase') =
                                                               'over');
                                                  ''', [stats.min_id])
    round_end_id, _ = execute_one(self.game_db, '''
                                                SELECT game_state_id
                                                     , json_extract(game_state, '$.round.phase')
                                                FROM game_state
                                                WHERE game_state_id =
                                                      (SELECT MIN(g2.game_state_id)
                                                       FROM game_state g2
                                                       WHERE g2.game_state_id > ? AND
                                                             json_extract(
                                                                     g2.game_state,
                                                                     '$.previously.round.phase') =
                                                             'over');
                                                ''', [stats.max_id])
    logger.info('Calculated range: %d - %d', round_start_id, round_end_id)
    return round_start_id, round_end_id

  def get_range_stats(
      self, start_id: int, end_id: int) -> ImpactedGameStateStats:
    return _sqlite_stats(self.game_db,
                         f'game_state_id BETWEEN {start_id} AND {end_id}')

  def execute(self, start_id: int, end_id: int):
    execute(self.game_db, '''
                          DELETE
                          FROM game_state
                          WHERE game_state_id BETWEEN ? AND ?
                          ''', (start_id, end_id))
    logger.debug('Deleted game states from %d to %d', start_id, end_id)


def _sqlite_stats(game_db, condition: str) -> ImpactedGameStateStats:
  stats = ImpactedGameStateStats()
  for game_state_id, map_name, round_phase, previous_phase \
      in execute(game_db, f'''
  SELECT game_state_id
     , json_extract(game_state, '$.map.name')
     , json_extract(game_state, '$.round.phase')
     , json_extract(game_state, '$.previously.round.phase')
  FROM game_state
  WHERE {condition}
  '''):
    stats.maps.add(map_name)
    if previous_phase == 'live' and round_phase == 'over':
      stats.rounds += 1
    stats.min_id = min(stats.min_id, game_state_id)
    stats.max_id = max(stats.max_id, game_state_id)
    stats.game_states += 1
  return stats


# ---------------------------------------------------------------------------
# Riegeli backend
# ---------------------------------------------------------------------------

class RiegeliBackend(SurgeryBackend):
  def __init__(self, source_path: pathlib.Path,
               output_path: pathlib.Path):
    self.source_log = GameStateLog(source_path, max_bytes=SEGMENT_MAX_BYTES)
    self.output_path = output_path
    self.output_log = GameStateLog(output_path, max_bytes=SEGMENT_MAX_BYTES)

  def get_impacted_stats(self, player_id: int) -> ImpactedGameStateStats:
    stats = ImpactedGameStateStats()
    with self.source_log.reader() as reader:
      for entry in reader:
        gs = entry.game_state
        if _player_in_gs(gs, player_id):
          if gs.HasField('map'):
            stats.maps.add(gs.map.name)
          if _is_round_end(gs):
            stats.rounds += 1
          stats.min_id = min(stats.min_id, entry.game_state_id)
          stats.max_id = max(stats.max_id, entry.game_state_id)
          stats.game_states += 1
    return stats

  def get_expanded_range(
      self, stats: ImpactedGameStateStats) -> Tuple[int, int]:
    round_start_id = stats.min_id
    round_end_id = stats.max_id

    with self.source_log.reader() as reader:
      prev_over_id = None
      for entry in reader:
        if entry.game_state_id >= stats.min_id:
          break
        if _is_round_end(entry.game_state):
          prev_over_id = entry.game_state_id

      if prev_over_id is not None:
        round_start_id = prev_over_id + 1

      for entry in reader.fetch_all(start_id=stats.max_id):
        round_end_id = entry.game_state_id
        if _is_round_end(entry.game_state):
          break

    logger.info('Tentative range: %d - %d', stats.min_id, stats.max_id)
    logger.info('Calculated range: %d - %d', round_start_id, round_end_id)
    return round_start_id, round_end_id

  def get_range_stats(
      self, start_id: int, end_id: int) -> ImpactedGameStateStats:
    stats = ImpactedGameStateStats()
    with self.source_log.reader() as reader:
      for entry in reader.fetch(start_id=start_id, end_id=end_id):
        gs = entry.game_state
        stats.game_states += 1
        if _is_round_end(gs):
          stats.rounds += 1
        if gs.HasField('map'):
          stats.maps.add(gs.map.name)
    return stats

  def execute(self, start_id: int, end_id: int):
    with self.output_log.writer() as writer, \
        self.source_log.reader() as reader:
      for entry in reader:
        if not start_id <= entry.game_state_id <= end_id:
          writer.append(entry)
    logger.info('Finished writing to %s, excluding states from %d to %d.',
                self.output_path, start_id, end_id)


def _is_round_end(gs) -> bool:
  """True if this game state is the final state of a completed round."""
  from truescrub.statewriter.state_parsing import ROUND_PHASES
  prev_phase = (gs.previously.round.phase
                if gs.HasField('previously') and
                   gs.previously.HasField('round') else 0)
  return (prev_phase == ROUND_PHASES['live']
          and gs.round.phase == ROUND_PHASES['over'])


def _player_in_gs(gs, player_id: int) -> bool:
  return any(p.steam_id == player_id for p in gs.allplayers)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def make_arg_parser():
  parser = argparse.ArgumentParser(
    description='Purge rounds containing a given player.')
  subparsers = parser.add_subparsers(dest='backend', required=True)

  sqlite_parser = subparsers.add_parser(
    'sqlite', help='Operate on a SQLite game state database')
  sqlite_parser.add_argument('steamid', type=int,
                             help='SteamID of the player to purge')

  riegeli_parser = subparsers.add_parser(
    'riegeli', help='Filter a Riegeli game state log directory')
  riegeli_parser.add_argument('source_log', type=pathlib.Path,
                              help='Source Riegeli log directory path')
  riegeli_parser.add_argument('output_log', type=pathlib.Path,
                              help='Output Riegeli log directory path')
  riegeli_parser.add_argument('--player_id', type=int, required=True,
                              help='SteamID of the player to filter by')

  return parser


def main():
  opts = make_arg_parser().parse_args()
  logging.basicConfig(
    format='%(asctime)s.%(msecs).3dZ\t%(name)s\t%(levelname)s\t%(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    level=logging.DEBUG,
  )

  if opts.backend == 'sqlite':
    from truescrub.db import get_game_db, get_skill_db, get_player_profile
    with get_game_db() as game_db, get_skill_db() as skill_db:
      try:
        player, overall_record = get_player_profile(skill_db, opts.steamid)
      except StopIteration:
        print('No such player found')
        return
      logger.info('Deleting rounds including player %s (record: %d-%d)',
                  player.steam_name, overall_record['rounds_won'],
                  overall_record['rounds_lost'])
      backend = SqliteBackend(game_db)
      purge_rounds_with_player(backend, opts.steamid)

  elif opts.backend == 'riegeli':
    if not opts.source_log.exists():
      logger.error('Source log directory not found: %s', opts.source_log)
      return
    if opts.output_log.exists():
      logger.warning(
        'Output log directory %s exists and files may be overwritten.',
        opts.output_log)
    backend = RiegeliBackend(opts.source_log, opts.output_log)
    purge_rounds_with_player(backend, opts.player_id)


if __name__ == '__main__':
  main()
