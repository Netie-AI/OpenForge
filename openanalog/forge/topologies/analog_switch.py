"""Analog switch — CMOS transmission gate."""

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
class SwitchParams:
    Wn: float = 50.0
    len_n: float = 0.5
    Wp: float = 100.0
    len_p: float = 0.5
    Wdrv: float = 10.0
    len_drv: float = 0.5

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _params_block(p: SwitchParams, supply_V: float) -> str:
    return f""".param VDD={supply_V}
.param WN={p.Wn}u LENN={p.len_n}u WP={p.Wp}u LENP={p.len_p}u
.param WDRV={p.Wdrv}u LENDRV={p.len_drv}u
"""

_CORE = f"""
VSUP vdd 0 {{VDD}}
Mn out sig ctrl 0 {NMOS} W={{WN}} L={{LENN}}
Mp out sig ctrl_n vdd {PMOS} W={{WP}} L={{LENP}}
Mnd ctrl_n ctrl 0 0 {NMOS} W={{WDRV}} L={{LENDRV}}
Mpd ctrl_n ctrl vdd vdd {PMOS} W={{WDRV}} L={{LENDRV}}
Rload out 0 1k
Cload out 0 10p
"""


def _build_dc_deck(p: SwitchParams, supply_V: float) -> str:
    harness = """
Vctrl ctrl 0 {VDD}
Vsig sig 0 dc 2.5
.control
set filetype=ascii
op
let iload = abs(v(out)/1000)
let ron = abs(v(sig)-v(out))/max(iload, 1e-15)
print ron
let isupp = abs(i(vsup))
print isupp
.endc
.end
"""
    return "* Switch DC RON\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


def _build_ac_deck(p: SwitchParams, supply_V: float) -> str:
    harness = """
Vctrl ctrl 0 {VDD}
Vsig sig 0 dc 2.5 ac 1
.control
set filetype=ascii
ac dec 30 1 1G
meas ac bw_hz when vdb(out)=-3
.endc
.end
"""
    return "* Switch AC BW\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


def _build_tran_deck(p: SwitchParams, supply_V: float) -> str:
    harness = f"""
Vctrl ctrl 0 pulse(0 {supply_V} 1u 1n 1n 5u 10u)
Vsig sig 0 2.5
.control
set filetype=ascii
tran 5n 12u
meas tran ton when v(out)=1.25 rise=1
meas tran toff when v(out)=1.25 fall=1
.endc
.end
"""
    return "* Switch tran\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


class AnalogSwitchTopology(Topology):
    circuit_type = "switch"
    topology_name = "cmos_transmission_gate"
    spec_weights = {"ron_ohm": 2.0, "bw_MHz": 1.5, "ton_ns": 1.0, "toff_ns": 1.0, "iq_uA": 1.0}

    def default_params(self) -> SwitchParams:
        return SwitchParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "Wn": (10.0, 200.0, True), "Wp": (20.0, 400.0, True),
            "len_n": (0.3, 2.0, False), "len_p": (0.3, 2.0, False),
            "Wdrv": (2.0, 60.0, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"ron_ohm", "bw_MHz", "ton_ns", "toff_ns", "iq_uA"}

    def measure(
        self, params: SwitchParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ok, out = run_ngspice(_build_dc_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 10))
        if ok:
            ron = grab_meas("ron", out)
            isupp = grab_meas("isupp", out)
            m.values["ron_ohm"] = ron if ron and 0 < ron < 1e6 else None
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        if with_full:
            aok, aout = run_ngspice(_build_ac_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 15))
            if aok:
                bw = grab_meas("bw_hz", aout)
                m.values["bw_MHz"] = bw / 1e6 if bw else None
            tok, tout = run_ngspice(_build_tran_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 20))
            if tok:
                ton = grab_meas("ton", tout)
                toff = grab_meas("toff", tout)
                m.values["ton_ns"] = ton * 1e9 if ton else None
                m.values["toff_ns"] = toff * 1e9 if toff else None
            m.raw = (aout if aok else out)[-2000:]
        m.ok = m.values.get("ron_ohm") is not None
        return m

    def emit_netlist(self, params: SwitchParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        return "* OpenForge analog switch\n" + BUNDLED_MODELS + _params_block(params, supply_V) + _CORE + "\n.end\n"

    def device_list(self, params: SwitchParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "Mn", "role": "NMOS pass", "W_um": round(p["Wn"], 3), "L_um": round(p["len_n"], 3)},
            {"name": "Mp", "role": "PMOS pass", "W_um": round(p["Wp"], 3), "L_um": round(p["len_p"], 3)},
            {"name": "Mdrv", "role": "control inv", "W_um": round(p["Wdrv"], 3), "L_um": round(p["len_drv"], 3)},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-6"


register(AnalogSwitchTopology())
