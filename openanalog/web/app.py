"""
openanalog/web/app.py

FastAPI web UI: paste a datasheet (or inline spec), OpenForge extracts specs,
sizes the circuit on ngspice, and renders compliance + netlist + KiCad hints.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS, VREF_PHASE3_SPEC
from openanalog.forge.topologies import REGISTRY
from openanalog.interface.designer import design

app = FastAPI(title="OpenForge EDA")

SAMPLES: dict[str, str] = {
    "opamp": """RS321/RS358 1.1MHz Rail-to-Rail I/O CMOS Operational Amplifier
SUPPLY RANGE: +2.2V to +5.5V  (test VS=5V)
GAIN-BANDWIDTH PRODUCT: 1.1 MHz
SLEW RATE: 0.5 V/us
PHASE MARGIN: 64 deg
AOL Open-Loop Voltage Gain: 95 100 dB (RL=10k)
IQ Quiescent Current Per Amplifier: 60 80 uA
CMRR Common-Mode Rejection Ratio: 80 dB
VOS Input Offset Voltage: 0.8 mV
""",
    "comparator": """RS8901 Low-Power Comparator
SUPPLY VS=5V
Propagation Delay: 0.8 us
Input Offset Voltage: 2.5 mV
Quiescent Current: 0.5 uA
Rise Time: 50 ns  Fall Time: 45 ns
""",
    "switch": """RS2105 Analog Switch
SUPPLY VS=5V
On-Resistance: 25 ohm
Bandwidth -3dB: 15 MHz
Turn-On Time: 12 ns  Turn-Off Time: 10 ns
Quiescent Current: 0.1 uA
""",
    "charge_pump": """RS2660 Charge Pump
SUPPLY VS=5V
Output Voltage: 5.0 V
Ripple: 30 mV
Settling Time: 3 ms
Output Current: 10 mA
""",
    "vref": """RS431 Voltage Reference
