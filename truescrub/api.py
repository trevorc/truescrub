#!/usr/bin/env python3
import json
import logging

import flask
from flask import request

from truescrub.envconfig import SHARED_KEY

app = flask.Flask('truescrub')
app.config['PROPAGATE_EXCEPTIONS'] = True

MAX_MATCHES = 50

logger = logging.getLogger(__name__)


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
