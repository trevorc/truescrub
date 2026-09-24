from unittest.mock import MagicMock

import pytest

from proto import config_service_pb2
from truescrub import envconfig
from truescrub.rpc import ConfigServiceServicer


def test_get_brand_config(monkeypatch):
  monkeypatch.setattr(envconfig, "SITE_NAME", "TestScrub")

  servicer = ConfigServiceServicer()
  request = config_service_pb2.GetBrandConfigRequest()

  response = servicer.GetBrandConfig(request, None)
  assert response.site_name == "TestScrub"


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xv", __file__]))
