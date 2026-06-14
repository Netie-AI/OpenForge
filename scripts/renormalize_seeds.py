"""Re-normalize existing seeds_normalized.jsonl through Phase 2 converter (no re-fetch)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openanalog.config import SEEDS_NORMALIZED
from openanalog.ingestion.converter import normalize_for_forge, prepare_seed_deck
from openanalog.ingestion.dialect import detect_dialect, dialect_breakdown
from openanalog.ingestion.seed_loader import _print_dialect_report
from openanalog.sim.ngspice import check_syntax

console = Console()


def main() -> None:
    src = SEEDS_NORMALIZED
    if not src.exists():
        console.print(f"[red]Missing {src}[/red]")
        raise SystemExit(1)

    backup = src.with_suffix(".jsonl.bak")
    if not backup.exists():
        backup.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    records: list[dict] = []
    raw_dialects: list[str] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))

    sim_ok = 0
    with src.open("w", encoding="utf-8") as out:
        for rec in records:
            raw = rec.get("netlist", "")
            dialect = detect_dialect(raw)
            raw_dialects.append(raw)
            flat, warnings, _ = normalize_for_forge(raw)
            deck = prepare_seed_deck(flat)
            ok, msg = check_syntax(deck, timeout=5)
            if ok:
                sim_ok += 1
            rec["netlist"] = flat if dialect == "masala-paren" else raw
            rec["original_dialect"] = dialect
            rec["conversion_warnings"] = warnings + ([] if ok else [msg[:200]])
            rec["sim_validated"] = ok
            out.write(json.dumps(rec) + "\n")

    console.print(f"[green]Wrote {src}[/green] ({len(records)} seeds, sim_ok={sim_ok})")

    raw_breakdown = dialect_breakdown(raw_dialects)
    table = Table(title="Original dialect breakdown (pre-conversion)")
    table.add_column("dialect")
    table.add_column("count")
    for d, n in sorted(raw_breakdown.items()):
        table.add_row(d, str(n))
    console.print(table)

    _print_dialect_report(src)

    summary = Table(title="Renormalize summary")
    summary.add_column("metric")
    summary.add_column("value")
    summary.add_row("total", str(len(records)))
    summary.add_row("sim_validated", str(sim_ok))
    summary.add_row("pct", f"{100 * sim_ok / len(records):.1f}%")
    console.print(summary)


if __name__ == "__main__":
    main()