SUPPLY VS=5V
Reference Voltage: 1.225 V
Line Regulation: 2 mV
Temperature Coefficient: 50 ppm/°C
Quiescent Current: 60 uA
""",
}

INLINE_SAMPLES: dict[str, str] = {**DEV_MODE_SPECS, "vref": VREF_PHASE3_SPEC}

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
    use_claude: bool = False


@app.get("/api/categories")
def categories() -> dict[str, Any]:
    return {
        "categories": list(REGISTRY.keys()),
        "samples": list(SAMPLES.keys()),
        "inline_samples": INLINE_SAMPLES,
    }


@app.get("/api/sample")
def sample(category: str = "opamp") -> dict[str, str]:
    return {"category": category, "text": SAMPLES.get(category, SAMPLES["opamp"])}


@app.post("/api/design")
def api_design(req: DesignRequest) -> JSONResponse:
    try:
        result: dict[str, Any] = design(
            text=req.text,
            inline_spec=req.spec,
            category=req.category,
            budget=max(20, min(req.budget, 600)),
            use_claude=req.use_claude,
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


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
  :root{
    --bg:#0b0e14; --panel:#121722; --panel2:#0e131c; --line:#1e2636;
    --txt:#d6deeb; --dim:#8a97ad; --acc:#5ad1c9; --acc2:#7aa2ff;
    --ok:#3fd17a; --bad:#ff6b6b; --warn:#ffcc66; --mono:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box}
  body{margin:0;background:linear-gradient(180deg,#0a0d13,#0b0e14);color:var(--txt);
    font-family:Inter,system-ui,Segoe UI,sans-serif;font-size:14px}
  header{display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--line);
    background:var(--panel2);position:sticky;top:0;z-index:5}
  .logo{font-weight:800;letter-spacing:.5px;font-size:18px}
  .logo span{color:var(--acc)}
  .tag{color:var(--dim);font-size:12px}
  .wrap{display:grid;grid-template-columns:380px 1fr;gap:16px;padding:16px;max-width:1500px;margin:0 auto}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
  h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:var(--dim)}
  textarea{width:100%;height:280px;background:var(--panel2);color:var(--txt);border:1px solid var(--line);
    border-radius:8px;padding:10px;font-family:var(--mono);font-size:12px;resize:vertical}
  select{background:var(--panel2);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 10px}
  .row{display:flex;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap}
  button{background:linear-gradient(180deg,var(--acc),#3bb4ab);color:#04221f;border:0;border-radius:8px;
    padding:10px 16px;font-weight:700;cursor:pointer;font-size:14px}
  button.ghost{background:transparent;color:var(--acc2);border:1px solid var(--line);font-weight:600}
  button:disabled{opacity:.5;cursor:not-allowed}
  input[type=range]{flex:1}
  .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:14px}
  .metric{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px}
  .metric .v{font-size:22px;font-weight:700;font-family:var(--mono)}
  .metric .l{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
  .metric.ok{border-color:rgba(63,209,122,.5)} .metric.bad{border-color:rgba(255,107,107,.5)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
  th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase}
  td.mono,.mono{font-family:var(--mono)}
  .badge{padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700}
  .badge.ok{background:rgba(63,209,122,.15);color:var(--ok)}
  .badge.bad{background:rgba(255,107,107,.15);color:var(--bad)}
  .badge.na{background:rgba(138,151,173,.15);color:var(--dim)}
  pre{background:#070a0f;border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;
    font-family:var(--mono);font-size:12px;line-height:1.5;max-height:520px}
  .verdict{font-size:16px;font-weight:800;padding:10px 14px;border-radius:8px;margin-bottom:14px}
  .verdict.ok{background:rgba(63,209,122,.12);color:var(--ok);border:1px solid rgba(63,209,122,.4)}
  .verdict.partial{background:rgba(255,204,102,.10);color:var(--warn);border:1px solid rgba(255,204,102,.4)}
  .muted{color:var(--dim);font-size:12px}
  .spin{display:inline-block;width:14px;height:14px;border:2px solid #04221f;border-top-color:transparent;
    border-radius:50%;animation:s .7s linear infinite;vertical-align:-2px;margin-right:6px}
  @keyframes s{to{transform:rotate(360deg)}}
  .tabs{display:flex;gap:6px;margin-bottom:10px}
  .tab{padding:6px 12px;border:1px solid var(--line);border-radius:6px;cursor:pointer;color:var(--dim);font-size:12px}
  .tab.active{color:var(--txt);border-color:var(--acc);background:var(--panel2)}
  .hidden{display:none}
</style>
</head>
<body>
<header>
  <div class="logo">Open<span>Forge</span></div>
  <div class="tag">AI Analog EDA · multi-category · ngspice-validated</div>
</header>

<div class="wrap">
  <div class="panel">
    <h3>1 · Input</h3>
    <div class="row">
      <span class="muted">category</span>
      <select id="cat">
        <option value="opamp">op-amp</option>
        <option value="comparator">comparator</option>
        <option value="switch">analog switch</option>
        <option value="charge_pump">charge pump</option>
        <option value="vref">voltage reference</option>
      </select>
    </div>
    <div class="muted" style="margin-top:8px">Paste a datasheet or inline spec</div>
    <textarea id="inp" placeholder="Paste datasheet text or inline spec..."></textarea>
    <div class="row">
      <button class="ghost" id="btnSample">Load sample</button>
      <button class="ghost" id="btnInline">Inline spec</button>
      <label class="muted"><input type="checkbox" id="claude"/> use Claude</label>
    </div>
    <div class="row">
      <span class="muted">budget</span>
      <input type="range" id="budget" min="40" max="400" step="20" value="200"/>
      <span class="mono" id="budgetv">200</span>
    </div>
    <div class="row">
      <button id="btnGo">⚡ Design Chip</button>
      <span id="status" class="muted"></span>
    </div>
  </div>

  <div class="panel" id="out">
    <h3>2 · Result</h3>
    <div class="muted" id="placeholder">Run a design to see spec compliance, devices, netlist, and KiCad hints.</div>
    <div id="results" class="hidden">
      <div id="verdict" class="verdict"></div>
      <div class="metrics" id="metrics"></div>
      <div class="tabs">
        <div class="tab active" data-t="compliance">Spec compliance</div>
        <div class="tab" data-t="devices">Devices</div>
        <div class="tab" data-t="eda">KiCad / EDA</div>
        <div class="tab" data-t="netlist">Netlist</div>
      </div>
      <div id="tab-compliance"></div>
      <div id="tab-devices" class="hidden"></div>
      <div id="tab-eda" class="hidden"></div>
      <div id="tab-netlist" class="hidden">
        <div class="row"><button class="ghost" id="btnCopy">Copy</button>
          <button class="ghost" id="btnDl">Download .sp</button></div>
        <pre id="netlist"></pre>
      </div>
    </div>
  </div>
</div>

<script>
const $=s=>document.querySelector(s);
const fmt=(v,d=2)=>v==null?'—':(typeof v==='number'?v.toFixed(d):v);
const LABELS={
  aol_dB:['AOL','dB',1],gbp_MHz:['GBP','MHz',3],pm_deg:['Phase margin','°',1],
  iq_uA:['Iq','µA',1],slew_Vus:['Slew','V/µs',2],tp_us:['Delay','µs',2],
  vos_mV:['Vos','mV',2],trise_ns:['Rise','ns',1],tfall_ns:['Fall','ns',1],
  ron_ohm:['RON','Ω',1],bw_MHz:['BW','MHz',1],ton_ns:['tON','ns',1],toff_ns:['tOFF','ns',1],
  vout_V:['Vout','V',2],ripple_mV:['Ripple','mV',1],settle_ms:['Settle','ms',2],
  iout_mA:['Iout','mA',2],vref_V:['Vref','V',3],line_reg_mV:['Line reg','mV',2],tempco_ppm:['Tempco','ppm',0]
};
const INLINE={
  opamp:'gbp=1.1MHz pm>60 aol>95dB iq<80uA slew>0.5',
  comparator:'type=comparator tp<1us vos<3mV iq<1uA',
  switch:'type=switch ron<50ohm bw>10MHz ton<20ns toff<20ns',
  charge_pump:'type=charge_pump vout=5V settle<5ms ripple<50mV',
  vref:'type=vref vref=1.2V line_reg<5mV iq<100uA'
};
$('#budget').oninput=e=>$('#budgetv').textContent=e.target.value;
$('#btnSample').onclick=async()=>{
  const cat=$('#cat').value;
  const r=await fetch('/api/sample?category='+cat);
  const j=await r.json();$('#inp').value=j.text;};
$('#btnInline').onclick=()=>{$('#inp').value=INLINE[$('#cat').value]||'';};
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  ['compliance','devices','eda','netlist'].forEach(n=>$('#tab-'+n).classList.add('hidden'));
  $('#tab-'+t.dataset.t).classList.remove('hidden');
});
let lastNetlist='';
function metricCard(label,val,unit,pass){
  const cls=pass===true?'ok':pass===false?'bad':'';
  return `<div class="metric ${cls}"><div class="l">${label}</div><div class="v">${val}<span class="muted" style="font-size:12px"> ${unit||''}</span></div></div>`;
}
async function run(){
  const txt=$('#inp').value.trim();
  if(!txt){$('#status').textContent='enter a datasheet or spec';return;}
  const isInline=/[<>=]/.test(txt)&&txt.length<200&&!/\n/.test(txt);
  const body={budget:+$('#budget').value,use_claude:$('#claude').checked,category:$('#cat').value};
  if(isInline)body.spec=txt;else body.text=txt;
  $('#btnGo').disabled=true;
  $('#status').innerHTML='<span class="spin"></span>extracting specs · sizing on ngspice…';
  try{
    const r=await fetch('/api/design',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.error){$('#status').textContent='error: '+j.error;$('#btnGo').disabled=false;return;}
    render(j);
    $('#status').textContent='done';
  }catch(e){$('#status').textContent='error: '+e;}
  $('#btnGo').disabled=false;
}
function render(j){
  $('#placeholder').classList.add('hidden');
  $('#results').classList.remove('hidden');
  const v=$('#verdict');
  v.className='verdict '+(j.meets_all?'ok':'partial');
  v.textContent=(j.meets_all?'✓ ALL SPECS MET':'◐ PARTIAL')+`  ·  ${j.category||'?'}  ·  ${j.spec.part||'design'}  ·  ${j.topology}  ·  ${j.supply_V} V  ·  score ${j.score}`;
  const m=j.metrics,c=j.compliance;
  const pass=k=>c[k]?c[k].pass:undefined;
  const keys=j.measurable_specs||Object.keys(m).filter(k=>m[k]!=null);
  $('#metrics').innerHTML=keys.slice(0,6).map(k=>{
    const L=LABELS[k]||[k,'',2];
    return metricCard(L[0],fmt(m[k],L[2]),L[1],pass(k));
  }).join('');
  let rows='<table><tr><th>Spec</th><th>Target</th><th>Mode</th><th>Measured</th><th>Status</th></tr>';
  for(const k in c){const x=c[k];
    const cls=x.pass===null?'na':x.pass?'ok':'bad';
    const lbl=x.pass===null?'N/A':x.pass?'PASS':'FAIL';
    rows+=`<tr><td>${k}</td><td class="mono">${x.target}</td><td class="muted">${x.mode}</td>
    <td class="mono">${fmt(x.measured,3)}</td>
    <td><span class="badge ${cls}">${lbl}</span></td></tr>`;}
  rows+='</table>';
  if(j.spec.source)rows+=`<div class="muted" style="margin-top:8px">spec source: ${j.spec.source}${(j.spec.notes&&j.spec.notes.length)?' · '+j.spec.notes.join('; '):''}</div>`;
  if(j.warnings&&j.warnings.length)rows+=`<div class="muted" style="margin-top:6px">⚠ ${j.warnings.join('; ')}</div>`;
  $('#tab-compliance').innerHTML=rows;
  let dv='<table><tr><th>Device</th><th>Role</th><th>W (µm)</th><th>L (µm)</th><th>Value</th></tr>';
  j.devices.forEach(d=>{dv+=`<tr><td class="mono">${d.name}</td><td>${d.role}</td>
    <td class="mono">${d.W_um??''}</td><td class="mono">${d.L_um??''}</td><td class="mono">${d.value??''}</td></tr>`;});
  dv+='</table>';
  $('#tab-devices').innerHTML=dv;
  const eda=j.eda||{};
  $('#tab-eda').innerHTML=`<table>
    <tr><th>Package</th><td class="mono">${j.package||eda.package||'—'}</td></tr>
    <tr><th>KiCad symbol</th><td class="mono">${eda.kicad_symbol||'—'}</td></tr>
    <tr><th>KiCad footprint</th><td class="mono">${eda.kicad_footprint||'—'}</td></tr>
    <tr><th>Library</th><td>${eda.library||'KiCad standard (open)'}</td></tr>
  </table><div class="muted" style="margin-top:8px">Symbol stub included in API response (kicad_sym_stub).</div>`;
  lastNetlist=j.netlist;
  $('#netlist').textContent=j.netlist;
}
$('#btnGo').onclick=run;
$('#btnCopy').onclick=()=>navigator.clipboard.writeText(lastNetlist);
$('#btnDl').onclick=()=>{const b=new Blob([lastNetlist],{type:'text/plain'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);
  a.download='openforge_'+( $('#cat').value||'design')+'.sp';a.click();};
</script>
</body>
</html>
"""
