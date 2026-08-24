#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from natural_common import PROMOTION_PATH, grade_natural, load_json, run_benchmark, write_json

def main() -> int:
    p=argparse.ArgumentParser(description='Run frozen SRE-002 natural-event benchmark')
    p.add_argument('--fixture', required=True); p.add_argument('--score', required=True); p.add_argument('--verdict', required=True)
    p.add_argument('--promotion-policy', default=str(PROMOTION_PATH)); a=p.parse_args()
    fixture=load_json(a.fixture); score=run_benchmark(fixture); verdict=grade_natural(fixture, score, load_json(a.promotion_policy))
    write_json(a.score, score); write_json(a.verdict, verdict); print(verdict['verdict']); return 0
if __name__=='__main__': raise SystemExit(main())
