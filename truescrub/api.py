#!/usr/bin/env python3
import re
import os
import sys
import json
import math
import logging
import datetime
import argparse
import operator
import itertools

import zmq
import flask
from flask import g, request

from . import db
from .matchmaking import (
    skill_group_ranges, compute_matches, make_player_skills,
    match_quality, team1_win_probability, estimated_skill_range)
from .models import Player
from .updater.recalculate import dump_rounds

app = flask.Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

SHARED_KEY = os.environ.get('TRUESCRUB_KEY', 'afohXaef9ighaeSh')
LOG_LEVEL = os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG')
UPDATER_HOST = os.environ.get('TRUESCRUB_UPDATER_HOST', '127.0.0.1')
UPDATER_PORT = os.environ.get('TRUESCRUB_UPDATER_PORT', 5555)
TIMEZONE_PATTERN = re.compile('([+-])(\d\d):00')


logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=LOG_LEVEL)
logger = logging.getLogger(__name__)
zmq_socket = zmq.Context().socket(zmq.PUSH)


def initialize():
    db.initialize_dbs()
    zmq_addr = 'tcp://{}:{}'.format(UPDATER_HOST, UPDATER_PORT)
    logger.info('Connecting ZeroMQ socket to {}'.format(zmq_addr))
    zmq_socket.connect(zmq_addr)


initialize()


def send_updater_message(**message):
    if 'command' not in message:
        raise ValueError('missing "command"')
    zmq_socket.send_json(message, flags=zmq.NOBLOCK)
    logger.debug('sent "%s" message', repr(message))


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
    return datetime.timezone(offset=datetime.timedelta(
            hours=offset_signum * int(offset)))


@app.route('/api/highlights/'
           '<int:year>-<int:month>-<int:day>T'
           '<int:hour>:<int:minute>:<int:second>'
           '<string:tz>', methods={'GET'})
def highlights(year, month, day, hour, minute, second, tz):
    try:
        timezone = parse_timezone(tz)
    except ValueError:
        return flask.make_response(
                'Invalid timezone {}{}'.format(plusminus, offset), 404)
    date = datetime.datetime(year, month, day, hour, minute, second,
                             tzinfo=timezone).astimezone(timezone.utc)
    try:
        return flask.jsonify(db.get_highlights(g.conn, date))
    except StopIteration:
        return flask.make_response(
                'No rounds on {}\n'.format(date.isoformat()), 404)


