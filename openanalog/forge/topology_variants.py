"""
Connection-level topology variants.

Each variant is a named modification to a base topology's netlist graph.
These are distinct from parameter mutations — they change what connects where.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from openanalog.forge.topologies.comparator import ComparatorParams, _params_block
from openanalog.sim.models import resolve_models


@dataclass
class TopologyVariant:
    name: str
    base_topology: str
    description: str
    apply: Callable[[Any, float], str]
    expected_tradeoff: str


def _comparator_cross_coupled_core(ms, *, supply_V: float) -> str:
    """PMOS load with cross-coupled gates — regenerative latch comparator."""
    return f"""
VSUP vdd 0 {{VDD}}
Iref vdd nb {{IREF}}
M8 nb nb 0 0 {ms.nmos} W={{Wb}} L={{Lb}}
M5 tail nb 0 0 {ms.nmos} W={{W5}} L={{L5}}
M7 vout nb 0 0 {ms.nmos} W={{W7}} L={{L7}}
M1 n1    vinp tail 0 {ms.nmos} W={{W1}} L={{L1}}
M2 nout1 vinn tail 0 {ms.nmos} W={{W1}} L={{L1}}
M3 n1    nout1 vdd vdd {ms.pmos} W={{W3}} L={{L3}}
M4 nout1 n1    vdd vdd {ms.pmos} W={{W3}} L={{L3}}
M6 vout nout1 vdd vdd {ms.pmos} W={{W6}} L={{L6}}
Rload vout 0 {{RLOAD}}
"""


def apply_comparator_cross_coupled(params: ComparatorParams, supply_V: float = 5.0) -> str:
    ms = resolve_models()
    return (
        "* Comparator cross-coupled load variant\n"
        + ms.block
        + _params_block(params, supply_V)
        + _comparator_cross_coupled_core(ms, supply_V=supply_V)
        + "\n.end\n"
    )


VARIANT_REGISTRY: dict[str, list[TopologyVariant]] = {
    "comparator": [
        TopologyVariant(
            name="comparator_cross_coupled_load",
            base_topology="comparator",
            description="Cross-couple M3/M4 PMOS load gates for regenerative latch action",
            apply=apply_comparator_cross_coupled,
            expected_tradeoff="faster tp, worse Vos stability",
        ),
    ],
    "charge_pump": [],
    "opamp": [],
    "switch": [],
    "ldo": [],
}


def list_variants(topology: str) -> list[TopologyVariant]:
    return list(VARIANT_REGISTRY.get(topology, []))


def get_variant(topology: str, name: str) -> TopologyVariant | None:
    for variant in VARIANT_REGISTRY.get(topology, []):
        if variant.name == name:
            return variant
    return None
