#!/usr/bin/env python3
"""Per-spec compliance breakdown for LDO sizing seeds (PSRR verify follow-up)."""
from __future__ import annotations

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design


def main() -> int:
    spec = DEV_MODE_SPECS["ldo"]
    print(f"spec={spec}\n")
    for seed in (7, 23, 1, 3, 42):
        r = design(inline_spec=spec, budget=200, seed=seed, record_kg=False)
        print(f"=== seed={seed} meets_all={r['meets_all']} score={r.get('score')} ===")
        for k, v in r["compliance"].items():
            meas = v["measured"]
            ms = f"{meas:.4f}" if isinstance(meas, (int, float)) else str(meas)
            print(
                f"  {k:14} mode={v['mode']:5} target={v['target']} "
                f"measured={ms} pass={v['pass']}"
            )
        psrr = r["metrics"].get("psrr_dB")
        print(f"  psrr_dB (bench only, not in envelope): {psrr}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
