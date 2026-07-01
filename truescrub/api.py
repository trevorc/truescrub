#!/usr/bin/env python3
import datetime
import json
import logging
import math
import re
import time
from typing import Dict

import flask
from flask import g, request, render_template

from truescrub import achievements
from truescrub import db
from truescrub.envconfig import TRUESCRUB_BRAND, SHARED_KEY
from truescrub.matchmaking import (
  skill_group_ranges, estimated_skill_range)
from truescrub.models import Player, skill_groups, skill_group_name

app = flask.Flask('truescrub')
app.config['PROPAGATE_EXCEPTIONS'] = True

TIMEZONE_PATTERN = re.compile(r'([+-])(\d\d):(\d\d)$')
MAX_MATCHES = 50

logger = logging.getLogger(__name__)


@app.before_request
def start_timer():
  g.start_time = time.time()


@app.after_request
def end_timer(response):
  response_time = f'{1000 * (time.time() - g.start_time):.2f}ms'
  response.headers['X-Processing-Time'] = response_time
  return response


@app.before_request
def db_connect():
  g.conn = db.get_skill_db()


@app.after_request
def db_commit(response):
  g.conn.commit()
  return response


@app.teardown_request
def db_close(exc):
  if hasattr(g, 'conn'):
    g.conn.close()





@app.route('/api/game_state', methods={'POST'})
def game_state():
  logger.debug('accepting game state')
  state_json = request.get_json(force=True)
  if state_json.get('auth', {}).get('token') != SHARED_KEY:
    return flask.make_response('Invalid auth token\n', 403)
  del state_json['auth']
  state = json.dumps(state_json)
  app.state_writer.send_message(game_state=state)
  return '<h1>OK</h1>\n'


def parse_timezone(tz: str) -> datetime.timezone:
  match = TIMEZONE_PATTERN.match(tz)
  if match is None:
    raise ValueError(f"Invalid timezone {tz}")

  plusminus, hours, minutes = match.groups()
  offset_signum = 1 if plusminus == '+' else -1
  offset = datetime.timedelta(
    hours=offset_signum * int(hours),
    minutes=offset_signum * int(minutes)
  )
  return datetime.timezone(offset=offset)



def make_player_viewmodel(player: Player):
  lower_bound, upper_bound = estimated_skill_range(player.skill)
  min_width = 0.1

  left_offset = min(lower_bound, 1 - min_width)
  right_offset = max(upper_bound, 0 + min_width)

  return {
    'player_id': player.player_id,
    'steam_name': player.steam_name,
    'skill': player.skill,
    'skill_group': skill_group_name(player.skill_group_index),
    'special_skill_group': skill_group_name(player.skill_group_index, True),
    'mmr': player.mmr,
    'rating_offset': left_offset,
    'rating_width': right_offset - left_offset,
    'lower_bound': f'{lower_bound * 100.0:.1f}',
    'upper_bound': f'{upper_bound * 100.0:.1f}',
    'impact_rating': (
      '-'
      if player.impact_rating is None
      else f'{player.impact_rating:.2f}')
  }


def make_skill_history_viewmodel(
    history: Dict[str, Player]) -> Dict[str, Dict[str, float]]:
  return {
    skill_date: {
      'skill_mean': player.skill.mu,
      'skill_stdev': player.skill.sigma,
    }
    for skill_date, player
    in history.items()
  }


@app.route('/api/profiles/<int:player_id>/skill_history', methods={'GET'})
def overall_skill_history(player_id):
  tz = request.args.get('tz', '+00:00')
  try:
    timezone = parse_timezone(tz)
  except ValueError:
    return flask.make_response(f'Invalid timezone {tz}', 404)

  skill_history = make_skill_history_viewmodel(
    db.get_overall_skill_history(g.conn, player_id, timezone))
  rating_history = db.get_impact_ratings_by_day(g.conn, player_id, timezone)

  return flask.jsonify({
    'player_id': player_id,
    'skill_history': skill_history,
    'rating_history': rating_history,
  })


@app.route('/api/profiles/<int:player_id>/skill_history/season/<int:season>',
           methods={'GET'})
def player_skill_history(player_id, season):
  tz = request.args.get('tz', '+00:00')
  try:
    timezone = parse_timezone(tz)
  except ValueError:
    return flask.make_response(f'Invalid timezone {tz}', 404)

  skill_history = make_skill_history_viewmodel(
    db.get_season_skill_history(g.conn, season, player_id, timezone))
  rating_history = db.get_impact_ratings_by_day(
    g.conn, player_id, timezone, season)

  return flask.jsonify({
    'player_id': player_id,
    'season': season,
    'skill_history': skill_history,
    'rating_history': rating_history,
  })



def format_bound(bound):
  if math.isfinite(bound):
    return int(bound)
  if bound < 0:
    return '-∞'
  return '∞'


@app.route('/skill_groups', methods={'GET'})
def all_skill_groups():
  groups = [{
    'name': skill_group,
    'lower_bound': format_bound(lower_bound),
    'upper_bound': format_bound(upper_bound),
  } for skill_group, lower_bound, upper_bound in skill_group_ranges()]
  return render_template('skill_groups.html', brand=TRUESCRUB_BRAND,
                         skill_groups=groups)


def make_rating_component_viewmodel(components, impact_rating):
  return {
    'mvp_rating': f'{100 * components["average_mvps"]:.0f}%',
    'kill_rating': f'{components["average_kills"]:.2f}',
    'death_rating': f'{components["average_deaths"]:.2f}',
    'damage_rating': f'{components["average_damage"]:.0f}',
    'kas_rating': f'{100 * components["average_kas"]:.0f}%',
    'impact_rating': f'{impact_rating:.2f}',
  }


SKILL_GROUPS_VIEWMODEL = [
  [cutoff if math.isfinite(cutoff) else None, skill_group] for
  cutoff, skill_group in skill_groups()
]


@app.route('/profiles/<int:player_id>', methods={'GET'})
def profile(player_id):
  seasons = db.get_season_range(g.conn)
  current_season = len(seasons)

  try:
    player, overall_record = db.get_player_profile(g.conn, player_id)
  except StopIteration:
    return flask.make_response('No such player', 404)

  skills_by_season = db.get_player_skills_by_season(g.conn, player_id)
  season_skills = [
    (season_id, make_player_viewmodel(season_skill))
    for season_id, season_skill in skills_by_season.items()
  ]
  season_skills.sort(reverse=True)

  # TODO: show percentiles of rating, DPR, KAS, ADR, MVP, KPR

  overall_rating = make_rating_component_viewmodel(
    db.get_player_round_stat_averages(g.conn, player_id),
    player.impact_rating)
  season_ratings = [
    (season_id, make_rating_component_viewmodel(
      components, skills_by_season[season_id].impact_rating))
    for season_id, components
    in db.get_player_round_stat_averages_by_season(g.conn, player_id).items()
  ]
  season_ratings.sort(reverse=True)
  player_viewmodel = make_player_viewmodel(player)

  player_achievements = achievements.get_achievements(g.conn, player_id)

  return render_template('profile.html',
                         brand=TRUESCRUB_BRAND,
                         seasons=seasons,
                         current_season=current_season,
                         player=player_viewmodel,
                         overall_record=overall_record,
                         overall_rating=overall_rating,
                         season_skills=season_skills,
                         season_ratings=season_ratings,
                         skill_groups=SKILL_GROUPS_VIEWMODEL,
                         achievements=player_achievements)
