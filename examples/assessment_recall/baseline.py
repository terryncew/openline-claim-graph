"""Run the conventional flat-table workflow without graph construction or impact analysis."""
import argparse
import json
from pathlib import Path
from demo import inputs, conventional, hash_object, signed, write

p = argparse.ArgumentParser()
p.add_argument('--packets', type=Path, required=True, help='bundle.json containing shared signed packets')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
packets = json.loads(a.packets.read_text())['packets']
records = inputs(packets)  # Same pinned signature, role and binding checks as OpenLine.
statuses, scans = conventional(records)
result = {'checkpoint': hash_object(packets), 'statuses': statuses,
          'next_authority': 'enterprise:risk-owner', 'dependency_rows_scanned': scans,
          'audit': [hash_object(records[n]) for n in ['acceptance', 'change', 'admission']],
          'kind': 'review tickets; not new deployment authorization'}
write(a.output, signed(result, 'receiver'))
print(json.dumps(result, sort_keys=True))
