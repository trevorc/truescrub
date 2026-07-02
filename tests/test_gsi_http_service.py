import json
import threading
import time
import urllib.request
import urllib.error
from unittest.mock import MagicMock

import pytest

from truescrub.application import GsiHttpService

@pytest.fixture
def mock_state_writer():
    return MagicMock()

@pytest.fixture
def gsi_server(mock_state_writer):
    service = GsiHttpService(mock_state_writer, 'test_secret_key', '127.0.0.1', 0)
    server_thread = threading.Thread(target=service.server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Allow time for server to start
    time.sleep(0.1)
    
    yield service
    
    service.stop()
    server_thread.join(timeout=1.0)

def test_rejects_missing_auth(gsi_server):
    port = gsi_server.server.server_port
    req = urllib.request.Request(f'http://127.0.0.1:{port}/api/game_state',
                                 data=json.dumps({'map': {'name': 'de_dust2'}}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req)
    assert excinfo.value.code == 403

def test_rejects_wrong_token(gsi_server):
    port = gsi_server.server.server_port
    req = urllib.request.Request(f'http://127.0.0.1:{port}/api/game_state',
                                 data=json.dumps({
                                     'auth': {'token': 'wrong_key'},
                                     'map': {'name': 'de_dust2'},
                                 }).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req)
    assert excinfo.value.code == 403

def test_accepts_valid_token(gsi_server, mock_state_writer):
    port = gsi_server.server.server_port
    req = urllib.request.Request(f'http://127.0.0.1:{port}/api/game_state',
                                 data=json.dumps({
                                     'auth': {'token': 'test_secret_key'},
                                     'map': {'name': 'de_dust2'},
                                 }).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
    response = urllib.request.urlopen(req)
    assert response.getcode() == 200
    
    # Verify the state writer received the json without the auth token
    mock_state_writer.send_message.assert_called_once_with(
        game_state=json.dumps({'map': {'name': 'de_dust2'}})
    )
