"""
Voltage reference — DEFERRED to Phase 3 (SKY130 PDK).

A real ~1.2 V bandgap comes from silicon junction physics (V_BE + PTAT).
Bundled level-1 MOSFET models have no BJT, no meaningful tempco, and a
hard-coded VTO — they cannot produce a trustworthy absolute reference.
Do not fake 1.2 V with diode-connected MOS or resistor dividers in dev mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.forge.topologies.base import (
    Topology,
    TopologyMetrics,
    register,
)

_PHASE3_MSG = (
    "vref deferred to Phase 3: requires SKY130 (or similar) parasitic BJTs. "
    "Bundled level-1 MOSFET models cannot validate absolute Vref, line reg, or tempco."
)


@dataclass
class VRefParams:
    """Placeholder params until SKY130 bandgap topology lands."""

    stub: float = 1.0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class VRefTopology(Topology):
    circuit_type = "vref"
    topology_name = "deferred_bandgap_phase3"
    spec_weights = {"vref_V": 2.0, "line_reg_mV": 1.5, "tempco_ppm": 1.0, "iq_uA": 1.0}

    def default_params(self) -> VRefParams:
        return VRefParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {}

    def measurable_specs(self) -> set[str]:
        return {"vref_V", "line_reg_mV", "tempco_ppm", "iq_uA"}

    def measure(
        self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        m.warnings.append(_PHASE3_MSG)
        m.error = _PHASE3_MSG
        m.ok = False
        return m

    def emit_netlist(self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        return f"* {_PHASE3_MSG}\n.end\n"

    def device_list(self, params: VRefParams) -> list[dict[str, Any]]:
        return [{"name": "—", "role": "deferred to Phase 3 (SKY130)", "value": ""}]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(VRefTopology())
