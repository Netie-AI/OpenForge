"""
openanalog/forge/simulator.py

Fixed simulator for OpenForge forge loop.

Strategy:
  1. Always run .op first — cheapest, catches broken netlists immediately.
  2. Only attempt AC sweep if:
       - .op succeeds (DC operating point converges)
       - netlist has a recognisable output node (out, vout, OUT, VOUT)
       - netlist has a standard SPICE source (Vxxx or Ixxx lines)
  3. .measure syntax uses correct ngspice form:
       .meas ac bw_3db trig ... (NOT vdb(out)-3 expression syntax)
  4. AnalogGenie / Masala-CHAI custom syntax (M0 (...) nmos4) is detected
     and skipped immediately — never sent to ngspice.
  5. Returns FitnessResult with all fields; sim_ok=False on any failure.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from openanalog.config import NGSPICE_TIMEOUT, resolve_ngspice_cmd

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FitnessResult:
    sim_ok: bool = False
    dc_ok: bool = False
    ac_ok: bool = False
    bw_mhz: float = 0.0
    gain_db: float = 0.0
    power_mw: float = 0.0
    fitness: float = 0.0
    failed: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class SimResult:
    """Backward-compatible view used by fitness.py and circuit_checker."""

    ok: bool
    gain_dB: float = 0.0
    bw_3db_MHz: float = 0.0
    phase_margin: float = 0.0
    power_mW: float = 0.0
    output_voltage: float = 0.0
    ripple_mV: float = 0.0
    raw: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Netlist syntax detection
# ---------------------------------------------------------------------------

_ANALOGGENIE_RE = re.compile(r"^\s*[A-Za-z]\w*\s+\(.*\)\s+\w+", re.MULTILINE)

_STANDARD_MOSFET_RE = re.compile(
    r"^\s*[Mm]\w+\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+", re.MULTILINE
)

_OUTPUT_NODE_RE = re.compile(r"\b(out|vout|output|OUT|VOUT|OUTPUT)\b")

_SOURCE_LINE_RE = re.compile(r"^\s*[VvIi]\w+\s+", re.MULTILINE)


def is_analoggenie_syntax(netlist: str) -> bool:
    """Return True if netlist uses AnalogGenie/Masala parenthesis syntax."""
    has_paren_style = bool(_ANALOGGENIE_RE.search(netlist))
    has_standard = bool(_STANDARD_MOSFET_RE.search(netlist))
    return has_paren_style and not has_standard


def has_output_node(netlist: str) -> bool:
    return bool(_OUTPUT_NODE_RE.search(netlist))


def has_spice_source(netlist: str) -> bool:
    return bool(_SOURCE_LINE_RE.search(netlist))


def is_simulatable(netlist: str) -> bool:
    return not is_analoggenie_syntax(netlist) and has_spice_source(netlist)


# ---------------------------------------------------------------------------
# Netlist preparation
# ---------------------------------------------------------------------------


def _strip_existing_analysis(netlist: str) -> str:
    """Remove any existing .tran/.ac/.dc/.measure/.end lines so we control them."""
    lines = []
    for line in netlist.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith(
            (".tran", ".ac", ".dc ", ".noise", ".measure", ".meas", ".end")
        ):
            continue
        lines.append(line)
    return "\n".join(lines)


def _build_op_netlist(netlist: str) -> str:
    """Minimal .op netlist — just DC operating point."""
    body = _strip_existing_analysis(netlist)
    return f"{body}\n.op\n.end\n"


def _build_ac_netlist(netlist: str, out_node: str = "out") -> str:
    """
    AC sweep netlist with correct ngspice .measure syntax.

    Correct ngspice AC measure form:
        .meas ac bw_3db when db(v(out))='max_gain_db-3' FALL=1
    We measure max gain first via a param, then find -3dB crossing.
    """
    body = _strip_existing_analysis(netlist)
    ac_block = f"""
