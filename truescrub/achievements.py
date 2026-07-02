from typing import List

from google.protobuf import json_format
from truescrub.db import execute_one
from truescrub.proto.profile_pb2 import AchievementConfiguration, Achievement


def load_achievements() -> List[Achievement]:
  with open('truescrub/proto/achievements.json', 'r') as f:
    return json_format.Parse(f.read(), AchievementConfiguration()).achievements


ACHIEVEMENTS = load_achievements()


def get_achievement_stats(skill_db, player_id):
  stats = {}

  row = execute_one(skill_db, '''
  SELECT COUNT(*)
       , COALESCE(SUM(kills), 0)
       , COALESCE(SUM(headshots), 0)
       , COALESCE(SUM(CASE WHEN kills >= 3 THEN 1 ELSE 0 END), 0)
       , COALESCE(SUM(CASE WHEN damage = 0 THEN 1 ELSE 0 END), 0)
  FROM round_stats
  WHERE player_id = ?
  ''', (player_id,))

  stats['rounds_played'] = row[0]
  stats['total_kills'] = row[1]
  stats['total_headshots'] = row[2]
  stats['multi_kill_rounds'] = row[3]
  stats['zero_damage_rounds'] = row[4]

  row = execute_one(skill_db, '''
  SELECT COALESCE(SUM(CASE WHEN r.mvp = ? THEN 1 ELSE 0 END), 0)
       , COUNT(DISTINCT r.season_id)
       , COALESCE(SUM(
           CASE WHEN rs.survived = 1
                 AND EXISTS (
                     SELECT 1 FROM team_membership tm
                     WHERE tm.player_id = rs.player_id
                       AND tm.team_id = r.loser
                 )
                THEN 1 ELSE 0 END
         ), 0)
  FROM round_stats rs
  JOIN rounds r
    ON rs.round_id = r.round_id
  WHERE rs.player_id = ?
  ''', (player_id, player_id))

  stats['total_mvps'] = row[0]
  stats['seasons_played'] = row[1]
  stats['survived_losses'] = row[2]

  row = execute_one(skill_db, '''
  SELECT COUNT(DISTINCT tm2.player_id) - 1
       , COUNT(DISTINCT r.map_id)
  FROM round_stats rs
  JOIN rounds r
    ON rs.round_id = r.round_id
  JOIN team_membership tm
    ON tm.player_id = rs.player_id
   AND tm.team_id IN (r.winner, r.loser)
  LEFT JOIN team_membership tm2
    ON tm2.team_id = tm.team_id
  WHERE rs.player_id = ?
  ''', (player_id,))

  stats['distinct_teammates'] = max(0, row[0])
  stats['distinct_maps'] = row[1]

  return stats


def compute_achievements(stats):
  results = []
  for achievement in ACHIEVEMENTS:
    current = stats.get(achievement.id, 0)
    highest_tier = None
    tiers = []
    for tier in achievement.tiers:
      earned = current >= tier.threshold
      if earned:
        highest_tier = tier.name
      tiers.append({
        'threshold': tier.threshold,
        'tier_name': tier.name,
        'earned': earned,
      })

    next_threshold = None
    for tier in tiers:
      if not tier['earned']:
        next_threshold = tier['threshold']
        break

    results.append({
      'id': achievement.id,
      'name': achievement.name,
      'tiers': tiers,
      'current': current,
      'highest_tier': highest_tier,
      'next_threshold': next_threshold,
    })
  return results


def get_achievements(skill_db, player_id):
  """Main entry point: fetch stats and compute achievements."""
  stats = get_achievement_stats(skill_db, player_id)
  return compute_achievements(stats)
