"""Stateless achievement system. Achievements are computed on-the-fly from
aggregate queries against the skill database. Every achievement is based on a
monotonically increasing counter, so achievements can never be lost."""

from truescrub.db import execute_one


ACHIEVEMENTS = [
    ('rounds_played', 'Rounds Played', 'rounds_played', [
        (10, 'Warm Body'),
        (100, 'Furniture'),
        (500, 'Veteran Scrub'),
    ]),
    ('total_kills', 'Total Kills', 'total_kills', [
        (50, 'First Blood'),
        (250, 'Serial Killer'),
        (1000, 'Chicken Slayer'),
    ]),
    ('total_mvps', 'Total MVPs', 'total_mvps', [
        (10, 'Shiny Star'),
        (50, 'Star Collector'),
    ]),
    ('total_headshots', 'Total Headshots', 'total_headshots', [
        (25, 'Lucky Shot'),
        (100, 'Actually Aiming'),
    ]),

    ('distinct_teammates', 'Distinct Teammates', 'distinct_teammates', [
        (5, 'Socialite'),
        (15, 'Knows Everyone'),
    ]),
    ('distinct_maps', 'Distinct Maps', 'distinct_maps', [
        (3, 'Tourist'),
        (5, 'World Traveler'),
    ]),
    ('multi_kill_rounds', 'Rounds with 3+ Kills', 'multi_kill_rounds', [
        (1, 'Hat Trick'),
        (10, 'Multi-Kill Machine'),
    ]),
    ('survived_losses', 'Survived Lost Rounds', 'survived_losses', [
        (5, 'Last One Standing'),
        (25, 'Sole Survivor'),
    ]),
    ('zero_damage_rounds', 'Rounds with 0 Damage', 'zero_damage_rounds', [
        (5, 'AFK Legend'),
        (25, 'Ghost'),
    ]),
    ('seasons_played', 'Seasons Played', 'seasons_played', [
        (2, 'Returning Customer'),
        (4, 'Lifer'),
    ]),
]


def get_achievement_stats(skill_db, player_id):
    stats = {}

    # Query 1: Core stats from round_stats only
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

    # Query 2: Round-level joins (MVPs, seasons, survived-losses).
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

    # Query 3: Distinct counts (teammates, maps)
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
    """Compare raw counters against thresholds and return achievement status.

    Returns a list of dicts, one per achievement category:
      {
        'id': str,
        'name': str,        # category name
        'tiers': [
          {'threshold': int, 'tier_name': str, 'earned': bool},
          ...
        ],
        'current': int,      # current counter value
        'highest_tier': str or None,  # name of highest earned tier
      }
    """
    results = []
    for achievement_id, name, stat_key, thresholds in ACHIEVEMENTS:
        current = stats.get(stat_key, 0)
        highest_tier = None
        tiers = []
        for threshold, tier_name in thresholds:
            earned = current >= threshold
            if earned:
                highest_tier = tier_name
            tiers.append({
                'threshold': threshold,
                'tier_name': tier_name,
                'earned': earned,
            })

        # Find the next unearned threshold for progress display
        next_threshold = None
        for tier in tiers:
            if not tier['earned']:
                next_threshold = tier['threshold']
                break

        results.append({
            'id': achievement_id,
            'name': name,
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
