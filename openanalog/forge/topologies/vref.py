"""Voltage reference — beta-multiplier + PTAT branch (bandgap-style)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.config import NGSPICE_TIMEOUT
from openanalog.forge.topologies.base import (
    BUNDLED_MODELS,
    NMOS,
    PMOS,
    Topology,
    TopologyMetrics,
    grab_meas,
    register,
    run_ngspice,
)


@dataclass
class VRefParams:
    W1: float = 8.0
    L1: float = 1.0
    W2: float = 32.0
    L2: float = 1.0
    W3: float = 12.0
    L3: float = 1.0
    Wb: float = 8.0
    Lb: float = 1.0
    Iref: float = 15e-6
    R1: float = 10e3
    R2: float = 10e3

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _params_block(p: VRefParams, supply_V: float) -> str:
    return f""".param VDD={supply_V}
.param W1={p.W1}u L1={p.L1}u W2={p.W2}u L2={p.L2}u
.param W3={p.W3}u L3={p.L3}u Wb={p.Wb}u Lb={p.Lb}u
.param IREF={p.Iref} R1={p.R1} R2={p.R2}
"""

_CORE = f"""
VSUP vdd 0 {{VDD}}
Iref vdd nb {{IREF}}
M8 nb nb 0 0 {NMOS} W={{Wb}} L={{Lb}}
* beta-multiplier (M1 diode, M2 mirror)
M1 n1 n1 0 0 {NMOS} W={{W1}} L={{L1}}
M2 n2 n1 0 0 {NMOS} W={{W2}} L={{L2}}
* PMOS load + reference node
M3 vref n2 vdd vdd {PMOS} W={{W3}} L={{L3}}
R1 vref 0 {{R1}}
R2 vref n1 {{R2}}
"""


def _build_op_deck(p: VRefParams, supply_V: float) -> str:
    harness = """
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
print v(vref)
.endc
.end
"""
    return "* VRef OP\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


def _build_line_deck(p: VRefParams, supply_V: float) -> str:
    harness = f"""
.control
set filetype=ascii
dc VSUP 2 {supply_V + 2} 0.25
meas dc vref_lo find v(vref) at=3
meas dc vref_hi find v(vref) at={supply_V + 1}
.endc
.end
"""
    return "* VRef line reg\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


def _build_temp_deck(p: VRefParams, supply_V: float) -> str:
    harness = """
.temp 25 85
.control
set filetype=ascii
op
let v25 = v(vref)
.endc
.end
"""
    m = TopologyMetrics()
    m.warnings.append(
        "tempco uses bundled level-1 models; absolute ppm/°C needs foundry PDK (e.g. SKY130)."
    )
    return "* VRef temp (approx)\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


class VRefTopology(Topology):
    circuit_type = "vref"
    topology_name = "beta_multiplier_vref"
    spec_weights = {"vref_V": 2.0, "line_reg_mV": 1.5, "tempco_ppm": 1.0, "iq_uA": 1.0}

    def default_params(self) -> VRefParams:
        return VRefParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "W1": (2.0, 40.0, True), "W2": (4.0, 120.0, True), "W3": (2.0, 60.0, True),
            "Wb": (2.0, 40.0, True), "Iref": (2e-6, 80e-6, True),
            "R1": (2e3, 50e3, True), "R2": (2e3, 50e3, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"vref_V", "line_reg_mV", "tempco_ppm", "iq_uA"}

    def measure(
        self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        m.warnings.append(
            "Bundled level-1 models: line regulation and Iq are indicative; "
            "tempco accuracy requires foundry PDK."
        )
        ok, out = run_ngspice(_build_op_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 10))
        if ok:
            isupp = grab_meas("isupp", out)
            vref = grab_meas("v\\(vref\\)", out) or grab_meas("v(vref)", out)
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
            m.values["vref_V"] = vref
        if with_full:
            lok, lout = run_ngspice(_build_line_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 15))
            if lok:
                vlo = grab_meas("vref_lo", lout)
                vhi = grab_meas("vref_hi", lout)
                if vlo is not None and vhi is not None and vlo > 0:
                    m.values["line_reg_mV"] = abs(vhi - vlo) * 1000
                    m.values["tempco_ppm"] = abs((vhi - vlo) / vlo) * 1e6 / max(supply_V - 1, 1)
            m.raw = lout[-2000:]
        m.ok = m.values.get("vref_V") is not None
        return m

    def emit_netlist(self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        return "* OpenForge voltage reference\n" + BUNDLED_MODELS + _params_block(params, supply_V) + _CORE + "\n.end\n"

    def device_list(self, params: VRefParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "M1/M2", "role": "beta-multiplier", "W_um": round(p["W1"], 3), "L_um": round(p["L1"], 3)},
            {"name": "M3", "role": "PMOS load", "W_um": round(p["W3"], 3), "L_um": round(p["L3"], 3)},
            {"name": "R1/R2", "role": "divider", "value": f"{p['R1']/1e3:.1f} kOhm"},
            {"name": "Iref", "role": "bias", "value": f"{p['Iref']*1e6:.2f} uA"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(VRefTopology())
