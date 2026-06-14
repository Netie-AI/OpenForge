"""Dickson charge pump topology with bootstrapped NMOS switches."""

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


@dataclass
class ChargePumpParams:
    stages: int = 2
    n_phases: int = 2
    cap_F: float = 100e-9
    cap_boot_F: float = 0.0  # 0 → auto cap_F / 4
    freq_Hz: float = 500e3
    rload_ohm: float = 100e3
    w_switch: float = 80.0

    def as_dict(self) -> dict:
        return self.__dict__.copy()

    def bootstrap_cap_F(self) -> float:
        return self.cap_boot_F if self.cap_boot_F > 0 else self.cap_F / 4

    def phase_count(self) -> int:
        return 4 if int(self.n_phases) >= 4 else 2


def _clock_lines(p: ChargePumpParams, supply_V: float) -> tuple[list[str], list[str]]:
    """Return (clock source lines, clock node names)."""
    period = 1.0 / p.freq_Hz
    quarter = period / 4.0
    half = period / 2.0
    tr, tf = "1n", "1n"
    n_ph = p.phase_count()
    if n_ph == 4:
        names = ["phi1", "phi2", "phi3", "phi4"]
        delays = [0.0, quarter, half, 3 * quarter]
        lines = [
            f"V{name} {name} 0 pulse(0 {supply_V} {delay} {tr} {tf} {half} {period})"
            for name, delay in zip(names, delays)
        ]
        return lines, names
    lines = [
        f"Vclk1 clk1 0 pulse(0 {supply_V} 0 {tr} {tf} {half} {period})",
        f"Vclk2 clk2 0 pulse(0 {supply_V} {half} {tr} {tf} {half} {period})",
    ]
    return lines, ["clk1", "clk2"]


def _boot_clock(stage: int, clocks: list[str]) -> str:
    n = len(clocks)
    if n == 4:
        # Interleaved: stage0 ↔ phi2/phi4, stage1 ↔ phi1/phi3
        return clocks[(stage * 2 + 1) % n]
    return clocks[(stage + 1) % n]


def _build_bootstrapped_tran_deck(p: ChargePumpParams, supply_V: float) -> str:
    """Bootstrapped NMOS Dickson — gate driven above VDD to eliminate Vth drop."""
    ms = resolve_models()
    stages = max(2, min(int(p.stages), 4))
    period = 1.0 / p.freq_Hz
    tstep = period / 200.0
    tstop = period * 400.0
    w = p.w_switch
    cap_boot = p.bootstrap_cap_F()
    l_switch = "0.18u" if ms.model_set == "sky130" else "0.5u"
    vout_node = f"n{stages}"
    n_ph = p.phase_count()

    clock_lines, clocks = _clock_lines(p, supply_V)

    cap_lines = [f"Cfly1 vdd n1 {p.cap_F}"]
    for i in range(2, stages + 1):
        cap_lines.append(f"Cfly{i} n{i-1} n{i} {p.cap_F}")
    cap_lines.append(f"Cout {vout_node} 0 {p.cap_F * 2}")

    switch_lines: list[str] = []
    boot_lines: list[str] = []
    for i in range(stages):
        clk_boot = _boot_clock(i, clocks)
        left = "vdd" if i == 0 else f"n{i}"
        right = f"n{i + 1}"
        gn = f"gn{i}"
        bulk = "vdd" if i == 0 else left
        switch_lines.append(
            mos_line(f"n{i}", right, gn, left, bulk, "n", w=f"{w}u", l=l_switch, ms=ms)
        )
        boot_lines.append(f"Cboot{i} {gn} {clk_boot} {cap_boot}")
        boot_lines.append(f"Dboot{i} {left} {gn} Dmod")

    settle_thresh = min(4.5, supply_V * 0.9)
    body = "\n".join(
        [
            f"* OpenForge bootstrapped NMOS Dickson ({stages} stages, {n_ph}-phase)",
            ms.block,
            f"Vsup vdd 0 {supply_V}",
            *clock_lines,
            ".model Dmod D (IS=1e-14 N=1)",
            *boot_lines,
            *switch_lines,
            *cap_lines,
            f"Rload {vout_node} 0 {p.rload_ohm}",
            ".control",
            "set filetype=ascii",
            f"tran {tstep} {tstop}",
            f"meas tran vout_avg avg v({vout_node}) from={tstop * 0.7} to={tstop}",
            f"meas tran ripple_pp pp v({vout_node}) from={tstop * 0.7} to={tstop}",
            f"meas tran isupp_avg avg i(vsup) from={tstop * 0.7} to={tstop}",
            f"meas tran settle when v({vout_node})={settle_thresh} rise=1",
            "print isupp_avg",
            "print vout_avg",
            "print ripple_pp",
            ".endc",
            ".end",
        ]
    )
    return body


def _build_tran_deck(p: ChargePumpParams, supply_V: float) -> str:
    return _build_bootstrapped_tran_deck(p, supply_V)


class ChargePumpTopology(Topology):
    circuit_type = "charge_pump"
    topology_name = "dickson_charge_pump"
    spec_weights = {"vout_V": 2.0, "ripple_mV": 1.5, "settle_ms": 1.0, "iout_mA": 1.0, "iq_uA": 0.5}

    def default_params(self) -> ChargePumpParams:
        return ChargePumpParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "stages": (2.0, 4.0, False),
            "n_phases": (2.0, 4.0, False),
            "cap_F": (10e-9, 500e-9, True),
            "cap_boot_F": (5e-9, 250e-9, True),
            "freq_Hz": (100e3, 3e6, True),
            "rload_ohm": (5e3, 100e3, True),
            "w_switch": (20.0, 200.0, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"vout_V", "ripple_mV", "settle_ms", "iout_mA", "iq_uA"}

    def measure(
        self, params: ChargePumpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        n_ph = 4 if int(params.n_phases) >= 4 else 2
        params = ChargePumpParams(
            stages=max(2, int(params.stages)),
            n_phases=n_ph,
            cap_F=max(params.cap_F, 10e-9),
            cap_boot_F=max(params.cap_boot_F, 0.0),
            freq_Hz=max(params.freq_Hz, 10e3),
            rload_ohm=max(params.rload_ohm, 1e3),
            w_switch=max(params.w_switch, 10.0),
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
            {"name": "n_phases", "role": "clock phases", "value": params.phase_count()},
            {"name": "Cpump", "role": "pump cap", "value": f"{p['cap_F']*1e9:.1f} nF"},
            {"name": "Cboot", "role": "bootstrap cap", "value": f"{params.bootstrap_cap_F()*1e9:.1f} nF"},
            {"name": "Wswitch", "role": "NMOS width", "value": f"{p['w_switch']:.0f} µm"},
            {"name": "fclk", "role": "clock", "value": f"{p['freq_Hz']/1e3:.1f} kHz"},
            {"name": "Rload", "role": "load", "value": f"{p['rload_ohm']/1e3:.1f} kOhm"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOIC-8"


register(ChargePumpTopology())
