"""Verify MoE works on v3.9.0 baseline after restore."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, '.')
from pa_cli.moe_router import assemble_dataset, ENGINES

d = assemble_dataset(Path('bench/v01'))
print(f'n_queries: {len(d["queries"])}')
print('label dist:')
for i, e in enumerate(ENGINES):
    n = int(np.sum(np.array(d['labels']) == i))
    print(f'  {e:12s} {n}')
