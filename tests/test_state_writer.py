import datetime
import json
import unittest
from unittest.mock import MagicMock

from tests.db_test_utils import TestDBManager, TestGameState
from truescrub import db
from truescrub.statewriter.state_writer import GameStateWriter


original_get_game_db = db.get_game_db

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
    game_state_data_1 = TestGameState(
      timestamp=datetime.datetime(2023, 1, 1, 12, 0, 0),
      map_name="de_dust2"
    ).to_json()
    game_state_data_2 = TestGameState(
      timestamp=datetime.datetime(2023, 1, 1, 12, 5, 0),
      map_name="de_inferno"
    ).to_json()

    messages = [
      {"game_state": json.dumps(game_state_data_1)},
      {"game_state": json.dumps(game_state_data_2)},
    ]

    self.writer.process_messages(messages)

    query = "SELECT COUNT(*) FROM game_state"
    [count] = self.execute_one(query)
    self.assertEqual(count, 2)

    results = list(self.execute(
      "SELECT game_state FROM game_state ORDER BY game_state_id"))
    self.assertEqual(json.loads(results[0][0]), game_state_data_1)
    self.assertEqual(json.loads(results[1][0]), game_state_data_2)

  def test_process_messages_sends_update_command(self):
    game_state_data = TestGameState(
      timestamp=datetime.datetime(2023, 1, 1, 12, 0, 0),
      map_name="de_dust2"
    ).to_json()
    messages = [{"game_state": json.dumps(game_state_data)}]

    self.writer.process_messages(messages)

    # Get the inserted game_state_id
    [max_id] = self.execute_one("SELECT MAX(game_state_id) FROM game_state")

    self.updater_mock.send_message.assert_called_once_with(
      command='process',
      game_state_id=max_id
    )

  def test_process_messages_empty_list(self):
    self.writer.process_messages([])
    self.updater_mock.send_message.assert_called_once_with(
      command='process',
      game_state_id=0
    )
    [count] = self.execute_one("SELECT COUNT(*) FROM game_state")
    self.assertEqual(count, 0)


if __name__ == '__main__':
  unittest.main()
