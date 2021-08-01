#!/usr/bin/env python3
import re
import os
import json
import math
import time
import logging
import datetime
import argparse
import operator
import itertools
from typing import List, Optional

import flask
from flask import g, request
from werkzeug.wsgi import SharedDataMiddleware
import waitress

from . import db
from .highlights import get_highlights
from .matchmaking import (
    skill_group_ranges, compute_matches,
    estimated_skill_range, MAX_PLAYERS_PER_TEAM)
from .models import Match, Player, skill_groups, skill_group_name
from .updater import updater


app = flask.Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

SHARED_KEY = os.environ.get('TRUESCRUB_KEY', 'afohXaef9ighaeSh')
LOG_LEVEL = os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG')
UPDATER_HOST = os.environ.get('TRUESCRUB_UPDATER_HOST', '127.0.0.1')
UPDATER_PORT = os.environ.get('TRUESCRUB_UPDATER_PORT', 5555)
TIMEZONE_PATTERN = re.compile(r'([+-])(\d\d):00')
MAX_MATCHES = 50

logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=LOG_LEVEL)
logger = logging.getLogger(__name__)


def initialize():
    db.initialize_dbs()



def send_updater_message(**message):
    if 'command' not in message:
        raise ValueError('missing "command"')
    updater.send_message(message)
    logger.debug('sent "%s" message', repr(message))


@app.before_request
def start_timer():
    g.start_time = time.time()


@app.after_request
def end_timer(response):
    response_time = '%.2fms' % (1000 * (time.time() - g.start_time))
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
    g.conn.close()


@app.route('/', methods={'GET'})
def index():
    seasons = len(db.get_season_range(g.conn))
    season_path = '/season/{}'.format(seasons) if seasons > 1 else ''
    return flask.render_template('index.html', season_path=season_path)


@app.route('/api/game_state', methods={'POST'})
def game_state():
    logger.debug('processing game state')
    state_json = request.get_json(force=True)
    if state_json.get('auth', {}).get('token') != SHARED_KEY:
        return flask.make_response('Invalid auth token\n', 403)
    del state_json['auth']
    state = json.dumps(state_json)
    with db.get_game_db() as game_db:
        game_state_id = db.insert_game_state(game_db, state)
        logger.debug('saved game_state with id %d', game_state_id)
        send_updater_message(command='process_game_state',
                             game_state_id=game_state_id)
        game_db.commit()
    return '<h1>OK</h1>\n'


def parse_timezone(tz: str) -> datetime.timezone:
    match = TIMEZONE_PATTERN.match(tz)
    if match is None:
        raise ValueError

    plusminus, offset = match.groups()
    offset_signum = 1 if plusminus == '+' else -1
    offset = datetime.timedelta(hours=offset_signum * int(offset))
    return datetime.timezone(offset=offset)


@app.route('/api/highlights/'
           '<int:year>-<int:month>-<int:day>T'
           '<int:hour>:<int:minute>:<int:second>'
           '<string:tz>', methods={'GET'})
def highlights(year, month, day, hour, minute, second, tz):
    try:
        timezone = parse_timezone(tz)
    except ValueError:
        return flask.make_response(
                'Invalid timezone {}'.format(tz), 404)
    date = datetime.datetime(year, month, day, hour, minute, second,
                             tzinfo=timezone).astimezone(timezone.utc)
    try:
        return flask.jsonify(get_highlights(g.conn, date))
    except StopIteration:
        return flask.make_response(
                'No rounds on {}\n'.format(date.isoformat()), 404)


def make_thin_player_viewmodel(player: Player) -> dict:
    return {
        'player_id': player.player_id,
        'steam_name': player.steam_name,
        'skill_group': skill_group_name(player.skill_group_index),
        'mmr': player.mmr,
    }


def make_match_viewmodel(match: Match) -> dict:
    return {
        'team1': [make_thin_player_viewmodel(player)
                  for player in match.team1],
        'team2': [make_thin_player_viewmodel(player)
                  for player in match.team2],
        'quality': match.quality,
        'team1_win_probability': match.team1_win_probability,
        'team2_win_probability': match.team2_win_probability,
    }


@app.route('/api/matchmaking/latest', methods={'GET'})
def latest_matchmaking_api():
    try:
        limit = int(request.args.get('limit', 1))
    except ValueError:
        return flask.make_response('Invalid limit\n', 400)
    seasons = db.get_season_range(g.conn)
    if len(seasons) == 0:
        return flask.make_response('No seasons found\n', 404)
    selected_players = db.get_players_in_last_round(g.conn)
    players, matches = compute_matchmaking(seasons[-1], selected_players)

    results = list(itertools.islice(map(make_match_viewmodel, matches), limit))
    return flask.jsonify(results)


@app.route('/api/leaderboard/season/<int:season>', methods={'GET'})
def leaderboard_api(season):
    players = [make_thin_player_viewmodel(player)
               for player in db.get_season_players(g.conn, season)]
    players.sort(key=operator.itemgetter('mmr'), reverse=True)
    return flask.jsonify({'players': players})


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
        'lower_bound': '%.1f' % (lower_bound * 100.0),
        'upper_bound': '%.1f' % (upper_bound * 100.0),
        'impact_rating': (
            '-'
            if player.impact_rating is None
            else '%.2f' % player.impact_rating)
    }


