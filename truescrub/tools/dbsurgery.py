'''
Purge the rounds that include game states with the given steamid.
'''
import argparse
import logging
import sys
from typing import Set

from truescrub.models import Player
from truescrub.db import get_game_db, get_player_profile, execute, get_skill_db, \
  execute_one

logger = logging.getLogger(__name__)


class ImpactedGameStateStats:
  def __init__(self):
    self.maps: Set[str] = set()
    self.min_game_state = sys.maxsize
    self.max_game_state = 0
    self.rounds = 0
    self.game_states = 0


def get_impacted_game_state_stats(game_db, condition: str):
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
    stats.min_game_state = min(stats.min_game_state, game_state_id)
    stats.max_game_state = max(stats.max_game_state, game_state_id)
    stats.game_states += 1

  return stats


def get_impacted_game_state_range(
    game_db, tentative_stats: ImpactedGameStateStats):
  round_start_game_state, round_start_phase = execute_one(game_db, '''
  SELECT game_state_id
       , json_extract(game_state, '$.round.phase')
  FROM game_state
  WHERE game_state_id =
        ( SELECT MAX(g2.game_state_id)
          FROM game_state g2
          WHERE g2.game_state_id < ?
                  AND json_extract(g2.game_state,
                                   '$.previously.round.phase') = 'over'
        );
  ''', [tentative_stats.min_game_state])
  logger.info('Round start phase: %s', round_start_phase)
  round_end_game_state, round_end_phase = execute_one(game_db, '''
    SELECT game_state_id
         , json_extract(game_state, '$.round.phase')
    FROM game_state
    WHERE game_state_id =
          ( SELECT MIN(g2.game_state_id)
            FROM game_state g2
            WHERE g2.game_state_id > ?
                    AND json_extract(g2.game_state,
                                     '$.previously.round.phase') = 'over'
          );
    ''', [tentative_stats.max_game_state])
  logger.info('Round end phase: %s', round_end_phase)
  return round_start_game_state, round_end_game_state


def delete_game_states(game_db, final_stats, round_end_game_state,
                       round_start_game_state):
  execute(game_db, f'''
  DELETE FROM game_state
  WHERE game_state_id BETWEEN {round_start_game_state} AND {round_end_game_state}
  ''')
  logger.debug('%d game states and %d rounds deleted',
               final_stats.game_states, final_stats.rounds)


def purge_rounds_with_player(game_db, player: Player):
  tentative_stats = get_impacted_game_state_stats(game_db, f'''
  json_type(game_state, '$.allplayers.{player.player_id}') IS NOT NULL
  ''')
  logger.info('Found %d game states including %d rounds containing %r',
              tentative_stats.game_states, tentative_stats.rounds,
              player.steam_name)
  if tentative_stats.game_states == 0:
    logger.debug('No matching game states found; exiting')
    return
  logger.info('Tentative maps: %s', ', '.join(tentative_stats.maps))

  round_start_game_state, round_end_game_state = get_impacted_game_state_range(
    game_db, tentative_stats)
  final_stats = get_impacted_game_state_stats(game_db, f'''
  game_state_id BETWEEN {round_start_game_state} AND {round_end_game_state}
  ''')

  print(f'Deleting {final_stats.game_states} game states '
        f'including {final_stats.rounds} rounds')
  logger.info('Impacted maps: %s', ', '.join(map(str, final_stats.maps)))

  confirmation = input('Confirm deletion by typing the number of game states '
                       'that will be erased: ')
  if confirmation != str(final_stats.game_states):
    print('Aborting')
    return

  delete_game_states(game_db, final_stats, round_end_game_state,
                     round_start_game_state)


def make_arg_parser():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('steamid', type=int,
                          help='purge rounds containing this player')
  return arg_parser


def main():
  opts = make_arg_parser().parse_args()
  logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                             '%(name)s\t%(levelname)s\t%(message)s',
                      datefmt='%Y-%m-%dT%H:%M:%S',
                      level=logging.DEBUG)

  with get_game_db() as game_db, \
       get_skill_db() as skill_db:
    try:
      player, overall_record = get_player_profile(skill_db, opts.steamid)
    except StopIteration:
      print('No such player found')
      return
    logger.info('Deleting rounds including player %s (record: %d-%d)',
                player.steam_name, overall_record['rounds_won'],
                overall_record['rounds_lost'])
    purge_rounds_with_player(game_db, player)


if __name__ == '__main__':
  main()
