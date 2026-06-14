"""Dickson charge pump topology."""

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


from openanalog.sim.models import resolve_models


@dataclass
class ChargePumpParams:
    stages: int = 2
    cap_F: float = 100e-9
    freq_Hz: float = 500e3
    rload_ohm: float = 10e3
    w_switch: float = 50.0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _build_diode_tran_deck(p: ChargePumpParams, supply_V: float) -> str:
    stages = max(2, min(int(p.stages), 4))
    period = 1.0 / p.freq_Hz
    half = period / 2.0
    tstep = period / 200.0
    tstop = period * 400.0

    # Dickson ladder anchored at vdd (not a floating n0 node).
    cap_lines = [f"C1 vdd n1 {p.cap_F}"]
    for i in range(2, stages + 1):
        cap_lines.append(f"C{i} n{i-1} n{i} {p.cap_F}")
    cap_lines.append(f"Cout n{stages} 0 {p.cap_F * 2}")

    diode_lines = []
    for i in range(stages):
        clk = f"clk{(i % 2) + 1}"
        left = "vdd" if i == 0 else f"n{i}"
        diode_lines.append(f"D{i} {left} {clk} Dmod")
        diode_lines.append(f"D{i}b {clk} n{i+1} Dmod")

    body = "\n".join(
        [
            f"* OpenForge Dickson charge pump ({stages} stages)",
            f"Vsup vdd 0 {supply_V}",
            f"Vclk1 clk1 0 pulse(0 {supply_V} 0 1n 1n {half} {period})",
            f"Vclk2 clk2 0 pulse(0 {supply_V} {half} 1n 1n {half} {period})",
            ".model Dmod D (IS=1e-14 N=1.2 RS=2)",
            *diode_lines,
            *cap_lines,
            f"Rload n{stages} 0 {p.rload_ohm}",
            ".control",
            "set filetype=ascii",
            f"tran {tstep} {tstop}",
            f"meas tran vout_avg avg v(n{stages}) from={tstop * 0.7} to={tstop}",
            f"meas tran ripple_pp pp v(n{stages}) from={tstop * 0.7} to={tstop}",
            f"meas tran isupp_avg avg i(vsup) from={tstop * 0.7} to={tstop}",
            f"meas tran settle when v(n{stages})={supply_V * 0.8} rise=1",
            "print isupp_avg",
            "print vout_avg",
            "print ripple_pp",
            ".endc",
            ".end",
        ]
    )
    return body


def _build_mos_tran_deck(p: ChargePumpParams, supply_V: float) -> str:
    """Bootstrapped MOS-switch Dickson for SKY130 (low Vf loss)."""
    ms = resolve_models()
    stages = max(2, min(int(p.stages), 4))
    period = 1.0 / p.freq_Hz
    half = period / 2.0
    tstep = period / 200.0
    tstop = period * 400.0
    w = p.w_switch

    cap_lines = [f"C1 vdd n1 {p.cap_F}"]
    for i in range(2, stages + 1):
        cap_lines.append(f"C{i} n{i-1} n{i} {p.cap_F}")
    cap_lines.append(f"Cout n{stages} 0 {p.cap_F * 2}")

    switch_lines = []
    for i in range(stages):
        clk = f"clk{(i % 2) + 1}"
        left = "vdd" if i == 0 else f"n{i}"
        switch_lines.append(
            f"M{i}a {left} {clk} n{i+1} 0 {ms.nmos} W={w}u L=0.5u"
        )
        switch_lines.append(
            f"M{i}b {clk} n{i+1} n{i+1} n{i+1} {ms.nmos} W={w}u L=0.5u"
        )

    body = "\n".join(
        [
            f"* OpenForge MOS Dickson charge pump ({stages} stages, SKY130)",
            ms.block,
            f"Vsup vdd 0 {supply_V}",
            f"Vclk1 clk1 0 pulse(0 {supply_V} 0 1n 1n {half} {period})",
            f"Vclk2 clk2 0 pulse(0 {supply_V} {half} 1n 1n {half} {period})",
            *switch_lines,
            *cap_lines,
            f"Rload n{stages} 0 {p.rload_ohm}",
            ".control",
            "set filetype=ascii",
            f"tran {tstep} {tstop}",
            f"meas tran vout_avg avg v(n{stages}) from={tstop * 0.7} to={tstop}",
            f"meas tran ripple_pp pp v(n{stages}) from={tstop * 0.7} to={tstop}",
            f"meas tran isupp_avg avg i(vsup) from={tstop * 0.7} to={tstop}",
            f"meas tran settle when v(n{stages})={supply_V * 0.95} rise=1",
            "print isupp_avg",
            "print vout_avg",
            "print ripple_pp",
            ".endc",
            ".end",
        ]
    )
    return body


def _build_tran_deck(p: ChargePumpParams, supply_V: float) -> str:
    if resolve_models().model_set == "sky130":
        return _build_mos_tran_deck(p, supply_V)
    return _build_diode_tran_deck(p, supply_V)


class ChargePumpTopology(Topology):
    circuit_type = "charge_pump"
    topology_name = "dickson_charge_pump"
    spec_weights = {"vout_V": 2.0, "ripple_mV": 1.5, "settle_ms": 1.0, "iout_mA": 1.0, "iq_uA": 0.5}

    def default_params(self) -> ChargePumpParams:
        return ChargePumpParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        ranges = {
            "stages": (2.0, 4.0, False),
            "cap_F": (10e-9, 500e-9, True),
            "freq_Hz": (100e3, 3e6, True),
            "rload_ohm": (5e3, 100e3, True),
        }
        if resolve_models().model_set == "sky130":
            ranges["w_switch"] = (20.0, 200.0, True)
        return ranges

    def measurable_specs(self) -> set[str]:
        return {"vout_V", "ripple_mV", "settle_ms", "iout_mA", "iq_uA"}

    def measure(
        self, params: ChargePumpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        params = ChargePumpParams(
            stages=max(2, int(params.stages)),
            cap_F=max(params.cap_F, 10e-9),
            freq_Hz=max(params.freq_Hz, 10e3),
            rload_ohm=max(params.rload_ohm, 1e3),
        )
        m = TopologyMetrics()
        ok, out = run_ngspice(_build_tran_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 45))
        m.raw = out[-3000:]
        if not ok:
            m.error = out[:800]
            return m
        vout = grab_meas("vout_avg", out)
        ripple = grab_meas("ripple_pp", out)
        settle = grab_meas("settle", out)
        isupp = grab_meas("isupp_avg", out)
        m.values["vout_V"] = vout
        m.values["ripple_mV"] = ripple * 1000 if ripple else None
        m.values["settle_ms"] = settle * 1000 if settle else None
        m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        if vout and params.rload_ohm > 0:
            m.values["iout_mA"] = (vout / params.rload_ohm) * 1000
        m.ok = vout is not None and vout > 0.1
        return m

    def emit_netlist(self, params: ChargePumpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        return _build_tran_deck(params, supply_V).replace(".control", "* .control").replace(".endc", "* .endc")

    def device_list(self, params: ChargePumpParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "stages", "role": "Dickson stages", "value": int(p["stages"])},
            {"name": "Cpump", "role": "pump cap", "value": f"{p['cap_F']*1e9:.1f} nF"},
            {"name": "fclk", "role": "clock", "value": f"{p['freq_Hz']/1e3:.1f} kHz"},
            {"name": "Rload", "role": "load", "value": f"{p['rload_ohm']/1e3:.1f} kOhm"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOIC-8"


register(ChargePumpTopology())
