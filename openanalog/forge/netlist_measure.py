"""Measure RS-relevant metrics on arbitrary converted seed netlists."""

from __future__ import annotations

import re

from openanalog.config import NGSPICE_TIMEOUT
from openanalog.forge.topologies.base import TopologyMetrics, grab_meas, run_ngspice
from openanalog.ingestion.converter import _supply_current_expr, _supply_current_i, prepare_seed_deck
from openanalog.sim.ngspice import check_syntax

_OUT_CANDIDATES = ("vout", "vout1", "vout2", "out", "output")
_IN_CANDIDATES = ("vin", "vin1", "vin2", "vinp", "vinn", "vinp", "vinn")


def _find_node(netlist: str, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if re.search(rf"\b{re.escape(name)}\b", netlist, re.I):
            return name.lower()
    return None


def _strip_control(deck: str) -> str:
    lines = []
    for line in deck.splitlines():
        lo = line.strip().lower()
        if lo.startswith((".op", ".ac", ".dc ", ".tran", ".meas", ".control", ".endc")):
            continue
        if lo == ".end":
            continue
        lines.append(line)
    return "\n".join(lines)


def _run_control_deck(body: str, control: str, *, timeout: int) -> tuple[bool, str]:
    deck = body.rstrip() + "\n.control\n" + control + "\n.endc\n.end\n"
    return run_ngspice(deck, timeout=timeout)


def _has_vsource_to_net(netlist: str, net: str) -> bool:
    for raw in netlist.splitlines():
        m = re.match(r"^\s*(\S+)\s+(\S+)\s+(\S+)", raw, re.I)
        if m and m.group(1)[0].upper() == "V" and m.group(2).lower() == net.lower():
            return True
    return False


def measure_bench_netlist(topology: str, netlist: str) -> TopologyMetrics:
    """Run topology-appropriate ngspice benches on a prepared seed deck."""
    m = TopologyMetrics()
    deck = prepare_seed_deck(netlist)
    ok, err = check_syntax(deck, timeout=15)
    if not ok:
        m.warnings.append(f"syntax/DC precheck failed: {err[:200]}")

    body = _strip_control(deck)
    isupp_expr = _supply_current_expr(deck)
    isupp_i = _supply_current_i(deck)
    out_node = _find_node(netlist, _OUT_CANDIDATES)
    in_node = _find_node(netlist, _IN_CANDIDATES)

    if topology == "opamp":
        if not out_node:
            m.warnings.append("no output node for opamp AC")
            m.ok = False
            return m
        stim = f"Vac_{in_node} {in_node} 0 dc 0.9 ac 1" if in_node else ""
        ctrl = f"""
set filetype=ascii
set units=degrees
op
let isupp = {isupp_expr}
print isupp
ac dec 30 0.1 1G
meas ac aol_db find vdb({out_node}) at=0.1
meas ac gbw_hz when vdb({out_node})=0 cross=1
meas ac ph_ugf find vp({out_node}) when vdb({out_node})=0 cross=1
meas ac ph_dc find vp({out_node}) at=0.1
"""
        ok, raw = _run_control_deck(
            body + ("\n" + stim if stim else ""),
            ctrl,
            timeout=max(NGSPICE_TIMEOUT, 20),
        )
        m.raw = raw[-2500:]
        if not ok:
            m.error = raw[:400]
            return m
        isupp = grab_meas("isupp", raw)
        m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        m.values["aol_dB"] = grab_meas("aol_db", raw)
        gbw = grab_meas("gbw_hz", raw)
        m.values["gbp_MHz"] = gbw / 1e6 if gbw else None
        ph_ugf, ph_dc = grab_meas("ph_ugf", raw), grab_meas("ph_dc", raw)
        if ph_ugf is not None and ph_dc is not None:
            pm = 180.0 + (ph_ugf - ph_dc)
            while pm > 180:
                pm -= 360
            while pm < -180:
                pm += 360
            m.values["pm_deg"] = pm
        m.ok = all(m.values.get(k) is not None for k in ("aol_dB", "gbp_MHz", "pm_deg", "iq_uA"))

    elif topology == "comparator":
        if not out_node:
            m.ok = False
            m.warnings.append("no output node for comparator tran")
            return m
        vinp = _find_node(netlist, ("vinp", "vin1", "vin")) or "vinp"
        vinn = _find_node(netlist, ("vinn", "vin2")) or "vinn"
        extras = ""
        if not _has_vsource_to_net(body, vinp):
            extras += f"\nVstim_p {vinp} 0 pulse(2.35 2.65 200n 50p 50p 4u 20u)"
        if not _has_vsource_to_net(body, vinn):
            extras += f"\nVstim_n {vinn} 0 2.5"
        ctrl = f"""
set filetype=ascii
op
let isupp = {isupp_expr}
print isupp
tran 5n 2u
meas tran tp when v({out_node})=1.25 cross=1
"""
        ok, raw = _run_control_deck(body + extras, ctrl, timeout=max(NGSPICE_TIMEOUT, 25))
        m.raw = raw[-2000:]
        if ok:
            isupp = grab_meas("isupp", raw)
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
            tp = grab_meas("tp", raw)
            m.values["tp_us"] = tp * 1e6 if tp else None
            m.values["vos_mV"] = None
        m.ok = m.values.get("tp_us") is not None and m.values.get("iq_uA") is not None

    elif topology == "switch":
        sig = _find_node(netlist, ("sig", "vin", "in")) or "sig"
        out = out_node or "out"
        extras = ""
        if not _has_vsource_to_net(body, sig):
            extras += f"\nVsig {sig} 0 dc 0.9"
        if not _has_vsource_to_net(body, "ctrl"):
            extras += f"\nVctrl_drv ctrl 0 1.8"
        ctrl = f"""
set filetype=ascii
alter Vctrl dc 1.8
alter Vin dc 0.9
op
let iload = abs(v({out})/1000)
let ron = abs(v({sig})-v({out}))/max(iload, 1e-15)
print ron
let isupp = {isupp_expr}
print isupp
ac dec 30 1 1G
meas ac bw_hz when vdb({out})=-3 cross=1
"""
        ok, raw = _run_control_deck(body + extras, ctrl, timeout=max(NGSPICE_TIMEOUT, 20))
        if ok:
            ron = grab_meas("ron", raw)
            m.values["ron_ohm"] = ron if ron and 0 < ron < 1e6 else None
            isupp = grab_meas("isupp", raw)
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
            bw = grab_meas("bw_hz", raw)
            m.values["bw_MHz"] = bw / 1e6 if bw else None
            m.values["ton_ns"] = None
            m.values["toff_ns"] = None
        m.ok = m.values.get("ron_ohm") is not None

    elif topology == "ldo":
        vout_node = _find_node(netlist, ("vout", "out")) or "vout"
        ctrl = f"""
set filetype=ascii
op
let vout_dc = v({vout_node})
print vout_dc
let isupp = {isupp_expr}
print isupp
"""
        ok, raw = _run_control_deck(body, ctrl, timeout=max(NGSPICE_TIMEOUT, 15))
        m.raw = raw[-2000:]
        if ok:
            vout = grab_meas("vout_dc", raw)
            isupp = grab_meas("isupp", raw)
            m.values["vout_V"] = vout
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        m.ok = m.values.get("vout_V") is not None

    elif topology == "charge_pump":
        pump_out = _find_node(netlist, ("vout", "n1", "n2", "n3", "out")) or "n1"
        ctrl = f"""
set filetype=ascii
tran 10n 5m
meas tran vout_avg avg v({pump_out}) from=3m to=5m
meas tran ripple_pp pp v({pump_out}) from=3m to=5m
meas tran settle when v({pump_out})=1.5 rise=1
let isupp = abs(avg({isupp_i}) from=3m to=5m)
print isupp
"""
        ok, raw = _run_control_deck(body, ctrl, timeout=max(NGSPICE_TIMEOUT, 45))
        if ok:
            vout = grab_meas("vout_avg", raw)
            ripple = grab_meas("ripple_pp", raw)
            settle = grab_meas("settle", raw)
            isupp = grab_meas("isupp", raw)
            m.values["vout_V"] = vout
            m.values["ripple_mV"] = ripple * 1000 if ripple else None
            m.values["settle_ms"] = settle * 1000 if settle else None
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        m.ok = m.values.get("vout_V") is not None

    else:
        m.ok = False
        m.warnings.append(f"no bench measure path for {topology}")

    return m
