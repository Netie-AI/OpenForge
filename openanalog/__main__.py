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
        )


app.add_typer(forge_app, name="forge")


@app.command("design")
def design_cmd(
    datasheet: Optional[Path] = typer.Option(None, "--datasheet", help="Datasheet text/PDF file"),
    spec: Optional[str] = typer.Option(None, "--spec", help='Inline spec e.g. "type=comparator tp<1us vos<3mV iq<1uA"'),
    text: Optional[str] = typer.Option(None, "--text", help="Raw datasheet text"),
    category: Optional[str] = typer.Option(None, "--category", help="Circuit category override (opamp, comparator, switch, charge_pump, vref)"),
    budget: int = typer.Option(200, "--budget", help="Sizing search evaluations"),
    use_claude: bool = typer.Option(False, "--use-claude", help="Use Claude for datasheet extraction"),
    out: Optional[Path] = typer.Option(None, "--out", help="Write netlist to this .sp file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Extract+show specs only, no sizing"),
):
    from rich.table import Table
    from openanalog.interface.designer import design
    from openanalog.interface.datasheet import extract_specs, parse_inline_spec

    ensure_dirs()
    src_text = text
    if datasheet and datasheet.exists():
        src_text = datasheet.read_text(encoding="utf-8", errors="ignore")

    if dry_run:
        if spec:
            parsed = parse_inline_spec(spec, category=category)
        elif src_text:
            parsed = extract_specs(src_text, use_claude=use_claude, category=category)
        else:
            typer.echo("Provide --datasheet, --text, or --spec")
            raise typer.Exit(2)
        typer.echo(json.dumps(parsed, indent=2))
        raise typer.Exit()

    from rich.console import Console
    from rich.progress import Progress

    console = Console()
    cat_label = category or "auto"
    with Progress(console=console) as prog:
        task = prog.add_task(f"Sizing ({cat_label})", total=budget)

        def cb(i, total, best):
            prog.update(task, completed=i, description=f"Sizing ({cat_label}) best={best:.3f}")

        result = design(
            text=src_text,
            inline_spec=spec,
            category=category,
            budget=budget,
            use_claude=use_claude,
            progress=cb,
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
    else:
        console.print("\n[bold]Netlist:[/bold]")
        console.print(result["netlist"])


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
