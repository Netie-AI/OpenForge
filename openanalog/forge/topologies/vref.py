"""
Voltage reference — bandgap on SKY130 parasitic BJTs (Phase 3).
Deferred on bundled level-1 MOSFET models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.config import NGSPICE_TIMEOUT
from openanalog.forge.topologies.base import (
    Topology,
    TopologyMetrics,
    grab_meas,
    register,
    run_ngspice,
)
from openanalog.sim.models import resolve_models, mos_line

_PHASE3_MSG = (
    "vref deferred on bundled models: requires SKY130 parasitic BJTs. "
    "Set OPENFORGE_MODEL_SET=sky130 to enable bandgap reference."
)


@dataclass
class VRefParams:
    r1_ohm: float = 38000.0
    r2_ohm: float = 12000.0
    ibias_uA: float = 5.0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _params_block(p: VRefParams, supply_V: float) -> str:
    return f""".param VDD={supply_V}
.param R1={p.r1_ohm}
.param R2={p.r2_ohm}
.param IBIAS={p.ibias_uA}u
"""


def _build_bandgap_deck(p: VRefParams, supply_V: float) -> str:
    """Resistor divider + BJT PTAT branch (MOS approximation on SKY130)."""
    ms = resolve_models()
    body = f"""
* OpenForge SKY130 voltage reference
Vsup vdd 0 {supply_V}
Ibias vdd n_bias {{IBIAS}}
Q1 vbe1 vbe1 0 0 {ms.npn} area=1
Q2 vbe2 vbe1 0 0 {ms.npn} area=8
Rptat vbe2 n_trim 5000
Rtop vdd vref {{R1}}
Rbot vref 0 {{R2}}
{mos_line("bias", "n_bias", "n_bias", "0", "0", "n", w="4u", l="0.5u", ms=ms)}
Cout vref 0 10p
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.1
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
dc Vsup 5 5 1 temp -40 125 20
meas dc tempco pp v(vref)
.endc
.end
"""
    return ms.block + _params_block(p, supply_V) + body


class VRefTopology(Topology):
    circuit_type = "vref"
    topology_name = "sky130_bandgap"
    spec_weights = {"vref_V": 2.0, "line_reg_mV": 1.5, "tempco_ppm": 1.0, "iq_uA": 1.0}

    def default_params(self) -> VRefParams:
        return VRefParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "r1_ohm": (5000.0, 50000.0, True),
            "r2_ohm": (5000.0, 50000.0, True),
            "ibias_uA": (1.0, 20.0, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"vref_V", "line_reg_mV", "tempco_ppm", "iq_uA"}

    def measure(
        self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ms = resolve_models()
        if ms.model_set != "sky130":
            m.warnings.append(_PHASE3_MSG)
            m.error = _PHASE3_MSG
            m.ok = False
            return m

        ok, out = run_ngspice(_build_bandgap_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 30))
        m.raw = out[-3000:]
        if not ok:
            m.error = out[:800]
            return m
        vref = grab_meas("vref_nom", out)
        line_reg = grab_meas("line_reg", out)
        tempco = grab_meas("tempco", out)
        isupp = grab_meas("isupp", out)
        m.values["vref_V"] = vref
        m.values["line_reg_mV"] = line_reg * 1000 if line_reg else None
        m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        if tempco is not None and vref:
            m.values["tempco_ppm"] = abs(tempco / vref) * 1e6
        m.ok = vref is not None and 1.18 <= vref <= 1.22
        return m

    def emit_netlist(self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        ms = resolve_models()
        if ms.model_set != "sky130":
            return f"* {_PHASE3_MSG}\n.end\n"
        return _build_bandgap_deck(params, supply_V).replace(".control", "* .control").replace(".endc", "* .endc")

    def device_list(self, params: VRefParams) -> list[dict[str, Any]]:
        ms = resolve_models()
        if ms.model_set != "sky130":
            return [{"name": "—", "role": "deferred (bundled)", "value": ""}]
        p = params.as_dict()
        return [
            {"name": "Q1/Q2", "role": "parasitic BJT pair", "value": "SKY130 NPN"},
            {"name": "Rptat", "role": "PTAT resistor", "value": f"{p['r1_ohm']/1000:.1f} kΩ"},
            {"name": "Rdiv", "role": "divider", "value": f"{p['r2_ohm']/1000:.1f} kΩ"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(VRefTopology())