def make_skill_history_viewmodel(history: {str: Player}) -> {str: {str: float}}:
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
        return flask.make_response('Invalid timezone {}'.format(tz), 404)

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
        return flask.make_response('Invalid timezone {}'.format(tz), 404)

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


@app.route('/leaderboard', methods={'GET'})
def default_leaderboard():
    players = [make_player_viewmodel(player)
               for player in db.get_all_players(g.conn)]
    players.sort(key=operator.itemgetter('mmr'), reverse=True)
    seasons = db.get_season_range(g.conn)
    return flask.render_template('leaderboard.html', leaderboard=players,
                                 seasons=seasons, selected_season=None)


@app.route('/leaderboard/season/<int:season>', methods={'GET'})
def leaderboard(season):
    players = [make_player_viewmodel(player)
               for player in db.get_season_players(g.conn, season)]
    players.sort(key=operator.itemgetter('mmr'), reverse=True)
    seasons = db.get_season_range(g.conn)
    return flask.render_template('leaderboard.html', leaderboard=players,
                                 seasons=seasons, selected_season=season)


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
    return flask.render_template('skill_groups.html', skill_groups=groups)


def make_rating_component_viewmodel(components, impact_rating):
    return {
        'mvp_rating': '%d%%' % (100 * components['average_mvps']),
        'kill_rating': '%.2f' % components['average_kills'],
        'death_rating': '%.2f' % components['average_deaths'],
        'damage_rating': '%d' % components['average_damage'],
        'kas_rating': '%d%%' % (100 * components['average_kas']),
        'impact_rating': '%.2f' % impact_rating,
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
    return flask.render_template('profile.html',
                                 seasons=seasons,
                                 current_season=current_season,
                                 player=player_viewmodel,
                                 overall_record=overall_record,
                                 overall_rating=overall_rating,
                                 season_skills=season_skills,
                                 season_ratings=season_ratings,
                                 skill_groups=SKILL_GROUPS_VIEWMODEL)


@app.route('/matchmaking', methods={'GET'})
def default_matchmaking():
    return matchmaking(None)


@app.route('/matchmaking/latest', methods={'GET'})
def latest_matchmaking():
    seasons = db.get_season_range(g.conn)
    if len(seasons) == 0:
        return flask.make_response('No seasons found', 404)
    players = db.get_players_in_last_round(g.conn)
    return matchmaking0(seasons, players, season_id=seasons[-1], latest=True)


@app.route('/matchmaking/season/<int:season_id>', methods={'GET'})
def matchmaking(season_id):
    seasons = db.get_season_range(g.conn)
    selected_players = {
        int(player_id) for player_id in request.args.getlist('player')
    }
    return matchmaking0(seasons, selected_players, season_id)


def compute_matchmaking(season_id, selected_players) \
        -> ([Player], Optional[List[Match]]):
    max_players = MAX_PLAYERS_PER_TEAM * 2
    if len(selected_players) > max_players:
        raise ValueError('Cannot compute matches for more than '
                         '{} players'.format(max_players))
    players = db.get_all_players(g.conn) \
        if season_id is None \
        else db.get_season_players(g.conn, season_id)
    players.sort(key=operator.attrgetter('mmr'), reverse=True)

    if len(selected_players) > 0:
        matches = itertools.islice(compute_matches([
            player for player in players if player.player_id in selected_players
        ]), MAX_MATCHES)
    else:
        matches = None

    return players, matches


def matchmaking0(seasons: [int], selected_players: {int}, season_id: int = None,
                 latest: bool = False):
    try:
        players, matches = compute_matchmaking(season_id, selected_players)
    except ValueError as e:
        return flask.make_response(e.args[0], 403)

    return flask.render_template('matchmaking.html',
                                 seasons=seasons, selected_season=season_id,
                                 selected_players=selected_players,
                                 players=players, teams=matches, latest=latest)


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-a', '--addr', metavar='HOST', default='0.0.0.0',
                        help='Bind to this address.')
arg_parser.add_argument('-p', '--port', metavar='PORT', type=int,
                        default=9000, help='Listen on this TCP port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-s', '--serve-htdocs', action='store_true',
                        help='Serve static files.')


def main():
    args = arg_parser.parse_args()
    initialize()
    updater_thread = updater.UpdaterThread()
    updater_thread.start()

    if args.recalculate:
        send_updater_message(command='recalculate')
    else:
        logger.info('TrueScrub listening on {}:{}'.format(args.addr, args.port))
        if args.serve_htdocs:
            app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
                '/htdocs': ('truescrub', 'htdocs'),
            }, cache_timeout=3600 * 24 * 14)
        waitress.serve(app, host=args.addr, port=args.port)

    updater_thread.stop()
    logger.debug('joining updater')
    updater_thread.join()
