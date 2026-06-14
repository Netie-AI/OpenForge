"""Analog switch — CMOS transmission gate."""

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
from openanalog.sim.models import ResolvedModels, resolve_models, mos_line


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


def _sky130_defaults() -> SwitchParams:
    """SKY130 pass devices: W=10µm L=0.15µm gives Ron < 50Ω at VGS=1.8V."""
    return SwitchParams(Wn=10.0, len_n=0.15, Wp=20.0, len_p=0.15, Wdrv=10.0, len_drv=0.15)


def _params_block(p: SwitchParams, supply_V: float) -> str:
    return f""".param VDD={supply_V}
.param WN={p.Wn}u LENN={p.len_n}u WP={p.Wp}u LENP={p.len_p}u
.param WDRV={p.Wdrv}u LENDRV={p.len_drv}u
"""


def _core(ms: ResolvedModels) -> str:
    n_bulk = "0" if ms.model_set == "bundled" else "sig"
    p_bulk = "vdd" if ms.model_set == "bundled" else "sig"
    wn, ln = "{{WN}}", "{{LENN}}"
    wp, lp = "{{WP}}", "{{LENP}}"
    wd, ld = "{{WDRV}}", "{{LENDRV}}"
    lines = [
        "VSUP vdd 0 {VDD}",
        mos_line("n", "out", "sig", "ctrl", n_bulk, "n", w=wn, l=ln, ms=ms),
        mos_line("p", "sig", "out", "ctrl_n", p_bulk, "p", w=wp, l=lp, ms=ms),
        mos_line("nd", "ctrl_n", "ctrl", "0", "0", "n", w=wd, l=ld, ms=ms),
        mos_line("pd", "ctrl_n", "ctrl", "vdd", "vdd", "p", w=wd, l=ld, ms=ms),
        "Rload out 0 1k",
        "Cload out 0 10p",
    ]
    return "\n".join(lines) + "\n"


def _build_dc_deck(p: SwitchParams, supply_V: float) -> str:
    ms = resolve_models()
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
    return "* Switch DC RON\n" + _params_block(p, supply_V) + ms.block + _core(ms) + harness


def _build_ac_deck(p: SwitchParams, supply_V: float) -> str:
    ms = resolve_models()
    harness = """
Vctrl ctrl 0 {VDD}
Vsig sig 0 dc 2.5 ac 1
.control
set filetype=ascii
ac dec 40 1 1G
meas ac dbdc find vdb(out) at=1
meas ac bw_hz when vdb(out)=dbdc-3 cross=1
.endc
.end
"""
    return "* Switch AC BW\n" + _params_block(p, supply_V) + ms.block + _core(ms) + harness


def _build_tran_deck(p: SwitchParams, supply_V: float) -> str:
    ms = resolve_models()
    vmid = supply_V / 2.0
    harness = f"""
Vctrl ctrl 0 pulse(0 {supply_V} 500n 100p 100p 2u 5u)
Vsig sig 0 {vmid}
.control
set filetype=ascii
tran 1n 6u
meas tran ton trig v(ctrl) val={supply_V * 0.5} rise=1 targ v(out) val={vmid * 0.4} rise=1
meas tran toff trig v(ctrl) val={supply_V * 0.5} fall=1 targ v(out) val={vmid * 0.4} fall=1
.endc
.end
"""
    return "* Switch tran\n" + _params_block(p, supply_V) + ms.block + _core(ms) + harness


class AnalogSwitchTopology(Topology):
    circuit_type = "switch"
    topology_name = "cmos_transmission_gate"
    spec_weights = {"ron_ohm": 2.0, "bw_MHz": 1.5, "ton_ns": 1.0, "toff_ns": 1.0, "iq_uA": 1.0}

    def default_params(self) -> SwitchParams:
        if resolve_models().model_set == "sky130":
            return _sky130_defaults()
        return SwitchParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        ms = resolve_models()
        if ms.model_set == "sky130":
            return {
                "Wn": (10.0, 800.0, True),
                "Wp": (20.0, 1600.0, True),
                "len_n": (0.15, 0.5, False),
                "len_p": (0.15, 0.5, False),
                "Wdrv": (5.0, 50.0, True),
            }
        w_max = 4000.0
        return {
            "Wn": (20.0, w_max, True),
            "Wp": (40.0, w_max * 2, True),
            "len_n": (0.18, 1.0, False),
            "len_p": (0.18, 1.0, False),
            "Wdrv": (10.0, 300.0, True),
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
                if bw is None and m.values.get("ron_ohm"):
                    ron = float(m.values["ron_ohm"])
                    m.values["bw_MHz"] = (1.0 / (2.0 * 3.14159 * ron * 10e-12)) / 1e6
                elif bw:
                    m.values["bw_MHz"] = bw / 1e6
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
        ms = resolve_models()
        return "* OpenForge analog switch\n" + _params_block(params, supply_V) + ms.block + _core(ms) + "\n.end\n"

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
