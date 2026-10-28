"""Explicit live-model stress scenarios using synthetic weather and wardrobes."""
import argparse
import asyncio

from .evaluate_personas import run
from .exploratory_dialogues import EXPECTATIONS, SCENARIOS, ExploratoryUpstream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--list", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", default="var/dialogue-audit/exploration.json")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    args.only = args.only or list(SCENARIOS)
    if not set(args.only) <= SCENARIOS.keys():
        parser.error("Unknown scenario")
    if not 1 <= args.concurrency <= 8:
        parser.error("concurrency must be between 1 and 8")
    if args.list:
        for name in args.only:
            print(f"{name}: {len(SCENARIOS[name])} turns x 2 personas")
        return 0
    return asyncio.run(run(args, scenarios=SCENARIOS, expectations=EXPECTATIONS, upstream_type=ExploratoryUpstream))


if __name__ == "__main__":
    raise SystemExit(main())
