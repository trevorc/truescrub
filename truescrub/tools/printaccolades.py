import argparse
import datetime
import sys

from truescrub.accolades import get_accolades
from truescrub.db import get_skill_db
from truescrub.highlights import get_highlights


def main():
  """Command-line interface for generating accolades."""

  parser = argparse.ArgumentParser(
    description="Generate accolades from player highlights")
  parser.add_argument("date", help="Date to analyze in ISO format (YYYY-MM-DD)")
  parser.add_argument("--json", "-j", action="store_true",
                      help="Output in JSON format")

  args = parser.parse_args()

  try:
    date = datetime.datetime.fromisoformat(args.date)
  except ValueError:
    print(
      f"Error: Invalid date format '{args.date}'. Use ISO format: YYYY-MM-DD",
      file=sys.stderr)
    sys.exit(1)

  try:
    with get_skill_db() as skill_db:
      highlights = get_highlights(skill_db, date)
      accolades = get_accolades(highlights['player_ratings'])

      if args.json:
        json.dump(accolades, sys.stdout, indent=2)
        print()
      else:
        for accolade in accolades:
          print(f"\n{accolade['accolade']}: {accolade['player_name']}")
        for detail in accolade['details']:
          print(f"  * {detail}")

  except StopIteration:
    print(f"No rounds found for {args.date}", file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