def make_player_viewmodel(player: Player):
    lower_bound, upper_bound = estimated_skill_range(player.skill)
    min_width = 0.1

    left_offset = min(lower_bound, 1 - min_width)
    right_offset = max(upper_bound, 0 + min_width)

    return {
        'player_id': player.player_id,
        'steam_name': player.steam_name,
        'skill': player.skill,
        'skill_group': player.skill_group,
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


def make_rating_component_viewmodel(components):
    return {
        'mvp_rating': '%d%%' % (100 * components['average_mvps']),
        'kill_rating': '%.2f' % components['average_kills'],
        'death_rating': '%.2f' % components['average_deaths'],
        'damage_rating': '%d' % components['average_damage'],
        'kas_rating': '%d%%' % (100 * components['average_kas']),
    }


@app.route('/profiles/<int:player_id>', methods={'GET'})
def profile(player_id):
    try:
        player, overall_record = db.get_player_profile(g.conn, player_id)
    except StopIteration:
        return flask.make_response('No such player', 404)

    overall_rating = make_rating_component_viewmodel(
        db.get_player_round_stat_averages(g.conn, player_id))
    season_ratings = [
        (season_id, make_rating_component_viewmodel(components))
        for season_id, components in db.get_player_round_stat_averages_by_season(
                g.conn, player_id).items()
    ]
    skills_by_season = db.get_player_skills_by_season(g.conn, player_id)

    player_viewmodel = make_player_viewmodel(player)
    team_records = db.get_team_records(g.conn, player_id)
    return flask.render_template('profile.html', player=player_viewmodel,
                                 overall_record=overall_record,
                                 overall_rating=overall_rating,
                                 season_ratings=season_ratings,
                                 skills_by_season=skills_by_season,
                                 team_records=team_records)


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


def matchmaking0(seasons: [int], selected_players: {int}, season_id: int = None,
                 latest: bool = False):
    if len(selected_players) > 10:
        return flask.make_response(
                'Cannot compute matches for more than 10 players', 403)

    players = db.get_all_players(g.conn) \
        if season_id is None \
        else db.get_season_players(g.conn, season_id)
    players.sort(key=operator.attrgetter('mmr'), reverse=True)

    teams = compute_matches([
        player for player in players if player.player_id in selected_players
    ]) if len(selected_players) > 0 else None

    return flask.render_template('matchmaking.html',
                                 seasons=seasons, selected_season=season_id,
                                 selected_players=selected_players,
                                 players=players, teams=teams, latest=latest)


@app.route('/profiles/<int:player_id>/matches', methods={'GET'})
def matches(player_id):
    all_players = db.get_all_players(g.conn)

    try:
        steam_name = next(player.steam_name
                          for player in all_players
                          if player.player_id == player_id)
    except StopIteration:
        return flask.make_response('No such player\n', 404)

    player_skills = make_player_skills(all_players)
    rounds_by_season = itertools.groupby(
            db.get_player_rounds(g.conn, player_skills, player_id),
            operator.itemgetter('season_id'))

    return flask.render_template(
            'matches.html', steam_name=steam_name,
            rounds_by_season=rounds_by_season)


@app.route('/profiles/<int:player_id>/team_records', methods={'GET'})
def team_records(player_id):
    try:
        player = db.get_player_profile(g.conn, player_id)[0]
    except StopIteration:
        return flask.make_response('No such player', 404)

    player_viewmodel = make_player_viewmodel(player)
    team_records = db.get_team_records(g.conn, player_id)
    return flask.render_template('team_records.html', player=player_viewmodel,
                                 team_records=team_records)


@app.route('/teams/<int:team_id>', methods={'GET'})
def team_details(team_id):
    members = db.get_team_members(g.conn, team_id)
    if len(members) == 0:
        return flask.make_response('No such team\n', 404)

    member_names = str.join(', ', [member.steam_name for member in members])
    opponent_records = db.get_opponent_records(g.conn, team_id)

    player_skills = make_player_skills(itertools.chain(
            members, *(record['opponent_team']
                       for record in opponent_records)))

    for record in opponent_records:
        record.update(
                quality=match_quality(
                        player_skills, members, record['opponent_team']),
                win_probability=team1_win_probability(
                        player_skills, members, record['opponent_team'])
        )

    rounds_won = 0
    rounds_lost = 0
    for record in opponent_records:
        rounds_won += record['rounds_won']
        rounds_lost += record['rounds_lost']

    return flask.render_template(
            'team_details.html',
            member_names=member_names, members=members,
            rounds_won=rounds_won, rounds_lost=rounds_lost,
            opponent_records=opponent_records)


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('-a', '--addr', metavar='HOST', default='0.0.0.0',
                        help='Bind to this address.')
arg_parser.add_argument('-p', '--port', metavar='PORT', type=int,
                        default=9000, help='Listen on this TCP port.')
arg_parser.add_argument('-c', '--recalculate', action='store_true',
                        help='Recalculate rankings.')
arg_parser.add_argument('-r', '--use-reloader', action='store_true',
                        help='Use code reloader.')
arg_parser.add_argument('-d', '--dump-rounds', action='store_true',
                        help='Print out round JSON.')
arg_parser.add_argument('-i', '--indent', action='store_true')


def print_rounds(indent: bool):
    with db.get_game_db() as game_db:
        dump_rounds(game_db, sys.stdout, indent)


def main():
    args = arg_parser.parse_args()
    if args.dump_rounds:
        return print_rounds(args.indent)
    if args.recalculate:
        return send_updater_message(command='recalculate')
    logger.info('TrueScrub listening on {}:{}'.format(args.addr, args.port))
    app.run(args.addr, args.port, app, use_reloader=args.use_reloader)
