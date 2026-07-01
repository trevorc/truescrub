import argparse
import json
import sys
from pathlib import Path
from typing import Any


def get_js_bundle(meta: dict[str, Any]) -> str:
  outputs: dict[str, Any] = meta.get("outputs", {})

  for out_path, info in outputs.items():
    if out_path.endswith(".js") and info.get("entryPoint"):
      return Path(out_path).name

  raise ValueError("Could not find JS entrypoint in metafile.")


def process_template(meta_json_path: Path, template_path: Path,
                     output_path: Path) -> None:
  with meta_json_path.open("r", encoding="utf-8") as f:
    meta: dict[str, Any] = json.load(f)

  js_bundle = get_js_bundle(meta)
  placeholder = "{{JS_BUNDLE}}"
  found = False

  with (
    template_path.open("r", encoding="utf-8") as fin,
    output_path.open("w", encoding="utf-8") as fout
  ):
    for line in fin:
      if placeholder in line:
        line = line.replace(placeholder, js_bundle)
        found = True
      fout.write(line)

  if not found:
    raise ValueError(
      f"Template does not contain the '{placeholder}' placeholder.")


parser = argparse.ArgumentParser(
  description="Injects a JS bundle name from a meta.json into an HTML template."
)
parser.add_argument("meta_json", type=Path, help="Path to the meta.json file")
parser.add_argument("template", type=Path,
                    help="Path to the index.template.html file")
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
