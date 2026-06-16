"""
Spec-fidelity test for the API netlist generation path.
Unlike test_netlist_llm.py (offline, no API calls), this test DOES call
the API and DOES run ngspice. It is allowed to be slow and to cost money
(a few cents). Run manually, not in CI, until cost/reliability is proven.

    pytest tests/test_netlist_llm_fidelity.py -v -s
"""

from __future__ import annotations

import pytest

from openanalog.config import GROQ_API_KEY, resolve_ngspice_cmd
from openanalog.forge.netlist_measure import measure_bench_netlist
from openanalog.forge.topologies.base import run_ngspice
from openanalog.llm import generate_netlist_api


def _ngspice_ready() -> bool:
    """True when ngspice is installed and can run a minimal deck."""
    if resolve_ngspice_cmd() is None:
        return False
    ok, _ = run_ngspice("* smoke\nV1 a 0 1\nR1 a 0 1k\n.op\n.end\n", timeout=5)
    return ok

# One test case per topology — spec values pulled from real winners,
# but NOT identical to any single winner (interpolated/perturbed) so this
# tests generalization, not memorized few-shot regurgitation.
FIDELITY_CASES = [
    ("comparator", {"iq_uA": 0.5, "vos_mV": 0.3, "tp_us": 0.4}),
    ("switch", {"ron_ohm": 30, "bw_MHz": 100}),
    ("ldo", {"vout_V": 3.3, "iq_uA": 15}),
    ("charge_pump", {"vout_V": 4.8}),
    # opamp deliberately excluded first pass — hardest spec, test last
]

pytestmark = [
    pytest.mark.skipif(not GROQ_API_KEY, reason="GROQ_API_KEY not set"),
    pytest.mark.skipif(not _ngspice_ready(), reason="ngspice not available or not functional"),
]


def run_full_sim(netlist: str, topology: str) -> dict:
    """Simulate netlist and return measured spec values."""
    metrics = measure_bench_netlist(topology, netlist)
    if not metrics.ok and metrics.error:
        pytest.fail(f"Simulation failed for {topology}: {metrics.error}")
    return metrics.values


@pytest.mark.parametrize("topology,targets", FIDELITY_CASES)
def test_api_netlist_meets_spec(topology, targets):
    result = generate_netlist_api(
        {"targets": {k: {"value": v, "mode": "max"} for k, v in targets.items()}},
        topology,
        provider="groq",
        repair=True,
    )
    assert result.get("syntax_ok"), (
        f"Syntax failed: {result.get('attempts', [])[-1].get('warnings') if result.get('attempts') else result.get('error')}"
    )

    measured = run_full_sim(result["netlist"], topology)

    print(f"\n[{topology}] targets={targets}")
    print(f"[{topology}] measured={measured}")

    failures = []
    for spec_name, target_val in targets.items():
        got = measured.get(spec_name)
        if got is None:
            failures.append(f"{spec_name}: NOT MEASURED")
            continue
        if abs(got - target_val) / abs(target_val) > 0.5:
            failures.append(f"{spec_name}: target={target_val} got={got}")

    assert not failures, f"Spec mismatch: {failures}"
