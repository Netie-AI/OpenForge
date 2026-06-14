from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

from rich.console import Console
from rich.table import Table

from openanalog.config import (
    ANALOGGENIE_DIR,
    MASALA_DIR,
    SEEDS_DIR,
    SEEDS_NORMALIZED,
    SPICE_DATASETS_FALLBACK,
    ensure_dirs,
    resolve_ngspice_cmd,
)
from openanalog.ingestion.converter import normalize_for_forge, prepare_seed_deck
from openanalog.ingestion.dialect import detect_dialect, dialect_breakdown
from openanalog.sim.ngspice import check_syntax, run_op

console = Console()

SPICE_SUBDIRS = ("kicad_github", "ltspice_demos", "ltspice_examples")


def _count_components(text: str) -> dict[str, int]:
    return {
        "M": len(re.findall(r"^\s*M\w*\s", text, re.I | re.M)),
        "C": len(re.findall(r"^\s*C\w*\s", text, re.I | re.M)),
        "R": len(re.findall(r"^\s*R\w*\s", text, re.I | re.M)),
        "L": len(re.findall(r"^\s*L\w*\s", text, re.I | re.M)),
        "E": len(re.findall(r"^\s*E\w*\s", text, re.I | re.M)),
        "Q": len(re.findall(r"^\s*Q\w*\s", text, re.I | re.M)),
        "X": len(re.findall(r"^\s*X\w*\s", text, re.I | re.M)),
    }


def _classify_circuit(text: str, path: Path) -> str:
    blob = (text + " " + path.name).lower()
    if any(k in blob for k in ("charge pump", "charge_pump", "dickson", "pump stage")):
        return "charge_pump"
    if any(k in blob for k in ("crossbar", "mvm", "mac array")):
        return "crossbar"
    if "mirror" in blob or "current mirror" in blob:
        return "mirror"

    c = _count_components(text)
    m, r, cap, q = c["M"], c["R"], c["C"], c["Q"]

    # AnalogGenie custom lines: M0 (...) pmos4
    ag_m = len(re.findall(r"\b(nmos4|pmos4|npn|pnp)\b", text, re.I))
    m_total = m + ag_m

    if m_total >= 6 and re.search(r"M\d+.*M\d+.*tail|diff.*pair", blob, re.I):
        return "diff_amp"
    if m_total >= 2 and len(re.findall(r"\bM\d+", text)) >= 2 and "matched" in blob:
        return "mirror"
    if m_total >= 4 and cap >= 2:
        return "amplifier"
    if r >= 2 and cap >= 2 and m_total <= 2:
        return "filter"
    if m_total >= 3:
        return "amplifier"
    if cap >= 3:
        return "filter"
    return "unknown"


def _emit(record: dict[str, Any], out: Path) -> None:
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _simulate_file(path: Path, *, dry_run: bool) -> tuple[bool, list[str], str]:
    if dry_run:
        text = path.read_text(encoding="utf-8", errors="ignore")
        flat, warnings, dialect = normalize_for_forge(text)
        return True, warnings, flat if dialect == "masala-paren" else text
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _simulate_text(text, dry_run=dry_run)


def _simulate_text(text: str, *, dry_run: bool) -> tuple[bool, list[str], str]:
    """Return (sim_ok, conversion_warnings, flat_netlist)."""
    flat, warnings, dialect = normalize_for_forge(text)
    if dry_run:
        if dialect == "masala-paren":
            return True, warnings, flat
        return True, warnings, text
    deck = prepare_seed_deck(flat)
    ok, _ = check_syntax(deck, timeout=5)
    return ok, warnings, flat if dialect == "masala-paren" else text


def _iter_netlists(root: Path) -> Iterator[tuple[Path, str]]:
    for ext in ("*.net", "*.cir", "*.sp", "*.asc"):
        for p in root.rglob(ext):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if len(text.strip()) < 20:
                continue
            yield p, text


