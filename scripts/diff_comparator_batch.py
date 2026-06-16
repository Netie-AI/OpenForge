#!/usr/bin/env python3
"""Print pre vs post comparator batch comparison."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    pre = json.loads(Path("/tmp/comparator_batch_pre.json").read_text())
    post = json.loads(Path("/tmp/comparator_batch_post.json").read_text())
    print("=== COMPARATOR REGRESSION GATE ===")
    print(f"pre-refactor (HEAD):    {pre['winners']}/{pre['n']} winners ({pre['win_rate'] * 100:.1f}%)")
    print(f"post-refactor (blocks): {post['winners']}/{post['n']} winners ({post['win_rate'] * 100:.1f}%)")
    print(f"delta winners: {post['winners'] - pre['winners']}")
    print()
    print("spec distributions (winners only):")
    for key in ("tp_us", "vos_mV", "iq_uA"):
        ps, qs = pre["spec_stats"][key], post["spec_stats"][key]
        print(f"  {key}:")
        print(
            f"    pre:  n={ps.get('n', 0)} median={ps.get('median', '—')} "
            f"min={ps.get('min', '—')} max={ps.get('max', '—')}"
        )
        print(
            f"    post: n={qs.get('n', 0)} median={qs.get('median', '—')} "
            f"min={qs.get('min', '—')} max={qs.get('max', '—')}"
        )

    # generation-by-generation fitness + spec identity
    pre_g = {r["gen"]: r for r in pre["per_gen"]}
    post_g = {r["gen"]: r for r in post["per_gen"]}
    win_mismatch = sum(1 for g in range(pre["n"]) if pre_g[g]["won"] != post_g[g]["won"])
    spec_mismatch = 0
    for g in range(pre["n"]):
        if pre_g[g]["won"] and post_g[g]["won"]:
            for k in ("tp_us", "vos_mV", "iq_uA"):
                if pre_g[g]["measured"].get(k) != post_g[g]["measured"].get(k):
                    spec_mismatch += 1
                    break
    print(f"\nper-generation fitness match: {pre['n'] - win_mismatch}/{pre['n']} identical")
    print(f"per-generation winner spec match: {spec_mismatch} mismatches among shared winners")


if __name__ == "__main__":
    main()
