from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from openanalog.config import PAPERS_INBOX, PDF_INBOX, TRAINING_DIR, ensure_dirs

app = typer.Typer(help="OpenAnalog: PDF to SPICE forge and train")
ingest_app = typer.Typer(help="PDF ingestion pipeline")
forge_app = typer.Typer(help="Simulation forge")
app.add_typer(ingest_app, name="ingest")


@ingest_app.callback(invoke_without_command=True)
def ingest_cmd(
    ctx: typer.Context,
    folder: Optional[Path] = typer.Option(None, "--folder", help="PDF inbox folder"),
    paper: Optional[Path] = typer.Option(None, "--paper", help="Single PDF"),
    status: bool = typer.Option(False, "--status", help="Show ingest progress"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse PDFs without Claude/ngspice"),
):
    from openanalog.ingestion.pdf_pipeline import run_ingest, ingest_status

    if status:
        ingest_status()
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        inbox = folder or (PDF_INBOX if PDF_INBOX.exists() else PAPERS_INBOX)
        run_ingest(folder=inbox, paper=paper, dry_run=dry_run)


@app.command("load-seeds")
def load_seeds(
    limit: int = typer.Option(500, help="Max spice-datasets netlists to validate"),
    analoggenie_limit: int = typer.Option(200, help="Max AnalogGenie circuits"),
    masala_limit: int = typer.Option(500, help="Max Masala-CHAI jsonl records"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip ngspice; just parse/count"),
):
    from openanalog.ingestion.seed_loader import load_all_seeds

    ensure_dirs()
    load_all_seeds(
        symbench_limit=limit,
        analoggenie_limit=analoggenie_limit,
        masala_limit=masala_limit,
        dry_run=dry_run,
    )


@forge_app.callback(invoke_without_command=True)
def forge_cmd(
    ctx: typer.Context,
    topology: Optional[str] = typer.Option(None, "--topology"),
    n: int = typer.Option(100, "--n"),
    all_topologies: bool = typer.Option(False, "--all"),
    status: bool = typer.Option(False, "--status"),
    workers: int = typer.Option(4, "--workers"),
    reset: bool = typer.Option(False, "--reset", help="Clear forge checkpoint and restart"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip ngspice simulations"),
    score_seeds: bool = typer.Option(True, "--score-seeds/--no-score-seeds", help="Score benchable seed netlists at forge start (Phase 2)"),
    seed_score_limit: int = typer.Option(25, "--seed-score-limit", help="Max seed netlists to score per forge run"),
):
    from openanalog.forge.runner import run_forge
    from openanalog.verify.dashboard import show_dashboard

    if status:
        show_dashboard()
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        run_forge(
            topology=topology,
            n=n,
            all_topologies=all_topologies,
            workers=workers,
            reset=reset,
            dry_run=dry_run,
            score_seeds=score_seeds,
            seed_score_limit=seed_score_limit,
        )


app.add_typer(forge_app, name="forge")


@app.command("design")
def design_cmd(
    datasheet: Optional[Path] = typer.Option(None, "--datasheet", help="Datasheet text/PDF file"),
    spec: Optional[str] = typer.Option(None, "--spec", help='Inline spec e.g. "type=comparator tp<1us vos<3mV iq<1uA"'),
    text: Optional[str] = typer.Option(None, "--text", help="Raw datasheet text or natural language"),
    category: Optional[str] = typer.Option(None, "--category", help="Circuit category override"),
    budget: int = typer.Option(200, "--budget", help="Sizing search evaluations"),
    use_claude: bool = typer.Option(False, "--use-claude", help="Use LLM for extraction"),
    use_llm: bool = typer.Option(False, "--use-llm", help="Use LLM for NL/datasheet parsing"),
    llm_provider: Optional[str] = typer.Option(None, "--llm-provider", help="LLM provider (openrouter, anthropic, groq)"),
    model_set: Optional[str] = typer.Option(None, "--model-set", help="bundled or sky130"),
    out: Optional[Path] = typer.Option(None, "--out", help="Write netlist to this .sp file"),
    sch_out: Optional[Path] = typer.Option(None, "--sch-out", help="Write KiCad schematic .kicad_sch"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Extract+show specs only, no sizing"),
):
    from rich.table import Table
    from openanalog.interface.designer import design
    from openanalog.interface.datasheet import parse_intent, parse_inline_spec

    ensure_dirs()
    src_text = text
    if datasheet and datasheet.exists():
        src_text = datasheet.read_text(encoding="utf-8", errors="ignore")

    use_llm_flag = use_llm or use_claude

    if dry_run:
        if spec:
            parsed = parse_inline_spec(spec, category=category)
        elif src_text:
            parsed = parse_intent(src_text, category=category, use_llm=use_llm_flag, provider=llm_provider)
        else:
            typer.echo("Provide --datasheet, --text, or --spec")
            raise typer.Exit(2)
        typer.echo(json.dumps(parsed, indent=2))
        raise typer.Exit()

    from rich.console import Console

    console = Console()
    result = design(
        text=src_text,
        inline_spec=spec,
        category=category,
        budget=budget,
        use_llm=use_llm_flag,
        llm_provider=llm_provider,
        model_set=model_set,
        progress=None,
    )

    sp = result["spec"]
    console.print(f"\n[bold]Part:[/bold] {sp.get('part','?')}  "
                  f"[bold]Category:[/bold] {result.get('category','?')}  "
                  f"[bold]Topology:[/bold] {result['topology']}  "
                  f"[bold]Package:[/bold] {result.get('package','?')}  "
                  f"[bold]Supply:[/bold] {result['supply_V']} V  "
                  f"[bold]Source:[/bold] {sp.get('source')}")
    if result.get("eda"):
        eda = result["eda"]
        console.print(f"[dim]KiCad: {eda.get('kicad_symbol')}  footprint: {eda.get('kicad_footprint')}[/dim]")
    table = Table(title="Spec compliance")
    table.add_column("spec")
    table.add_column("target")
    table.add_column("mode")
    table.add_column("measured")
    table.add_column("pass")
    for k, v in result["compliance"].items():
        meas = v["measured"]
        meas_s = f"{meas:.3f}" if isinstance(meas, (int, float)) else "n/a"
        if v["pass"] is None:
            status = "[dim]N/A[/dim]"
        elif v["pass"]:
            status = "[green]PASS[/green]"
        else:
            status = "[red]FAIL[/red]"
        table.add_row(k, str(v["target"]), v["mode"], meas_s, status)
    console.print(table)
    verdict = "[green]ALL SPECS MET[/green]" if result["meets_all"] else "[yellow]partial[/yellow]"
    console.print(f"Result: {verdict}  score={result['score']}")

    if out:
        out.write_text(result["netlist"], encoding="utf-8")
        console.print(f"[dim]netlist -> {out}[/dim]")
    if sch_out:
        sch_out.write_text(result.get("kicad_sch", ""), encoding="utf-8")
        console.print(f"[dim]schematic -> {sch_out}[/dim]")
    if not out:
        console.print("\n[bold]Netlist:[/bold]")
        console.print(result["netlist"])


@app.command("presets")
def presets_cmd(
    category: Optional[str] = typer.Option(None, "--category"),
):
    """List design presets (each is also a test case)."""
    from rich.table import Table
    from openanalog.presets import list_presets

    table = Table(title="OpenForge presets")
    table.add_column("id")
    table.add_column("name")
    table.add_column("category")
    table.add_column("expect_pass")
    table.add_column("spec")
    for p in list_presets(category=category):
        table.add_row(p.id, p.name, p.category, str(p.expect_pass), p.spec[:60])
    from rich.console import Console
    Console().print(table)


@app.command("test-presets")
def test_presets_cmd(
    preset_id: Optional[str] = typer.Option(None, "--preset", help="Run one preset only"),
    model_set: Optional[str] = typer.Option(None, "--model-set"),
):
    """Run preset verification against ngspice (Test & Verify)."""
    from rich.console import Console
    from rich.table import Table
    from openanalog.interface.designer import verify_preset
    from openanalog.presets import PRESETS, get_preset

    console = Console()
    targets = [get_preset(preset_id)] if preset_id else PRESETS
    targets = [p for p in targets if p is not None]
    if not targets:
        typer.echo(f"Unknown preset: {preset_id}")
        raise typer.Exit(1)

    table = Table(title="Preset verification")
    table.add_column("preset")
    table.add_column("expect")
    table.add_column("meets_all")
    table.add_column("result")
    failed = 0
    for p in targets:
        out = verify_preset(p.id, model_set=model_set)
        ok = out["passed"]
        if not ok:
            failed += 1
        table.add_row(
            p.name,
            str(p.expect_pass),
            str(out["meets_all"]),
            "[green]PASS[/green]" if ok else "[red]FAIL[/red]",
        )
    console.print(table)
    raise typer.Exit(1 if failed else 0)


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8080, "--port"),
):
    """Launch the OpenForge web EDA UI."""
    import uvicorn

    uvicorn.run("openanalog.web.app:app", host=host, port=port, reload=False)


@app.command("query")
def query_cmd(
    spec: str = typer.Argument(..., help='Natural language spec, e.g. "TIA BW>1MHz power<2mW"'),
    top: int = typer.Option(5, "--top", help="Number of results"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse spec only, no KG lookup"),
):
    from openanalog.forge.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.load()
    if dry_run:
        parsed = kg.parse_spec_query(spec)
        typer.echo(json.dumps(parsed, indent=2))
        raise typer.Exit()
    results = kg.query(spec, top=top)
    if not results:
        typer.echo("No matching KG nodes.")
        raise typer.Exit(1)
    for i, node in enumerate(results, 1):
        typer.echo(f"\n--- #{i} {node['id']} (score={node['score']:.3f}) ---")
        typer.echo(f"topology={node.get('topology')} tier={node.get('tier')}")
        stats = node.get("sim_stats") or {}
        typer.echo(
            f"  bw={stats.get('bw_MHz', '?')} MHz  gain={stats.get('gain_dB', '?')} dB  "
            f"power={stats.get('power_mW', '?')} mW  PM={stats.get('PM_deg', '?')} deg"
        )
        nl = node.get("netlist_template") or ""
        typer.echo(nl[:400] + ("..." if len(nl) > 400 else ""))


@app.command("status")
def status():
    from openanalog.verify.dashboard import show_dashboard

    show_dashboard()


@app.command("verify")
def verify(
    netlist: Path = typer.Argument(..., help="SPICE file to verify"),
    topology: str = typer.Option("tia", "--topology"),
    top: bool = typer.Option(False, "--top-performer", help="Run Claude L5 review"),
):
    from openanalog.verify.circuit_checker import verify_circuit

    text = netlist.read_text(encoding="utf-8")
    r = verify_circuit(text, topology, top_performer=top)
    typer.echo(f"passed={r.passed} confidence={r.confidence:.3f} tier={r.tier}")


@app.command("train")
def train(
    dataset: Optional[Path] = typer.Option(None, "--dataset"),
    epochs: int = typer.Option(1, "--epochs"),
):
    from openanalog.trainer.finetune import run_finetune

    path = dataset or TRAINING_DIR / "winners.jsonl"
    run_finetune(path, epochs=epochs)


def main():
    ensure_dirs()
    PAPERS_INBOX.mkdir(parents=True, exist_ok=True)
    app()


if __name__ == "__main__":
    main()