def ltspice_asc_to_spice(text: str) -> str:
    """Minimal .asc → SPICE-ish conversion for seed parsing."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.upper().startswith("SYMATTR"):
            continue
        # SYMBOL cap 0 0 R0 ... → skip layout
        if line.upper().startswith("SYMBOL") or line.upper().startswith("WIRE"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    if ".end" not in body.lower():
        body += "\n.end\n"
    return body


def spice_datasets_loader(
    out: Path,
    stats: dict,
    *,
    dry_run: bool,
    limit: int,
) -> int:
    roots = [SEEDS_DIR / "spice-datasets", SPICE_DATASETS_FALLBACK]
    root = next((r for r in roots if r.exists()), None)
    if not root:
        console.print("[yellow]spice-datasets not found[/yellow]")
        return 0

    count = 0
    scanned = 0
    subroots = [root / s for s in SPICE_SUBDIRS if (root / s).exists()]
    if not subroots:
        subroots = [root]

    for sub in subroots:
        for path, text in _iter_netlists(sub):
            scanned += 1
            if path.suffix.lower() == ".asc":
                text = ltspice_asc_to_spice(text)
            topo = _classify_circuit(text, path)
            stats[topo]["total"] += 1
            ok, conv_warnings, flat_nl = _simulate_text(text, dry_run=dry_run)
            if not ok:
                continue
            if count >= limit:
                break
            stats[topo]["validated"] += 1
            dialect = detect_dialect(text)
            rec = {
                "id": f"spice_{count:05d}",
                "source": "spice_datasets",
                "source_subdir": sub.name,
                "circuit_type": topo,
                "netlist": flat_nl,
                "original_dialect": dialect,
                "conversion_warnings": conv_warnings,
                "param_hints": _count_components(flat_nl),
                "spec_hints": {},
                "sim_validated": True,
                "source_confidence": 0.65,
                "path": str(path.relative_to(root)),
            }
            _emit(rec, out)
            count += 1
        if count >= limit:
            break

    console.print(f"[dim]spice-datasets scanned={scanned} kept={count}[/dim]")
    return count


def analoggenie_loader(
    out: Path,
    stats: dict,
    *,
    dry_run: bool,
    limit: int = 200,
) -> int:
    dataset = ANALOGGENIE_DIR / "Dataset"
    if not dataset.exists():
        console.print("[dim]AnalogGenie/Dataset not found at repo root[/dim]")
        return 0

    count = 0
    for cir in sorted(dataset.rglob("*.cir")):
        if count >= limit:
            break
        text = cir.read_text(encoding="utf-8", errors="ignore")
        topo = _classify_circuit(text, cir)
        if topo == "unknown" and ("pmos4" in text or "nmos4" in text):
            topo = "amplifier"
        stats[topo]["total"] += 1
        ok, conv_warnings, flat_nl = _simulate_text(text, dry_run=dry_run)
        stats[topo]["validated"] += int(ok)
        dialect = detect_dialect(text)
        rec = {
            "id": f"analoggenie_{cir.parent.name}",
            "source": "analoggenie",
            "circuit_type": topo,
            "netlist": flat_nl,
            "original_dialect": dialect,
            "conversion_warnings": conv_warnings,
            "param_hints": {"device_lines": len(text.splitlines())},
            "spec_hints": {},
            "sim_validated": ok,
            "source_confidence": 0.8 if ok else 0.5,
            "path": str(cir.relative_to(dataset)),
        }
        _emit(rec, out)
        count += 1
    return count


def _classify_from_description(text: str) -> str:
    blob = text.lower()
    if any(k in blob for k in ("transimpedance", " tia", "tia ", "photodiode amplifier")):
        return "tia"
    if any(k in blob for k in ("low-dropout", " ldo", "ldo ", "voltage regulator")):
        return "ldo"
    if any(k in blob for k in ("oscillator", "ring oscillator", "vco")):
        return "osc"
    if "mirror" in blob or "current mirror" in blob:
        return "mirror"
    if any(k in blob for k in ("differential", "diff pair", "fully differential")):
        return "diff_amp"
    if any(k in blob for k in ("filter", "bandpass", "low-pass", "high-pass")):
        return "filter"
    if any(k in blob for k in ("integrator", "amplifier", "operational amplifier", "op-amp", " op amp")):
        return "amplifier"
    if any(k in blob for k in ("charge pump", "switched-capacitor", "switched capacitor")):
        return "charge_pump"
    return "unknown"


def _parse_masala_jsonl(line: str) -> tuple[str, str] | None:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    user_text = ""
    netlist = ""
    for msg in data.get("messages", []):
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            user_text = content
        elif role == "assistant":
            netlist = content
    if not netlist.strip():
        return None
    return user_text, netlist


def masala_chai_loader(
    out: Path,
    stats: dict,
    *,
    dry_run: bool,
    limit: int = 500,
) -> int:
    root = MASALA_DIR
    jsonl_path = root / "analoggenie.jsonl"
    if not root.exists():
        console.print("[yellow]Masala-CHAI not cloned — run setup.sh[/yellow]")
        return 0
    if not jsonl_path.exists():
        console.print("[yellow]Masala-CHAI analoggenie.jsonl not found[/yellow]")
        return 0

    count = 0
    with jsonl_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if count >= limit:
                break
            parsed = _parse_masala_jsonl(line)
            if not parsed:
                continue
            description, netlist = parsed
            pseudo_path = Path(f"record_{line_no:05d}.cir")
            topo = _classify_from_description(description)
            if topo == "unknown":
                topo = _classify_circuit(netlist, pseudo_path)
            stats[topo]["total"] += 1
            ok, conv_warnings, flat_nl = _simulate_text(netlist, dry_run=dry_run)
            if ok:
                stats[topo]["validated"] += 1
            dialect = detect_dialect(netlist)
            rec = {
                "id": f"masala_{count:05d}",
                "source": "masala_chai",
                "circuit_type": topo,
                "netlist": flat_nl,
                "original_dialect": dialect,
                "conversion_warnings": conv_warnings,
                "param_hints": _count_components(flat_nl),
                "spec_hints": {"description": description[:800]},
                "sim_validated": ok,
                "source_confidence": 0.75 if ok else 0.55,
                "path": f"analoggenie.jsonl:{line_no}",
            }
            _emit(rec, out)
            count += 1

    console.print(f"[dim]Masala-CHAI jsonl records loaded={count}[/dim]")
    return count


def load_aicircuit(out: Path, stats: dict) -> int:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        console.print("[dim]huggingface_hub not installed — skip AICircuit[/dim]")
        return 0
    local = SEEDS_DIR / "AICircuit"
    try:
        snapshot_download("aicircuit/AICircuit", local_dir=str(local))
    except Exception as e:
        console.print(f"[yellow]AICircuit download failed: {e}[/yellow]")
        return 0
    count = 0
    for jf in local.rglob("*.json"):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        topo = str(data.get("topology_type", data.get("type", "unknown")))
        stats[topo]["total"] += 1
        stats[topo]["validated"] += 1
        rec = {
            "id": f"aicircuit_{count:05d}",
            "source": "aicircuit",
            "circuit_type": topo,
            "netlist": data.get("netlist", ""),
            "param_hints": data.get("param_ranges", data.get("params", {})),
            "spec_hints": data.get("perf_metrics", data.get("specs", {})),
            "sim_validated": True,
            "source_confidence": 0.9,
        }
        if rec["netlist"]:
            _emit(rec, out)
            count += 1
    return count


def load_all_seeds(
    *,
    symbench_limit: int = 500,
    analoggenie_limit: int = 200,
    masala_limit: int = 500,
    reset: bool = True,
    dry_run: bool = False,
) -> Path:
    ensure_dirs()
    out = SEEDS_NORMALIZED
    if reset and out.exists():
        out.unlink()
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "validated": 0})

    ngspice_cmd = resolve_ngspice_cmd()
    if not dry_run:
        if not ngspice_cmd:
            console.print(
                "[red]ngspice not found.[/red]\n"
                "WSL: wsl -u root -e bash -lc \"apt-get install -y ngspice\"\n"
                "Or: python -m openanalog load-seeds --dry-run"
            )
            raise SystemExit(2)
        try:
            subprocess.run([*ngspice_cmd, "--version"], capture_output=True, timeout=5)
        except Exception:
            console.print("[red]ngspice not executable[/red]")
            raise SystemExit(2)

    totals = {
        "spice_datasets": spice_datasets_loader(
            out, stats, dry_run=dry_run, limit=symbench_limit
        ),
        "analoggenie": analoggenie_loader(
            out, stats, dry_run=dry_run, limit=analoggenie_limit
        ),
        "masala": masala_chai_loader(
            out, stats, dry_run=dry_run, limit=masala_limit
        ),
        "aicircuit": load_aicircuit(out, stats),
    }
    console.print(f"Loaded: {totals}")
    print_seed_stats(stats)
    _print_dialect_report(out)
    return out


def _print_dialect_report(path: Path) -> None:
    """Print dialect + sim-valid breakdown for all seeds in the output file."""
    if not path.exists():
        return
    netlists: list[str] = []
    sim_ok = 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        total += 1
        netlists.append(rec.get("netlist", ""))
        if rec.get("sim_validated"):
            sim_ok += 1
    breakdown = dialect_breakdown(netlists)
    table = Table(title="Seed corpus dialect report (Phase 2)")
    table.add_column("dialect")
    table.add_column("count")
    for d, n in sorted(breakdown.items()):
        table.add_row(d, str(n))
    table.add_row("TOTAL", str(total))
    table.add_row("sim_validated", str(sim_ok))
    pct = f"{100 * sim_ok / total:.1f}%" if total else "—"
    table.add_row("sim_valid_pct", pct)
    console.print(table)


def print_seed_stats(stats: dict[str, dict[str, int]]) -> None:
    table = Table(title="Seed dataset stats (master plan Phase 2)")
    table.add_column("circuit_type")
    table.add_column("count")
    table.add_column("sim_valid")
    table.add_column("sim_valid_pct")
    total_n = total_v = 0
    for topo, s in sorted(stats.items()):
        total = s["total"]
        val = s["validated"]
        total_n += total
        total_v += val
        rate = f"{100 * val / total:.1f}%" if total else "—"
        table.add_row(topo, str(total), str(val), rate)
    table.add_row("TOTAL", str(total_n), str(total_v), f"{100 * total_v / total_n:.1f}%" if total_n else "—")
    console.print(table)
