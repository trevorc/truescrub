#!/usr/bin/env python3

import os
import json
import math
import logging
import argparse
import operator
import itertools

import zmq
import flask
from flask import g, request

from . import db
from .matchmaking import (
    skill_group_ranges, compute_matches, make_player_skills,
    match_quality, team1_win_probability)

app = flask.Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

SHARED_KEY = os.environ.get('TRUESCRUB_KEY', 'afohXaef9ighaeSh')

logging.basicConfig(format='%(asctime)s.%(msecs).3dZ\t'
                           '%(levelname)s\t%(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    level=os.environ.get('TRUESCRUB_LOG_LEVEL', 'DEBUG'))
logger = logging.getLogger(__name__)
zmq_socket = zmq.Context().socket(zmq.PUSH)


def send_updater_message(**message):
    if 'command' not in message:
        raise ValueError('missing "command"')
    try:
        result = zmq_socket.send_json(message, flags=zmq.NOBLOCK)
        logger.debug('send "%s" message. result: %s',
                     message['command'], result)
    except zmq.Again:
        pass


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
    seasons = len(db.get_season_count(g.conn))
    season_path = '/season/{}'.format(seasons) if seasons > 1 else ''
    return flask.render_template('index.html', season_path=season_path)


@app.route('/api/game_state', methods={'POST'})
def game_state():
    state_json = request.get_json(force=True)
    if state_json.get('auth', {}).get('token') != SHARED_KEY:
        return flask.make_response('Invalid auth token\n', 403)
    del state_json['auth']
    state = json.dumps(state_json)
    with db.get_game_db() as game_db:
        game_state_id = db.insert_game_state(game_db, state)
        send_updater_message(command='process_game_state',
                             game_state_id=game_state_id)
    return '<h1>OK</h1>\n'


@app.route('/leaderboard', methods={'GET'})
def default_leaderboard():
    players = db.get_all_players(g.conn)
    seasons = db.get_season_count(g.conn)
    return flask.render_template('leaderboard.html', leaderboard=players,
                                 seasons=seasons, selected_season=None)


@app.route('/leaderboard/season/<int:season>', methods={'GET'})
def leaderboard(season):
    players = db.get_season_players(g.conn, season)
    seasons = db.get_season_count(g.conn)
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


@app.route('/profiles/<int:player_id>', methods={'GET'})
def profile(player_id):
    try:
        player_profile = db.get_player_profile(g.conn, player_id)
    except StopIteration:
        return flask.make_response('No such player', 404)

    team_records = db.get_team_records(g.conn, player_id)
    return flask.render_template('profile.html', profile=player_profile,
                                 team_records=team_records)


@app.route('/matchmaking', methods={'GET'})
def default_matchmaking():
    return matchmaking(None)


@app.route('/matchmaking/season/<int:season_id>', methods={'GET'})
def matchmaking(season_id):
    seasons = db.get_season_count(g.conn)
    selected_players = {
        int(player_id) for player_id in request.args.getlist('player')
    }
    if len(selected_players) > 10:
        return flask.make_response(
                'Cannot compute matches for more than 10 players', 403)

    players = db.get_all_players(g.conn) \
        if season_id is None \
        else db.get_season_players(g.conn, season_id)

    for player in players:
        player['selected'] = player['player_id'] in selected_players

    teams = compute_matches([
        player for player in players if player['selected']
    ]) if len(selected_players) > 0 else None

    return flask.render_template('matchmaking.html',
                                 seasons=seasons, selected_season=season_id,
                                 players=players, teams=teams)


@app.route('/profiles/<int:player_id>/matches', methods={'GET'})
def matches(player_id):
    all_players = db.get_all_players(g.conn)

    try:
        steam_name = next(player['steam_name']
                          for player in all_players
                          if player['player_id'] == player_id)
    except StopIteration:
        return flask.make_response('No such player\n', 404)

    player_skills = make_player_skills(all_players)
    rounds_by_season = itertools.groupby(
            db.get_player_rounds(g.conn, player_skills, player_id),
            operator.itemgetter('season_id'))

    return flask.render_template(
            'matches.html', steam_name=steam_name,
            rounds_by_season=rounds_by_season)


@app.route('/teams/<int:team_id>', methods={'GET'})
def team_details(team_id):
    members = db.get_team_members(g.conn, team_id)
    if len(members) == 0:
        return flask.make_response('No such team\n', 404)

    member_names = str.join(', ', [member['steam_name'] for member in members])
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
arg_parser.add_argument('-y', '--zmq-addr', metavar='HOST',
                        default=os.environ.get(
                                'TRUESCRUB_UPDATER_HOST', '127.0.0.1'),
                        help='Connect to zeromq on this address.')
arg_parser.add_argument('-z', '--zmq-port', type=int,
                        default=5555, help='Connect to zeromq on this port.')

db.initialize_dbs()


def main():
    args = arg_parser.parse_args()
    zmq_addr = 'tcp://{}:{}'.format(args.zmq_addr, args.zmq_port)
    logger.info('Connecting ZeroMQ socket to {}'.format(zmq_addr))
    zmq_socket.connect(zmq_addr)
    if args.recalculate:
        return send_updater_message(command='recalculate')
    logger.info('TrueScrub listening on {}:{}'.format(args.addr, args.port))
    app.run(args.addr, args.port, app, use_reloader=args.use_reloader)