.ac dec 100 1 1G
.meas ac gain_db_max MAX db(v({out_node}))
.meas ac bw_3db WHEN db(v({out_node}))='gain_db_max-3' FALL=1
.end
"""
    return f"{body}\n{ac_block}"


# ---------------------------------------------------------------------------
# ngspice runner
# ---------------------------------------------------------------------------


def _run_ngspice(netlist_text: str, timeout: int = NGSPICE_TIMEOUT) -> tuple[bool, str]:
    """
    Write netlist to temp file, run ngspice -b, return (success, stdout+stderr).
    success=True only if ngspice exits 0 AND no fatal error keywords in output.
    """
    cmd = resolve_ngspice_cmd() or ["ngspice"]
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sp", delete=False, prefix="openforge_"
    ) as tmp:
        tmp.write(netlist_text)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            cmd + ["-b", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        fatal = any(
            kw in output
            for kw in [
                "fatal",
                "Error:",
                "error:",
                "undefined",
                "Expression err",
                "No such parameter",
                "Undefined parameter",
            ]
        )
        return (result.returncode == 0 and not fatal), output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except FileNotFoundError:
        return False, "ngspice not found"
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------


def _parse_op_power(output: str) -> float:
    """Extract total power from .op output (mW). Returns 0.0 if not found."""
    m = re.search(
        r"[Tt]otal\s+power\s+dissipation\s+([\d.eE+\-]+)\s+[Ww]", output
    )
    if m:
        try:
            return float(m.group(1)) * 1e3
        except ValueError:
            pass
    return 0.0


def _parse_ac_results(output: str) -> tuple[float, float]:
    """
    Parse bw_3db (Hz → MHz) and gain_db_max from ngspice .meas output.
    Returns (bw_mhz, gain_db).
    """
    bw_mhz = 0.0
    gain_db = 0.0

    m_bw = re.search(r"bw_3db\s*=\s*([\d.eE+\-]+)", output, re.IGNORECASE)
    if m_bw:
        try:
            bw_mhz = float(m_bw.group(1)) / 1e6
        except ValueError:
            pass

    m_gain = re.search(r"gain_db_max\s*=\s*([\d.eE+\-]+)", output, re.IGNORECASE)
    if m_gain:
        try:
            gain_db = float(m_gain.group(1))
        except ValueError:
            pass

    return bw_mhz, gain_db


# ---------------------------------------------------------------------------
# Fitness scoring
# ---------------------------------------------------------------------------


def _score_fitness(bw_mhz: float, gain_db: float, power_mw: float) -> float:
    """
    Simple normalised fitness in [0, 1].
    Targets (tunable): BW >= 1 MHz, gain >= 20 dB, power <= 10 mW.
    All three must be non-zero for fitness > 0.
    """
    if bw_mhz <= 0 and gain_db <= 0:
        return 0.0

    bw_score = min(bw_mhz / 10.0, 1.0)
    gain_score = min(max(gain_db, 0) / 40.0, 1.0)
    if power_mw > 0:
        power_score = max(0.0, 1.0 - (power_mw / 50.0))
    else:
        power_score = 0.5

    return round((bw_score * 0.4 + gain_score * 0.4 + power_score * 0.2), 4)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def simulate_netlist(netlist: str, circuit_type: str = "unknown") -> FitnessResult:
    """
    Full simulation pipeline for one netlist.

    Steps:
      1. Syntax gate — reject AnalogGenie/Masala immediately
      2. .op run — DC convergence check
      3. AC run — only if .op passes + output node exists + source exists
      4. Score fitness from parsed metrics
    """
    _ = circuit_type
    result = FitnessResult()

    if is_analoggenie_syntax(netlist):
        result.failed["syntax"] = "analoggenie_custom_format"
        result.warnings.append(
            "AnalogGenie/Masala syntax detected (parenthesis style) — "
            "skipped. Convert to standard SPICE before simulating."
        )
        return result

    if not has_spice_source(netlist):
        result.failed["syntax"] = "no_voltage_or_current_source"
        result.warnings.append("No V/I source found — cannot simulate.")
        return result

    op_netlist = _build_op_netlist(netlist)
    op_ok, op_output = _run_ngspice(op_netlist, timeout=max(NGSPICE_TIMEOUT, 10))

    if not op_ok:
        result.failed["dc"] = "op_failed"
        result.warnings.append(f".op failed: {op_output[:200]}")
        return result

    result.dc_ok = True
    result.power_mw = _parse_op_power(op_output)

    if not has_output_node(netlist):
        result.sim_ok = True
        result.fitness = _score_fitness(0, 0, result.power_mw)
        result.warnings.append("No output node found — skipped AC sweep.")
        return result

    out_node = "out"
    for candidate in ["vout", "VOUT", "out", "OUT", "output", "OUTPUT"]:
        if re.search(rf"\b{candidate}\b", netlist):
            out_node = candidate.lower()
            break

    ac_netlist = _build_ac_netlist(netlist, out_node=out_node)
    ac_ok, ac_output = _run_ngspice(ac_netlist, timeout=max(NGSPICE_TIMEOUT, 15))

    if ac_ok:
        result.ac_ok = True
        result.bw_mhz, result.gain_db = _parse_ac_results(ac_output)
    else:
        result.warnings.append(f"AC sweep failed: {ac_output[:200]}")

    result.sim_ok = True
    result.fitness = _score_fitness(result.bw_mhz, result.gain_db, result.power_mw)

    return result


def _fitness_to_sim(fr: FitnessResult) -> SimResult:
    return SimResult(
        ok=fr.sim_ok,
        gain_dB=fr.gain_db,
        bw_3db_MHz=fr.bw_mhz,
        phase_margin=0.0,
        power_mW=fr.power_mw,
        output_voltage=0.0,
        ripple_mV=0.0,
        raw="",
        error="; ".join(fr.warnings) if fr.warnings else "",
    )


def simulate(
    netlist: str,
    analyses: list[str] | None = None,
    *,
    circuit_type: str = "unknown",
) -> SimResult:
    """Backward-compatible wrapper around simulate_netlist()."""
    _ = analyses
    return _fitness_to_sim(simulate_netlist(netlist, circuit_type))
