"""Separate-process verifier; reads exported files, takes an external freshness checkpoint."""
import argparse
import json
from pathlib import Path
from demo import verify, page

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
p.add_argument("--checkpoint", type=Path, required=True)
a = p.parse_args()
b = json.loads((a.output / "bundle.json").read_text())
c = json.loads(a.checkpoint.read_text())["checkpoint"]
verify(b, c)
if (a.output / "review.html").read_text() != page(b):
    raise ValueError("review page tampered")
print("PASS: pinned receipts, bindings, impact replay, baseline, decision records and HTML; freshness conditional on supplied checkpoint")
