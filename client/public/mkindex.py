import argparse
import json
import sys
from pathlib import Path
from typing import Any

def get_js_bundle(meta: dict[str, Any]) -> str:
  for out_path, info in meta.get("outputs", {}).items():
    if out_path.endswith(".js") and info.get("entryPoint"):
      return Path(out_path).name
  raise ValueError("Could not find JS entrypoint in metafile.")

def get_css_bundle(meta: dict[str, Any]) -> str:
  for out_path in meta.get("outputs", {}).keys():
    if out_path.endswith(".css"):
      return Path(out_path).name
  raise ValueError("Could not find css bundle in metadata")

def process_template(meta_json_path: Path, template_path: Path, output_path: Path) -> None:
  with meta_json_path.open("r", encoding="utf-8") as f:
    meta = json.load(f)

  js_bundle = get_js_bundle(meta)
  css_bundle = get_css_bundle(meta)

  with template_path.open("r", encoding="utf-8") as f:
    tmpl = f.read()

  if "{{JS_BUNDLE}}" not in tmpl:
    raise ValueError("Template does not contain the '{{JS_BUNDLE}}' placeholder")
  if "{{CSS_BUNDLE}}" not in tmpl:
    raise ValueError("Template does not contain the '{{CSS_BUNDLE}}' placeholder")

  tmpl = tmpl.replace("{{JS_BUNDLE}}", js_bundle)
  tmpl = tmpl.replace("{{CSS_BUNDLE}}", css_bundle)

  with output_path.open("w", encoding="utf-8") as f:
    f.write(tmpl)

parser = argparse.ArgumentParser(description="Generate index.html from template")
parser.add_argument("meta_json", type=Path, help="Path to the meta.json file")
parser.add_argument("template", type=Path, help="Path to the index.template.html file")
parser.add_argument("output", type=Path, help="Path to the output HTML file")

def main() -> None:
  args = parser.parse_args()
  try:
    process_template(args.meta_json, args.template, args.output)
  except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
  main()
