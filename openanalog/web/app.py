"""
openanalog/web/app.py

FastAPI web UI — backend-driven chat-to-chip interface.

Stack: FastAPI serves a single vanilla HTML/JS page from index.html (no SPA framework).
"""

from __future__ import annotations

import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from openanalog.config import MODEL_SET, ROOT
from openanalog.corpus_stats import achievable_ranges_payload
from openanalog.product_line import PRODUCT_LINE, get_product, product_line_payload
from openanalog.interface.designer import design, verify_preset
from openanalog.llm import available_providers
from openanalog.presets import PRESETS, presets_payload
from openanalog.use_cases import use_cases_payload

app = FastAPI(title="OpenForge EDA")

_test_suite_lock = threading.Lock()
_test_suite_state: dict[str, Any] = {
    "running": False,
    "results": [],
    "started_at": None,
    "finished_at": None,
    "model_set": None,
    "error": None,
}


def _git_short_hash() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def _build_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

SAMPLES: dict[str, str] = {p.id: p.sample for p in PRODUCT_LINE if p.sample}
# Topology-keyed samples for backward compat
for p in PRODUCT_LINE:
    if p.topology and p.topology not in SAMPLES:
        SAMPLES[p.topology] = p.sample

INLINE_SAMPLES: dict[str, str] = {p.id: p.inline_spec for p in PRODUCT_LINE}
for p in PRODUCT_LINE:
    if p.topology and p.topology not in INLINE_SAMPLES:
        INLINE_SAMPLES[p.topology] = p.inline_spec

METRIC_LABELS: dict[str, tuple[str, str, int]] = {
    "aol_dB": ("AOL", "dB", 1),
    "gbp_MHz": ("GBP", "MHz", 3),
    "pm_deg": ("Phase margin", "°", 1),
    "iq_uA": ("Iq", "µA", 1),
    "slew_Vus": ("Slew", "V/µs", 2),
    "tp_us": ("Delay", "µs", 2),
    "vos_mV": ("Vos", "mV", 2),
    "trise_ns": ("Rise", "ns", 1),
    "tfall_ns": ("Fall", "ns", 1),
    "ron_ohm": ("RON", "Ω", 1),
    "bw_MHz": ("BW", "MHz", 1),
    "ton_ns": ("tON", "ns", 1),
    "toff_ns": ("tOFF", "ns", 1),
    "vout_V": ("Vout", "V", 2),
    "ripple_mV": ("Ripple", "mV", 1),
    "settle_ms": ("Settle", "ms", 2),
    "iout_mA": ("Iout", "mA", 2),
    "vref_V": ("Vref", "V", 3),
    "line_reg_mV": ("Line reg", "mV", 2),
    "tempco_ppm": ("Tempco", "ppm", 0),
    "gain_err_pct": ("Gain err", "%", 1),
    "output_swing_V": ("Out swing", "V", 3),
}


class DesignRequest(BaseModel):
    text: Optional[str] = None
    spec: Optional[str] = None
    category: Optional[str] = None
    product_id: Optional[str] = None
    budget: int = 200
    use_llm: bool = True
    use_claude: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    model_set: Optional[str] = None


class VerifyRequest(BaseModel):
    preset_id: str
    model_set: Optional[str] = None


class EditRequest(BaseModel):
    instruction: str
    current_netlist: str = ""


_last_result: dict[str, Any] = {}


def _slim_result(result: dict[str, Any]) -> dict[str, Any]:
    """API payload — omit huge fields from design response (fetch separately)."""
    slim = dict(result)
    slim.pop("kicad_sym_stub", None)
    if "schematic_svg" in slim and len(slim.get("schematic_svg", "")) > 500:
        slim["has_schematic"] = True
        slim.pop("schematic_svg", None)
    if "kicad_sch" in slim and len(slim.get("kicad_sch", "")) > 500:
        slim["has_kicad_sch"] = True
        slim.pop("kicad_sch", None)
    return slim


@app.get("/api/meta")
def api_meta() -> dict[str, Any]:
    from openanalog.forge.topologies import REGISTRY

    return {
        "categories": list(REGISTRY.keys()),
        "product_line": product_line_payload(),
        "samples": SAMPLES,
        "inline_samples": INLINE_SAMPLES,
        "metric_labels": {
            k: {"label": v[0], "unit": v[1], "decimals": v[2]} for k, v in METRIC_LABELS.items()
        },
        "providers": [
            {"id": p.id, "label": p.label, "model": p.model, "available": p.available}
            for p in available_providers()
        ],
        "model_sets": ["bundled", "sky130"],
        "default_model_set": MODEL_SET,
        "achievable_ranges": achievable_ranges_payload(),
        **use_cases_payload(),
        "version": {
            "git_hash": _git_short_hash(),
            "build_date": _build_date(),
            "pdk_mode": MODEL_SET,
        },
        **presets_payload(),
    }


@app.get("/api/categories")
def categories() -> dict[str, Any]:
    return api_meta()


@app.get("/api/presets")
def api_presets() -> dict[str, Any]:
    return presets_payload()


@app.get("/api/sample")
def sample(category: str = "opamp", product_id: str | None = None) -> dict[str, str]:
    if product_id:
        p = get_product(product_id)
        if p:
            return {"category": p.topology or p.id, "product_id": p.id, "text": p.sample}
    return {"category": category, "text": SAMPLES.get(category, SAMPLES.get("opamp", ""))}


