import pytest

from proto import config_service_pb2
from truescrub import envconfig
from truescrub.rpc import ConfigServiceServicer


def get_brand_config():
  servicer = ConfigServiceServicer()
  request = config_service_pb2.GetBrandConfigRequest()
  return servicer.GetBrandConfig(request, None)


def test_get_brand_config(monkeypatch):
  monkeypatch.setattr(envconfig, "SITE_NAME", "TestScrub")
  monkeypatch.setattr(envconfig, "STYLESHEET", None)
  monkeypatch.setattr(envconfig, "TAGLINE", "Scrubbier than ever.")

  response = get_brand_config()
  assert response.site_name == "TestScrub"
  assert response.stylesheet == ''
  assert response.tagline == "Scrubbier than ever."


def test_stylesheet(monkeypatch, tmp_path):
  stylesheet = tmp_path.joinpath('brand.css')
  stylesheet.write_text(':root { --font-sans: serif; }\n')
  monkeypatch.setattr(envconfig, "STYLESHEET", str(stylesheet))

  response = get_brand_config()
  assert response.stylesheet == ':root { --font-sans: serif; }\n'


if __name__ == '__main__':
  raise SystemExit(pytest.main(["-xv", __file__]))
