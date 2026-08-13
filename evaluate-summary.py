#!/usr/bin/env python3

import json
import pathlib

for p in pathlib.Path('results').glob('*/*/metrics.json'):
    print(json.loads(p.read_text()))
