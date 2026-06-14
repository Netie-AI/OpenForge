import time

from openanalog.forge.sizer import size_opamp

spec = {
    "circuit_type": "opamp",
    "supply_V": 5.0,
    "targets": {
        "aol_dB": {"value": 90.0, "mode": "min"},
        "gbp_MHz": {"value": 1.1, "mode": "target"},
        "pm_deg": {"value": 60.0, "mode": "min"},
        "iq_uA": {"value": 80.0, "mode": "max"},
        "slew_Vus": {"value": 0.5, "mode": "min"},
    },
}

t0 = time.time()
n = [0]


def prog(i, total, best):
    if i % 5 == 0 or i == total:
        print(f"  [{i}/{total}] best={best:.3f}  ({time.time()-t0:.1f}s)")


BUDGET = 200
best = size_opamp(spec, budget=BUDGET, seed=1, progress=prog)
dt = time.time() - t0
print(f"\nDONE in {dt:.1f}s  ({dt/BUDGET:.2f}s/eval)")
print("score    :", round(best.score, 3), "meets_all:", best.meets_all)
print("metrics  :", best.metrics.as_dict())
print("params   :", {k: round(v, 4) for k, v in best.params.as_dict().items()})
for k, v in best.per_spec.items():
    print(f"  {k:10s} target={v['target']} {v['mode']:6s} measured={v['measured']} pass={v['pass']}")
