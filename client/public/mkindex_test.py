import json
import tempfile
import unittest
from pathlib import Path

from client.public.mkindex import get_js_bundle, process_template


class TestMkIndex(unittest.TestCase):
  def test_get_js_bundle_success(self) -> None:
    meta = {
      "outputs": {
        "dist/TrueScrubClient-A1B2.js": {"entryPoint": "TrueScrubClient.tsx"}
      }
    }
    self.assertEqual(get_js_bundle(meta), "TrueScrubClient-A1B2.js")

  def test_get_js_bundle_missing(self) -> None:
    meta = {"outputs": {"dist/TrueScrubClient.js": {}}}
    with self.assertRaisesRegex(ValueError, "Could not find JS entrypoint"):
      get_js_bundle(meta)

  def test_process_template_success(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      td_path = Path(td)
      meta_path = td_path / "meta.json"
      tmpl_path = td_path / "tmpl.html"
      out_path = td_path / "out.html"

      meta_path.write_text(
        json.dumps(
          {"outputs": {"dist/app-HASH.js": {"entryPoint": "app.tsx"}}}),
        encoding="utf-8"
      )
      tmpl_path.write_text(
        "<html><script src='/{{JS_BUNDLE}}'></script></html>",
        encoding="utf-8"
      )

      process_template(meta_path, tmpl_path, out_path)

      self.assertEqual(
        out_path.read_text(encoding="utf-8"),
        "<html><script src='/app-HASH.js'></script></html>"
      )

  def test_process_template_missing_placeholder(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      td_path = Path(td)
      meta_path = td_path / "meta.json"
      tmpl_path = td_path / "tmpl.html"
      out_path = td_path / "out.html"

      meta_path.write_text(
        json.dumps(
          {"outputs": {"dist/app-HASH.js": {"entryPoint": "app.tsx"}}}),
        encoding="utf-8"
      )
      tmpl_path.write_text("<html><body></body></html>", encoding="utf-8")

      with self.assertRaisesRegex(ValueError,
                                  "Template does not contain the '{{JS_BUNDLE}}' placeholder"):
        process_template(meta_path, tmpl_path, out_path)


if __name__ == '__main__':
  unittest.main()
