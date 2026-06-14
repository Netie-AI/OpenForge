"""
openanalog/web/app.py

FastAPI web UI — backend-driven chat-to-chip interface.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from openanalog.config import MODEL_SET
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS, VREF_PHASE3_SPEC
from openanalog.forge.topologies import REGISTRY
from openanalog.interface.designer import design, verify_preset
from openanalog.llm import available_providers
from openanalog.presets import presets_payload

app = FastAPI(title="OpenForge EDA")

SAMPLES: dict[str, str] = {
    "opamp": """RS321/RS358 1.1MHz Rail-to-Rail I/O CMOS Operational Amplifier
SUPPLY RANGE: +2.2V to +5.5V  (test VS=5V)
GAIN-BANDWIDTH PRODUCT: 1.1 MHz
SLEW RATE: 0.5 V/us
PHASE MARGIN: 64 deg
AOL Open-Loop Voltage Gain: 95 100 dB (RL=10k)
IQ Quiescent Current Per Amplifier: 60 80 uA
""",
    "comparator": """RS8901 Low-Power Comparator
SUPPLY VS=5V
Propagation Delay: 0.8 us
Input Offset Voltage: 2.5 mV
Quiescent Current: 0.5 uA
""",
    "switch": """RS2105 Analog Switch
SUPPLY VS=5V
On-Resistance: 25 ohm
Bandwidth -3dB: 15 MHz
Turn-On Time: 12 ns  Turn-Off Time: 10 ns
""",
    "charge_pump": """RS2660 Charge Pump
SUPPLY VS=5V
Output Voltage: 5.0 V
Ripple: 30 mV
Settling Time: 3 ms
""",
    "vref": """RS431 Voltage Reference
