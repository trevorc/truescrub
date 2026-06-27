import requests
import sonora.client

from proto import highlights_service_pb2
from proto.highlights_service_pb2_grpc import HighlightsServiceStub


def test_grpc_web():
  channel = sonora.client.insecure_web_channel('http://localhost:9000')

  stub = HighlightsServiceStub(channel)

  req = highlights_service_pb2.GetDailyHighlightsRequest(
    date=highlights_service_pb2.Date(year=2021, month=5, day=23),
    timezone="-05:00",
    include_accolades=True
  )
  try:
    resp = stub.GetDailyHighlights(req)
    print("Response received!")
    print(f"Rounds played: {resp.rounds_played}")
    print(f"Accolades count: {len(resp.accolades)}")
  except Exception as e:
    print(f"Error: {e}")


if __name__ == '__main__':
  test_grpc_web()
