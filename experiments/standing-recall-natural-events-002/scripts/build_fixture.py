#!/usr/bin/env python3
from __future__ import annotations
import argparse
from natural_common import CASES_PATH, build_fixture, load_json, write_json

def main() -> int:
    p=argparse.ArgumentParser(description='Build frozen SRE-002 natural-event fixture')
    p.add_argument('--cases', default=str(CASES_PATH)); p.add_argument('--output', required=True)
    a=p.parse_args(); fixture=build_fixture(load_json(a.cases)); write_json(a.output, fixture)
    print(f"built {fixture['event_count']} natural events and {fixture['target_count']} scored targets")
    return 0
if __name__=='__main__': raise SystemExit(main())
