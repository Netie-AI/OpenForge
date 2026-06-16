#!/usr/bin/env python3
"""Debug preset verification failures."""
import json
import sys

from openanalog.interface.designer import verify_preset
from openanalog.presets import PRESETS

failed_ids = [
    "rs321_opamp",
    "rs8901_comparator",
    "rs2105_switch",
    "rs2660_charge_pump",
    "fast_comparator",
    "low_iq_opamp",
]

for pid in failed_ids:
    out = verify_preset(pid)
    print(f"\n=== {pid} ===")
    print(json.dumps(out, indent=2, default=str))
