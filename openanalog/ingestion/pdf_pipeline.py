from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from openanalog import claude
from openanalog.confidence import decide, should_write_kg_seed, record_flags
from openanalog.config import (
    CHECKPOINT,
    KG_SEEDS,
    NGSPICE_TIMEOUT,
    PAPERS_INBOX,
    PAPERS_PROCESSED,
    PDF_INBOX,
    ensure_dirs,
    resolve_ngspice_cmd,
)

console = Console()


def _slug(pdf: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "_", pdf.stem.lower()).strip("_")


def _load_checkpoint() -> dict[str, Any]:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {"papers_done": [], "stats": {"papers": 0, "schematics": 0, "validated": 0, "kg_seeds": 0}}


def _save_checkpoint(cp: dict[str, Any]) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(cp, indent=2), encoding="utf-8")


def _convert_pdf_marker(pdf_path: Path, out_dir: Path) -> tuple[str, list[Path], dict[str, Any]]:
    try:
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
    except ImportError as e:
        raise RuntimeError("Install ingest extras: pip install -e '.[ingest]'") from e

    models = load_all_models()
    full_text, images, metadata = convert_single_pdf(str(pdf_path), models)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "images"
    img_dir.mkdir(exist_ok=True)
    paths: list[Path] = []
    for i, img in enumerate(images or []):
        dest = img_dir / f"fig_{i + 1:03d}.png"
        if hasattr(img, "save"):
            img.save(dest)
        elif isinstance(img, (str, Path)):
            shutil.copy(img, dest)
        paths.append(dest)
    md_path = out_dir / "full_text.md"
    md_path.write_text(full_text or "", encoding="utf-8")
    meta_path = out_dir / "metadata.json"
    meta = metadata if isinstance(metadata, dict) else {"source": pdf_path.name}
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return full_text or "", paths, meta


def _heuristic_classify_image(image_path: Path) -> dict[str, Any]:
    """Method A: fast rule-based schematic detection before Claude vision."""
    result: dict[str, Any] = {
        "is_schematic": None,
        "confidence": 0.0,
        "circuit_type": "unknown",
        "method": "A",
    }
    try:
        from PIL import Image
    except ImportError:
        return result

    try:
        img = Image.open(image_path).convert("L")
    except OSError:
        return result

    w, h = img.size
    if h == 0 or w == 0:
        return result
    aspect = w / h
    if not (0.3 <= aspect <= 3.0):
        result.update({"is_schematic": False, "confidence": 0.25})
        return result

    pixels = list(img.getdata())
    light = sum(1 for p in pixels if p > 200) / len(pixels)
    dark = sum(1 for p in pixels if p < 80) / len(pixels)
    mid = 1.0 - light - dark

    # Schematics: light background, sparse dark ink lines
    if light < 0.45:
        result.update({"is_schematic": False, "confidence": 0.35})
        return result
    if dark > 0.35:
        result.update({"is_schematic": False, "confidence": 0.4})
        return result
    if 0.02 <= dark <= 0.18 and light >= 0.55:
        conf = min(0.92, 0.55 + light * 0.3 + mid * 0.1)
        result.update({"is_schematic": True, "confidence": conf})
        return result
    result.update({"is_schematic": None, "confidence": 0.55})
    return result


def _validate_spice(netlist_path: Path) -> tuple[bool, str]:
    cmd = resolve_ngspice_cmd()
    if not cmd:
        return False, "ngspice not installed"
    try:
        r = subprocess.run(
            [*cmd, "-b", str(netlist_path)],
            capture_output=True,
            text=True,
            timeout=NGSPICE_TIMEOUT,
        )
        ok = r.returncode == 0
        err = (r.stderr or r.stdout or "")[:2000]
        return ok, err
    except subprocess.TimeoutExpired:
        return False, "ngspice timeout"


def _sina_confidence(_image: Path) -> float:
    """Placeholder until SINA weights are installed; triggers Claude fallback."""
    return 0.0


def _context_around_marker(md: str, marker: str, window: int = 800) -> str:
    idx = md.find(marker)
    if idx < 0:
        return md[: window * 4]
    start = max(0, idx - window * 4)
    end = min(len(md), idx + window * 4)
    return md[start:end]


