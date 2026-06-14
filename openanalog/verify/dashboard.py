from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openanalog.config import TRAINING_DIR
from openanalog.forge.knowledge_graph import KnowledgeGraph
from openanalog.forge.runner import forge_status

console = Console()


def _count_jsonl(path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def show_dashboard() -> None:
    stats = forge_status()
    kg = KnowledgeGraph()
    kg.load()
    ks = kg.stats()
    winners = _count_jsonl(TRAINING_DIR / "winners.jsonl")
    sims = stats.get("sims", 0)
    w = stats.get("winners", 0)
    rate = f"{100 * w / sims:.1f}%" if sims else "—"

    table = Table(title="OpenAnalog Forge — Live Status", show_header=True)
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Sims run", str(sims))
    table.add_row("Winners (1)", f"{w} ({rate})")
    table.add_row("KG nodes", f"{ks['live']} live / {ks['archived']} archived")
    table.add_row("Training records", str(winners))

    topo_table = Table(title="Per topology")
    topo_table.add_column("topology")
    topo_table.add_column("sims")
    topo_table.add_column("winners")
    topo_table.add_column("pass_rate")
    for topo, bt in sorted(stats.get("by_topology", {}).items()):
        s = bt.get("sims", 0)
        ww = bt.get("winners", 0)
        pr = f"{100 * ww / s:.1f}%" if s else "—"
        topo_table.add_row(topo, str(s), str(ww), pr)

    console.print(Panel(table))
    console.print(topo_table)