@app.post("/api/design")
def api_design(req: DesignRequest) -> JSONResponse:
    global _last_result
    try:
        use_llm = req.use_llm or req.use_claude
        result = design(
            text=req.text,
            inline_spec=req.spec,
            category=req.category,
            product_id=req.product_id,
            budget=max(20, min(req.budget, 600)),
            use_llm=use_llm,
            llm_provider=req.llm_provider,
            llm_model=req.llm_model,
            model_set=req.model_set,
            progress=None,
        )
        _last_result = result
        return JSONResponse(_slim_result(result))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/verify")
def api_verify(req: VerifyRequest) -> JSONResponse:
    global _last_result
    try:
        out = verify_preset(req.preset_id, model_set=req.model_set)
        # Re-run design so schematic/kicad endpoints have payload
        from openanalog.presets import get_preset

        p = get_preset(req.preset_id)
        if p:
            _last_result = design(
                inline_spec=p.spec,
                category=p.category,
                budget=p.budget,
                seed=p.seed,
                use_llm=False,
                model_set=req.model_set,
                record_kg=False,
            )
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


def _run_test_suite(model_set: str | None) -> None:
    global _test_suite_state
    results: list[dict[str, Any]] = []
    try:
        for p in PRESETS:
            out = verify_preset(p.id, model_set=model_set)
            row = {
                "preset_id": p.id,
                "preset_name": p.name,
                "category": p.category,
                "expect_pass": p.expect_pass,
                "passed": out["passed"],
                "meets_all": out["meets_all"],
                "score": out["score"],
                "compliance": out.get("compliance", {}),
                "model_set": out.get("model_set", model_set or MODEL_SET),
            }
            results.append(row)
        with _test_suite_lock:
            _test_suite_state["results"] = results
            _test_suite_state["running"] = False
            _test_suite_state["finished_at"] = datetime.now(timezone.utc).isoformat()
            _test_suite_state["error"] = None
    except Exception as e:
        with _test_suite_lock:
            _test_suite_state["running"] = False
            _test_suite_state["error"] = str(e)
            _test_suite_state["finished_at"] = datetime.now(timezone.utc).isoformat()


class TestSuiteRequest(BaseModel):
    model_set: Optional[str] = None


@app.get("/api/test-presets")
def api_test_presets_status() -> dict[str, Any]:
    with _test_suite_lock:
        return dict(_test_suite_state)


@app.post("/api/test-presets")
def api_test_presets_run(req: TestSuiteRequest) -> JSONResponse:
    global _test_suite_state
    with _test_suite_lock:
        if _test_suite_state["running"]:
            return JSONResponse({"error": "test suite already running"}, status_code=409)
        _test_suite_state = {
            "running": True,
            "results": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "model_set": req.model_set or MODEL_SET,
            "error": None,
        }
    threading.Thread(
        target=_run_test_suite,
        args=(req.model_set,),
        daemon=True,
    ).start()
    return JSONResponse({"started": True, "preset_count": len(PRESETS)})


@app.get("/api/schematic.svg")
def api_schematic_svg(preset_id: str | None = Query(None)) -> Response:
    if preset_id:
        try:
            out = verify_preset(preset_id)
            from openanalog.presets import get_preset
            from openanalog.eda.schematic import render_svg

            p = get_preset(preset_id)
            if not p:
                return Response(content="unknown preset", status_code=404)
            r = design(inline_spec=p.spec, category=p.category, budget=p.budget, seed=p.seed, record_kg=False)
            svg = r.get("schematic_svg") or render_svg(r)
        except Exception as e:
            return Response(content=str(e), status_code=400)
    elif _last_result.get("schematic_svg"):
        svg = _last_result["schematic_svg"]
    else:
        return Response(content="no design yet", status_code=404)
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/kicad_sch")
def api_kicad_sch() -> Response:
    if not _last_result.get("kicad_sch"):
        return Response(content="no design yet", status_code=404)
    name = (_last_result.get("eda") or {}).get("design_id", "openforge")
    return Response(
        content=_last_result["kicad_sch"],
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}.kicad_sch"'},
    )


@app.get("/api/netlist")
def api_netlist() -> Response:
    if not _last_result.get("netlist"):
        return Response(content="no design yet", status_code=404)
    cat = _last_result.get("category", "design")
    return Response(
        content=_last_result["netlist"],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="openforge_{cat}.sp"'},
    )


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    from openanalog.config import probe_ngspice, resolve_ngspice_cmd

    cmd = resolve_ngspice_cmd()
    ok, detail = probe_ngspice()
    return {
        "status": "ok" if ok else "degraded",
        "ngspice_available": ok,
        "ngspice_cmd": cmd,
        "ngspice_probe": detail,
        "version": _git_short_hash(),
    }


@app.get("/api/products")
def api_products() -> dict[str, Any]:
    return product_line_payload()


@app.post("/api/edit")
def api_edit(req: EditRequest) -> JSONResponse:
    return JSONResponse(
        {
            "applied": False,
            "status": "not_implemented",
            "instruction": req.instruction,
            "netlist": None,
            "classification": None,
            "diff": None,
            "note": "edit engine not wired yet",
        }
    )


@app.get("/api/drc-lvs")
def api_drc_lvs() -> dict[str, Any]:
    return {"status": "not_implemented", "drc": None, "lvs": None}


@app.get("/api/last-design")
def api_last_design() -> JSONResponse:
    if not _last_result:
        return JSONResponse({"error": "no design yet"}, status_code=404)
    return JSONResponse(_slim_result(_last_result))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


_WEB_DIR = Path(__file__).parent
INDEX_HTML = (_WEB_DIR / "index.html").read_text(encoding="utf-8")