def _append_kg_seed(record: dict[str, Any]) -> None:
    KG_SEEDS.parent.mkdir(parents=True, exist_ok=True)
    with KG_SEEDS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def process_paper(pdf_path: Path, cp: dict[str, Any], *, dry_run: bool = False) -> None:
    slug = _slug(pdf_path)
    out_dir = PAPERS_PROCESSED / slug
    sch_dir = out_dir / "schematics"
    sch_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        t = progress.add_task(f"Converting {pdf_path.name}", total=6)

        full_text, images, meta = _convert_pdf_marker(pdf_path, out_dir)
        progress.advance(t)

        schematics_found = 0
        validated = 0
        kg_written = 0
        md = full_text

        for i, img_path in enumerate(images):
            fig = f"fig_{i + 1:03d}"
            progress.update(t, description=f"Classify {fig}")

            heur = _heuristic_classify_image(img_path)
            cls: dict[str, Any]
            if heur.get("is_schematic") is False and float(heur.get("confidence", 0)) >= 0.7:
                progress.advance(t)
                continue
            if dry_run:
                cls = heur if heur.get("is_schematic") is not None else {
                    "is_schematic": True,
                    "confidence": 0.5,
                    "circuit_type": "unknown",
                }
            elif heur.get("is_schematic") is True and float(heur.get("confidence", 0)) >= 0.85:
                cls = heur
            else:
                try:
                    cls = claude.classify_schematic(img_path)
                except RuntimeError as e:
                    console.print(f"[yellow]Claude skip ({fig}): {e}[/yellow]")
                    progress.advance(t)
                    continue
                if heur.get("confidence"):
                    cls["heuristic_confidence"] = heur["confidence"]

            conf = float(cls.get("confidence", 0))
            is_sch = bool(cls.get("is_schematic", False))
            d = decide(conf)

            if d.needs_claude and is_sch and not dry_run:
                rev = claude.reexamine_ambiguous(
                    "schematic classification",
                    cls,
                    image_path=img_path,
                )
                if rev.get("accept"):
                    conf = float(rev.get("confidence", conf))
                    cls = rev.get("revised", cls) if isinstance(rev.get("revised"), dict) else cls
                    is_sch = bool(cls.get("is_schematic", is_sch))
                d = decide(conf)

            if not (is_sch and conf > 0.7):
                continue

            schematics_found += 1
            dest = sch_dir / f"{fig}.png"
            shutil.copy(img_path, dest)
            ctype = str(cls.get("circuit_type", "unknown"))
            marker = f"<!-- SCHEMATIC: {fig} | type: {ctype} | confidence: {conf:.2f} -->"
            md += f"\n{marker}\n"
            (out_dir / "full_text.md").write_text(md, encoding="utf-8")

            ctx = _context_around_marker(md, marker)
            (sch_dir / f"{fig}_context.json").write_text(
                json.dumps({"context_text": ctx, "window_tokens": 800}, indent=2),
                encoding="utf-8",
            )
            if dry_run:
                schematics_found += 1
                progress.advance(t)
                continue
            try:
                params = claude.extract_nearby_params(ctx)
            except RuntimeError:
                params = {"params": {}, "specs": {}}
            (sch_dir / f"{fig}_params.json").write_text(
                json.dumps(params, indent=2), encoding="utf-8"
            )

            sina_c = _sina_confidence(dest)
            netlist = ""
            extract_conf = sina_c
            if sina_c < 0.7:
                try:
                    netlist = claude.schematic_to_spice(dest)
                    extract_conf = max(sina_c, 0.75)
                except RuntimeError as e:
                    console.print(f"[red]SPICE extract failed {fig}: {e}[/red]")
                    continue

            sp_path = sch_dir / f"{fig}.sp"
            sp_path.write_text(netlist, encoding="utf-8")
            (sch_dir / f"{fig}_confidence.json").write_text(
                json.dumps({"sina": sina_c, "extraction": extract_conf}, indent=2),
                encoding="utf-8",
            )

            sim_ok, sim_err = _validate_spice(sp_path)
            status = "validated" if sim_ok else "extraction_failed"
            (sch_dir / f"{fig}_status.json").write_text(
                json.dumps({"status": status, "error": sim_err if not sim_ok else ""}),
                encoding="utf-8",
            )
            if sim_ok:
                validated += 1

            final_conf = min(conf, extract_conf)
            if d.needs_claude or 0.5 <= final_conf < 0.7:
                rev2 = claude.reexamine_ambiguous(
                    "netlist extraction quality",
                    {"classification": cls, "netlist_preview": netlist[:1500], "sim_validated": sim_ok},
                    image_path=dest,
                )
                if rev2.get("accept"):
                    final_conf = float(rev2.get("confidence", final_conf))

            if should_write_kg_seed(final_conf, sim_ok):
                rec = {
                    "source": "paper",
                    "paper": slug,
                    "figure": fig,
                    "circuit_type": ctype,
                    "netlist": netlist,
                    "params": params.get("params", {}),
                    "specs": params.get("specs", {}),
                    "extraction_confidence": final_conf,
                    "sim_validated": sim_ok,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **record_flags(final_conf),
                }
                _append_kg_seed(rec)
                kg_written += 1

        progress.advance(t, advance=6 - progress.tasks[t].completed)

    cp["papers_done"].append(slug)
    st = cp["stats"]
    st["papers"] = len(cp["papers_done"])
    st["schematics"] = st.get("schematics", 0) + schematics_found
    st["validated"] = st.get("validated", 0) + validated
    st["kg_seeds"] = st.get("kg_seeds", 0) + kg_written
    _save_checkpoint(cp)
    console.print(
        f"[green]{slug}[/green]: schematics={schematics_found} validated={validated} kg={kg_written}"
    )


def run_ingest(*, folder: Path | None = None, paper: Path | None = None, dry_run: bool = False) -> None:
    ensure_dirs()
    PAPERS_INBOX.mkdir(parents=True, exist_ok=True)
    cp = _load_checkpoint()

    if paper:
        pdfs = [paper]
    else:
        root = folder or (PDF_INBOX if PDF_INBOX.exists() else PAPERS_INBOX)
        pdfs = sorted(root.glob("*.pdf"))

    if not pdfs:
        inbox = folder or PDF_INBOX if PDF_INBOX.exists() else PAPERS_INBOX
        console.print(f"[yellow]No PDFs in {inbox}[/yellow]")
        return

    for pdf in pdfs:
        if _slug(pdf) in cp.get("papers_done", []):
            console.print(f"[dim]Skip done: {pdf.name}[/dim]")
            continue
        process_paper(pdf, cp, dry_run=dry_run)
        cp = _load_checkpoint()


def ingest_status() -> None:
    cp = _load_checkpoint()
    st = cp.get("stats", {})
    console.print(
        f"Papers: {st.get('papers', 0)} | Schematics: {st.get('schematics', 0)} | "
        f"Validated: {st.get('validated', 0)} | KG seeds: {st.get('kg_seeds', 0)}"
    )
