from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from openanalog.config import NGSPICE_TIMEOUT, resolve_ngspice_cmd


def run_batch(netlist: str, *, timeout: int | None = None) -> tuple[bool, str]:
    """Run ngspice in batch mode on a netlist string."""
    cmd = resolve_ngspice_cmd()
    if not cmd:
        return False, "ngspice not found"
    deck = netlist.strip()
    if ".end" not in deck.lower():
        deck += "\n.end\n"
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".sp", delete=False) as tmp:
            tmp.write(deck)
            path = Path(tmp.name)
        r = subprocess.run(
            [*cmd, "-b", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout or NGSPICE_TIMEOUT,
        )
        text = (r.stdout or "") + (r.stderr or "")
        fatal = any(
            kw in text.lower()
            for kw in (
                "fatal",
                "error on line",
                "could not find a valid modelname",
                "device already exists",
                "simulation interrupted due to error",
                "undefined",
                "expression err",
            )
        )
        return (r.returncode == 0 and not fatal), text[:2000]
    except FileNotFoundError:
        return False, "ngspice executable missing"
    except subprocess.TimeoutExpired:
        return False, "ngspice timeout"
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def run_op(netlist: str, *, timeout: int = 5) -> tuple[bool, str]:
    """DC operating point only — used by seed loader (master plan Phase 2)."""
    deck = netlist.strip()
    if ".op" not in deck.lower():
        deck += "\n.op\n"
    if ".end" not in deck.lower():
        deck += ".end\n"
    return run_batch(deck, timeout=timeout)


def check_syntax(netlist: str, *, timeout: int = 5) -> tuple[bool, str]:
    """
    Pre-simulation gate: run ngspice batch with ``.op`` appended.

    ``sim_validated=True`` requires ngspice exit code 0 **and** a converged DC
    operating point (no fatal parse/model errors). This is not parse-only.
    """
    ok, output = run_op(netlist, timeout=timeout)
    if ok:
        return True, "syntax ok"
    snippet = (output or "ngspice failed")[:300]
    return False, snippet
