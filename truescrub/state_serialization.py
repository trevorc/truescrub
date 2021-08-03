from google.protobuf.timestamp_pb2 import Timestamp

from truescrub.proto import game_state_pb2


class DeserializationError(RuntimeError):
  pass


def parse_map(map_json) -> game_state_pb2.Map:
  if map_json is None:
    return None
  try:
    return game_state_pb2.Map(name=map_json['name'])
  except KeyError as e:
    raise DeserializationError(e)


def parse_provider(provider_json) -> game_state_pb2.Provider:
  try:
    timestamp = Timestamp()
    timestamp.FromSeconds(provider_json['timestamp'])
    return game_state_pb2.Provider(
        app_id=int(provider_json['appid']),
        steam_id=int(provider_json['steamid']),
        timestamp=timestamp,
        version=int(provider_json['version']),
    )
  except (TypeError, KeyError) as e:
    raise DeserializationError(e)


def json_to_proto(gs_json: dict):
  map_ = parse_map(gs_json.get('map'))
  provider = parse_provider(gs_json.get('provider', {}))
  game_state_proto = game_state_pb2.GameState(map=map_, provider=provider)
  return game_state_proto
