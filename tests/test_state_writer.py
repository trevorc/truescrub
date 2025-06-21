import datetime
import json
import unittest
from unittest.mock import MagicMock

import pytest

from tests.db_test_utils import TestDBManager, TestGameState
from truescrub import db
from truescrub.statewriter.state_writer import GameStateWriter, \
  RiegeliGameStateWriter

original_get_game_db = db.get_game_db

GAME_STATE_DATA_1 = TestGameState(
  timestamp=datetime.datetime(2023, 1, 1, 12, 0, 0),
  map_name="de_dust2"
)
GAME_STATE_DATA_2 = TestGameState(
  timestamp=datetime.datetime(2023, 1, 1, 12, 5, 0),
  map_name="de_inferno"
)


class TestGameStateWriter(unittest.TestCase):
  def setUp(self):
    self.db_manager = TestDBManager()
    self.updater_mock = MagicMock()
    self.writer = GameStateWriter(self.updater_mock)
    db.get_game_db = MagicMock(return_value=self.db_manager.game_db)

  def tearDown(self):
    db.get_game_db = original_get_game_db
    self.db_manager.close()

  def execute_one(self, query):
    return db.execute_one(self.db_manager.game_db, query)

  def execute(self, query):
    return db.execute(self.db_manager.game_db, query)

  def test_process_messages_inserts_game_states(self):
    game_state_data_1 = GAME_STATE_DATA_1.to_json()
    game_state_data_2 = GAME_STATE_DATA_2.to_json()

    messages = [
      {"game_state": json.dumps(game_state_data_1)},
      {"game_state": json.dumps(game_state_data_2)},
    ]

    self.writer.process_messages(messages)

    [count] = self.execute_one("SELECT COUNT(*) FROM game_state")
    self.assertEqual(count, 2)

    results = list(self.execute(
      "SELECT game_state FROM game_state ORDER BY game_state_id"))
    self.assertEqual(json.loads(results[0][0]), game_state_data_1)
    self.assertEqual(json.loads(results[1][0]), game_state_data_2)


class TestRiegeliGameStateWriter(unittest.TestCase):
  def setUp(self):
    self.log_mock = MagicMock()
    self.updater_mock = MagicMock()
    self.writer = RiegeliGameStateWriter(self.log_mock, self.updater_mock)

  def test_process_messages_writes_to_log_and_sends_update(self):
    game_state_data_1 = GAME_STATE_DATA_1.to_json()
    game_state_data_2 = GAME_STATE_DATA_2.to_json()

    messages = [
      {"game_state": json.dumps(game_state_data_1)},
      {"game_state": json.dumps(game_state_data_2)},
    ]

    mock_writer = MagicMock()
    self.log_mock.writer.return_value.__enter__.return_value = mock_writer
    self.writer.process_messages(messages)

    self.assertEqual(mock_writer.append.call_count, 2)
    self.assertEqual(mock_writer.flush.call_count, 1)

    written_game_states = [call_args[0][0].game_state for call_args in
                           mock_writer.append.call_args_list]

    self.assertEqual(written_game_states[0].map.name,
                     game_state_data_1['map']['name'])
    self.assertEqual(written_game_states[1].map.name,
                     game_state_data_2['map']['name'])

    mock_writer.flush.assert_called_once()

    self.updater_mock.send_message.assert_called_once_with(
      command='process',
      game_state_id=2
    )

  def test_process_no_messages(self):
    self.writer.max_id = 10
    self.writer.process_messages([])
    self.updater_mock.send_message.assert_called_once_with(
      command='process',
      game_state_id=10
    )
    self.log_mock.writer.assert_called_once()
    mock_writer = self.log_mock.writer.return_value.__enter__.return_value
    mock_writer.write_message.assert_not_called()
    mock_writer.flush.assert_called_once()

  def test_process_messages_sends_update_command(self):
    game_state_data = GAME_STATE_DATA_1.to_json()
    messages = [{"game_state": json.dumps(game_state_data)}]

    self.writer.process_messages(messages)

    self.updater_mock.send_message.assert_called_once_with(
      command='process',
      game_state_id=1
    )


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xv", __file__]))