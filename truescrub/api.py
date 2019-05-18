#!/usr/bin/env python3

import os
import json
import math
import argparse
import itertools

import flask
from flask import g, request

from . import db
from .recalculate import recalculate
from .matchmaking import (
    skill_group_ranges, compute_matches, make_player_skills,
    match_quality, team1_win_probability)

app = flask.Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

SHARED_KEY = os.environ.get('TRUESCRUB_KEY', 'afohXaef9ighaeSh')


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
    return flask.render_template('index.html')


@app.route('/api/game_state', methods={'POST'})
def game_state():
    state_json = request.get_json(force=True)
    if state_json.get('auth', {}).get('token') != SHARED_KEY:
        return flask.make_response('Invalid auth token\n', 403)
    del state_json['auth']
    state = json.dumps(state_json)
    db.insert_game_state(state)
    return '<h1>OK</h1>\n'


@app.route('/leaderboard', methods={'GET'})
def leaderboard():
    players = list(db.get_all_players())
    return flask.render_template('leaderboard.html', leaderboard=players)


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
        player_profile = db.get_player_profile(player_id)
    except StopIteration:
        return flask.make_response('No such player', 404)

    team_records = list(db.get_team_records(player_id))
    return flask.render_template('profile.html', profile=player_profile,
                                 team_records=team_records)


@app.route('/matchmaking', methods={'GET'})
def matchmaking():
    selected_players = {
        int(player_id) for player_id in request.args.getlist('player')
    }
    if len(selected_players) > 10:
        return flask.make_response(
                'Cannot compute matches for more than 10 players', 403)

    players = list(db.get_all_players())
    for player in players:
        player['selected'] = player['player_id'] in selected_players

    teams = compute_matches([
        player for player in players if player['selected']
    ]) if len(selected_players) > 0 else None

    return flask.render_template('matchmaking.html',
                                 players=players, teams=teams)


@app.route('/profiles/<int:player_id>/matches', methods={'GET'})
def matches(player_id):
    all_players = list(db.get_all_players())

    try:
        steam_name = next(player['steam_name']
                          for player in all_players
                          if player['player_id'] == player_id)
    except StopIteration:
        return flask.make_response('No such player\n', 404)

    player_skills = make_player_skills(all_players)
    rounds = db.get_player_rounds(player_skills, player_id)

    return flask.render_template(
            'matches.html', steam_name=steam_name, rounds=rounds)


@app.route('/teams/<int:team_id>', methods={'GET'})
def team_details(team_id):
    members = db.get_team_members(team_id)
    if len(members) == 0:
        return flask.make_response('No such team\n', 404)

    member_names = str.join(', ', [member['steam_name'] for member in members])
    opponent_records = list(db.get_opponent_records(team_id))

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


def main():
    args = arg_parser.parse_args()
    if args.recalculate:
        return recalculate()
    app.run(args.addr, args.port, app, use_reloader=args.use_reloader)


db.initialize_dbs()

if __name__ == '__main__':
    main()