SUPPLY VS=5V
Reference Voltage: 1.225 V
Line Regulation: 2 mV
Temperature Coefficient: 50 ppm/°C
""",
}

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
}


class DesignRequest(BaseModel):
    text: Optional[str] = None
    spec: Optional[str] = None
    category: Optional[str] = None
    budget: int = 200
    use_llm: bool = True
    use_claude: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    model_set: Optional[str] = None


class VerifyRequest(BaseModel):
    preset_id: str
    model_set: Optional[str] = None


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
    return {
        "categories": list(REGISTRY.keys()),
        "samples": SAMPLES,
        "inline_samples": {**DEV_MODE_SPECS, "vref": VREF_PHASE3_SPEC},
        "metric_labels": {
            k: {"label": v[0], "unit": v[1], "decimals": v[2]} for k, v in METRIC_LABELS.items()
        },
        "providers": [
            {"id": p.id, "label": p.label, "model": p.model, "available": p.available}
            for p in available_providers()
        ],
        "model_sets": ["bundled", "sky130"],
        "default_model_set": MODEL_SET,
        **presets_payload(),
    }


@app.get("/api/categories")
def categories() -> dict[str, Any]:
    return api_meta()


@app.get("/api/presets")
def api_presets() -> dict[str, Any]:
    return presets_payload()


@app.get("/api/sample")
def sample(category: str = "opamp") -> dict[str, str]:
    return {"category": category, "text": SAMPLES.get(category, SAMPLES["opamp"])}


@app.post("/api/design")
def api_design(req: DesignRequest) -> JSONResponse:
    global _last_result
    try:
        use_llm = req.use_llm or req.use_claude
        result = design(
            text=req.text,
            inline_spec=req.spec,
            category=req.category,
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
    try:
        out = verify_preset(req.preset_id, model_set=req.model_set)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


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


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>OpenForge — AI Analog EDA</title>
<style>
  :root{--bg:#0b0e14;--panel:#121722;--panel2:#0e131c;--line:#1e2636;--txt:#d6deeb;--dim:#8a97ad;--acc:#5ad1c9;--acc2:#7aa2ff;--ok:#3fd17a;--bad:#ff6b6b;--warn:#ffcc66;--mono:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace}
  *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#0a0d13,#0b0e14);color:var(--txt);font-family:Inter,system-ui,sans-serif;font-size:14px}
  header{display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--line);background:var(--panel2);position:sticky;top:0;z-index:5}
  .logo{font-weight:800;font-size:18px} .logo span{color:var(--acc)} .tag{color:var(--dim);font-size:12px}
  .wrap{display:grid;grid-template-columns:400px 1fr;gap:16px;padding:16px;max-width:1600px;margin:0 auto}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
  h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:var(--dim)}
  textarea{width:100%;height:220px;background:var(--panel2);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:10px;font-family:var(--mono);font-size:12px;resize:vertical}
  select,input[type=text]{background:var(--panel2);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 10px}
  .row{display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap}
  button{background:linear-gradient(180deg,var(--acc),#3bb4ab);color:#04221f;border:0;border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer}
  button.ghost{background:transparent;color:var(--acc2);border:1px solid var(--line);font-weight:600}
  button:disabled{opacity:.5;cursor:not-allowed}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:14px}
  .metric{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px}
  .metric .v{font-size:20px;font-weight:700;font-family:var(--mono)}
  .metric .l{color:var(--dim);font-size:11px;text-transform:uppercase}
  .metric.ok{border-color:rgba(63,209,122,.5)} .metric.bad{border-color:rgba(255,107,107,.5)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}
  th{color:var(--dim);font-size:11px;text-transform:uppercase}
  .badge{padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700}
  .badge.ok{background:rgba(63,209,122,.15);color:var(--ok)}
  .badge.bad{background:rgba(255,107,107,.15);color:var(--bad)}
  pre{background:#070a0f;border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;font-family:var(--mono);font-size:12px;max-height:420px}
  .verdict{font-size:15px;font-weight:800;padding:10px;border-radius:8px;margin-bottom:14px}
  .verdict.ok{background:rgba(63,209,122,.12);color:var(--ok);border:1px solid rgba(63,209,122,.4)}
  .verdict.partial{background:rgba(255,204,102,.10);color:var(--warn);border:1px solid rgba(255,204,102,.4)}
  .muted{color:var(--dim);font-size:12px}
  .tabs{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
  .tab{padding:6px 12px;border:1px solid var(--line);border-radius:6px;cursor:pointer;color:var(--dim);font-size:12px}
  .tab.active{color:var(--txt);border-color:var(--acc);background:var(--panel2)}
  .hidden{display:none}
  .sch-wrap{background:#070a0f;border:1px solid var(--line);border-radius:8px;padding:8px;max-height:480px;overflow:auto}
  .sch-wrap svg{max-width:100%;height:auto}
</style>
</head>
<body>
<header>
  <div class="logo">Open<span>Forge</span></div>
  <div class="tag">chat → spec → ngspice → netlist + schematic</div>
</header>
<div class="wrap">
  <div class="panel">
    <h3>Input</h3>
    <div class="row">
      <span class="muted">category</span>
      <select id="cat"></select>
    </div>
    <div class="row">
      <span class="muted">preset</span>
      <select id="preset"><option value="">— custom —</option></select>
    </div>
    <div class="row">
      <span class="muted">model</span>
      <select id="provider"></select>
      <select id="modelset"><option value="bundled">bundled</option><option value="sky130">sky130</option></select>
    </div>
    <textarea id="inp" placeholder="Natural language, inline spec, or datasheet text…"></textarea>
    <div class="row">
      <button class="ghost" id="btnSample">Load sample</button>
      <button class="ghost" id="btnInline">Inline spec</button>
      <label class="muted"><input type="checkbox" id="useLlm" checked/> LLM parse</label>
    </div>
    <div class="row">
      <span class="muted">budget</span>
      <input type="range" id="budget" min="40" max="400" step="20" value="200"/>
      <span class="mono" id="budgetv">200</span>
    </div>
    <div class="row">
      <button id="btnGo">Design Chip</button>
      <button class="ghost" id="btnVerify">Test &amp; Verify</button>
      <span id="status" class="muted"></span>
    </div>
  </div>
  <div class="panel">
    <h3>Result</h3>
    <div class="muted" id="placeholder">Run a design or verify a preset.</div>
    <div id="results" class="hidden">
      <div id="verdict" class="verdict"></div>
      <div class="metrics" id="metrics"></div>
      <div class="tabs">
        <div class="tab active" data-t="compliance">Compliance</div>
        <div class="tab" data-t="schematic">Schematic</div>
        <div class="tab" data-t="devices">Devices</div>
        <div class="tab" data-t="eda">KiCad</div>
        <div class="tab" data-t="netlist">Netlist</div>
      </div>
      <div id="tab-compliance"></div>
      <div id="tab-schematic" class="hidden"><div class="sch-wrap" id="sch"></div></div>
      <div id="tab-devices" class="hidden"></div>
      <div id="tab-eda" class="hidden"></div>
      <div id="tab-netlist" class="hidden">
        <div class="row">
          <button class="ghost" id="btnCopy">Copy</button>
          <button class="ghost" id="btnDl">Download .sp</button>
          <button class="ghost" id="btnKicad">Download .kicad_sch</button>
        </div>
        <pre id="netlist"></pre>
      </div>
    </div>
  </div>
</div>
<script>
const $=s=>document.querySelector(s);
let META={}, lastNetlist='', lastResult={};
const fmt=(v,d=2)=>v==null?'—':(typeof v==='number'?v.toFixed(d):v);

async function loadMeta(){
  const r=await fetch('/api/meta'); META=await r.json();
  $('#cat').innerHTML=META.categories.map(c=>`<option value="${c}">${c}</option>`).join('');
  $('#preset').innerHTML='<option value="">— custom —</option>'+
    META.presets.map(p=>`<option value="${p.id}">${p.name}${p.expect_pass?' ✓':''}</option>`).join('');
  $('#provider').innerHTML=META.providers.map(p=>
    `<option value="${p.id}" ${!p.available?'disabled':''}>${p.label}${p.available?'':' (no key)'}</option>`).join('');
  if(META.default_model_set) $('#modelset').value=META.default_model_set;
}
$('#budget').oninput=e=>$('#budgetv').textContent=e.target.value;
$('#preset').onchange=()=>{
  const id=$('#preset').value; if(!id)return;
  const p=META.presets.find(x=>x.id===id);
  if(p){$('#cat').value=p.category;$('#inp').value=p.spec;$('#budget').value=p.budget;$('#budgetv').textContent=p.budget;}
};
$('#btnSample').onclick=async()=>{
  const cat=$('#cat').value;
  const t=META.samples&&META.samples[cat]; if(t)$('#inp').value=t;
};
$('#btnInline').onclick=()=>{
  const cat=$('#cat').value;
  const t=META.inline_samples&&META.inline_samples[cat]; if(t)$('#inp').value=t;
};
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  ['compliance','schematic','devices','eda','netlist'].forEach(n=>$('#tab-'+n).classList.add('hidden'));
  $('#tab-'+t.dataset.t).classList.remove('hidden');
});

function metricCard(label,val,unit,pass){
  const cls=pass===true?'ok':pass===false?'bad':'';
  return `<div class="metric ${cls}"><div class="l">${label}</div><div class="v">${val}<span class="muted" style="font-size:11px"> ${unit||''}</span></div></div>`;
}

function render(j, svg){
  $('#placeholder').classList.add('hidden');
  $('#results').classList.remove('hidden');
  lastResult=j;
  const v=$('#verdict');
  v.className='verdict '+(j.meets_all?'ok':'partial');
  v.textContent=(j.meets_all?'✓ ALL SPECS MET':'◐ PARTIAL')+` · ${j.category||'?'} · ${j.topology||''} · ${j.supply_V}V · score ${j.score}`;
  const m=j.metrics||{}, c=j.compliance||{};
  const labels=META.metric_labels||{};
  const keys=j.measurable_specs||Object.keys(m).filter(k=>m[k]!=null);
  $('#metrics').innerHTML=keys.slice(0,6).map(k=>{
    const L=labels[k]||{label:k,unit:'',decimals:2};
    return metricCard(L.label,fmt(m[k],L.decimals),L.unit,c[k]?c[k].pass:undefined);
  }).join('');
  let rows='<table><tr><th>Spec</th><th>Target</th><th>Measured</th><th>Status</th></tr>';
  for(const k in c){const x=c[k];
    const cls=x.pass===null?'':x.pass?'ok':'bad';
    const lbl=x.pass===null?'N/A':x.pass?'PASS':'FAIL';
    rows+=`<tr><td>${k}</td><td>${x.target}</td><td>${fmt(x.measured,3)}</td><td><span class="badge ${cls}">${lbl}</span></td></tr>`;}
  rows+='</table>';
  $('#tab-compliance').innerHTML=rows;
  let dv='<table><tr><th>Device</th><th>Role</th><th>W</th><th>L</th><th>Value</th></tr>';
  (j.devices||[]).forEach(d=>{dv+=`<tr><td>${d.name}</td><td>${d.role||''}</td><td>${d.W_um??''}</td><td>${d.L_um??''}</td><td>${d.value??''}</td></tr>`;});
  $('#tab-devices').innerHTML=dv;
  const eda=j.eda||{};
  $('#tab-eda').innerHTML=`<table>
    <tr><th>Package</th><td>${j.package||eda.package||'—'}</td></tr>
    <tr><th>Symbol</th><td>${eda.kicad_symbol||'—'}</td></tr>
    <tr><th>Footprint</th><td>${eda.kicad_footprint||'—'}</td></tr>
    <tr><th>Model set</th><td>${j.model_set||'bundled'}</td></tr>
  </table>`;
  lastNetlist=j.netlist||'';
  $('#netlist').textContent=lastNetlist;
  if(svg) $('#sch').innerHTML=svg;
  else if(j.schematic_svg) $('#sch').innerHTML=j.schematic_svg;
}

async function runDesign(){
  const txt=$('#inp').value.trim();
  if(!txt){$('#status').textContent='enter text';return;}
  const isInline=/[<>=]/.test(txt)&&txt.length<200&&!/\n/.test(txt);
  const body={budget:+$('#budget').value,use_llm:$('#useLlm').checked,category:$('#cat').value,
    llm_provider:$('#provider').value,model_set:$('#modelset').value};
  if(isInline)body.spec=txt; else body.text=txt;
  $('#btnGo').disabled=true; $('#status').textContent='designing…';
  try{
    const r=await fetch('/api/design',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.error){$('#status').textContent='error: '+j.error;return;}
    let svg='';
    if(j.has_schematic){const sr=await fetch('/api/schematic.svg'); svg=await sr.text();}
    render(j,svg); $('#status').textContent='done';
  }catch(e){$('#status').textContent='error: '+e;}
  $('#btnGo').disabled=false;
}

async function runVerify(){
  const id=$('#preset').value;
  if(!id){$('#status').textContent='select a preset';return;}
  $('#btnVerify').disabled=true; $('#status').textContent='verifying…';
  try{
    const r=await fetch('/api/verify',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({preset_id:id,model_set:$('#modelset').value})});
    const j=await r.json();
    if(j.error){$('#status').textContent='error: '+j.error;return;}
    const v=$('#verdict');
    v.className='verdict '+(j.passed?'ok':'partial');
    v.textContent=(j.passed?'✓ PRESET PASS':'✗ PRESET FAIL')+` · ${j.preset_name} · meets_all=${j.meets_all} (expect ${j.expect_pass})`;
    $('#placeholder').classList.add('hidden'); $('#results').classList.remove('hidden');
    $('#tab-compliance').innerHTML=`<table><tr><th>Preset</th><td>${j.preset_name}</td></tr>
      <tr><th>Expected</th><td>${j.expect_pass}</td></tr><tr><th>Measured meets_all</th><td>${j.meets_all}</td></tr>
      <tr><th>Score</th><td>${j.score}</td></tr></table>`;
    const sr=await fetch('/api/schematic.svg?preset_id='+encodeURIComponent(id));
    if(sr.ok)$('#sch').innerHTML=await sr.text();
    $('#status').textContent=j.passed?'verify pass':'verify fail';
  }catch(e){$('#status').textContent='error: '+e;}
  $('#btnVerify').disabled=false;
}

$('#btnGo').onclick=runDesign;
$('#btnVerify').onclick=runVerify;
$('#btnCopy').onclick=()=>navigator.clipboard.writeText(lastNetlist);
$('#btnDl').onclick=()=>window.open('/api/netlist','_blank');
$('#btnKicad').onclick=()=>window.open('/api/kicad_sch','_blank');
loadMeta();
</script>
</body>
</html>
"""
