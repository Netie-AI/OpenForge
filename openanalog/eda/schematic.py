"""
openanalog/eda/schematic.py

Template-based SVG schematic rendering per topology category.
"""

from __future__ import annotations

import re
from typing import Any

from openanalog.eda.netlist_graph import render_netlist_graph_svg

_SVG_HEAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>
  .wire{{stroke:#5ad1c9;stroke-width:2;fill:none}}
  .box{{fill:#121722;stroke:#1e2636;stroke-width:1.5}}
  .dev{{fill:#0e131c;stroke:#7aa2ff;stroke-width:1.5}}
  .lbl{{fill:#d6deeb;font:12px ui-monospace,monospace}}
  .dim{{fill:#8a97ad;font:10px ui-monospace,monospace}}
  .title{{fill:#5ad1c9;font:bold 14px sans-serif}}
</style>
"""

_SVG_TAIL = "</svg>"


def _svg(w: int, h: int, body: str, title: str = "OpenForge") -> str:
    return _SVG_HEAD.format(w=w, h=h) + f'<text x="20" y="24" class="title">{title}</text>\n' + body + _SVG_TAIL


def _opamp_svg(result: dict[str, Any]) -> str:
    params = result.get("params", {})
    body = """
<rect x="180" y="80" width="120" height="80" rx="6" class="box"/>
<text x="210" y="125" class="lbl">OPAMP</text>
<line x1="60" y1="100" x2="180" y2="100" class="wire"/>
<text x="20" y="104" class="dim">IN+</text>
<line x1="60" y1="140" x2="180" y2="140" class="wire"/>
<text x="20" y="144" class="dim">IN-</text>
<line x1="300" y1="120" x2="380" y2="120" class="wire"/>
<text x="390" y="124" class="dim">OUT</text>
<rect x="340" y="40" width="50" height="24" class="dev"/>
<text x="348" y="56" class="dim">VDD</text>
<line x1="365" y1="64" x2="365" y2="80" class="wire"/>
<rect x="340" y="170" width="50" height="24" class="dev"/>
<text x="350" y="186" class="dim">GND</text>
<line x1="365" y1="160" x2="365" y2="170" class="wire"/>
"""
    for i, d in enumerate(result.get("devices", [])[:4]):
        y = 200 + i * 18
        body += f'<text x="20" y="{y}" class="dim">{d.get("name","")} W={d.get("W_um","?")}µm</text>\n'
    return _svg(440, 280, body, f"Op-Amp · {result.get('topology','')}")


def _comparator_svg(result: dict[str, Any]) -> str:
    body = """
<rect x="160" y="90" width="100" height="70" rx="6" class="box"/>
<polygon points="160,125 180,110 180,140" class="dev"/>
<text x="185" y="130" class="lbl">CMP</text>
<line x1="40" y1="110" x2="160" y2="110" class="wire"/>
<text x="10" y="114" class="dim">IN+</text>
<line x1="40" y1="140" x2="160" y2="140" class="wire"/>
<text x="10" y="144" class="dim">IN-</text>
<line x1="260" y1="125" x2="360" y2="125" class="wire"/>
<text x="370" y="129" class="dim">OUT</text>
"""
    return _svg(420, 220, body, f"Comparator · {result.get('topology','')}")


def _switch_svg(result: dict[str, Any]) -> str:
    body = """
<line x1="40" y1="120" x2="120" y2="120" class="wire"/>
<rect x="120" y="100" width="80" height="40" rx="4" class="dev"/>
<text x="130" y="125" class="lbl">TG</text>
<line x1="200" y1="120" x2="320" y2="120" class="wire"/>
<text x="10" y="124" class="dim">SIG</text>
<text x="330" y="124" class="dim">OUT</text>
<line x1="160" y1="60" x2="160" y2="100" class="wire"/>
<text x="140" y="55" class="dim">CTRL</text>
"""
    return _svg(400, 200, body, f"Analog Switch · {result.get('topology','')}")


def _charge_pump_svg(result: dict[str, Any]) -> str:
    stages = int(result.get("params", {}).get("stages", 2))
    body = '<rect x="40" y="80" width="60" height="30" class="dev"/><text x="50" y="100" class="dim">VDD</text>\n'
    x = 120
    for i in range(min(stages, 4)):
        body += f'<rect x="{x}" y="75" width="50" height="40" class="dev"/><text x="{x+8}" y="100" class="dim">S{i+1}</text>\n'
        body += f'<line x1="{x-10}" y1="95" x2="{x}" y2="95" class="wire"/>\n'
        x += 70
    body += f'<line x1="{x-10}" y1="95" x2="{x+20}" y2="95" class="wire"/>\n'
    body += f'<text x="{x+30}" y="100" class="dim">VOUT</text>\n'
    return _svg(420, 180, body, f"Charge Pump · {stages} stages")


def _vref_svg(result: dict[str, Any]) -> str:
    body = """
<rect x="140" y="90" width="120" height="60" rx="6" class="box"/>
<text x="165" y="125" class="lbl">BANDGAP</text>
<line x1="40" y1="120" x2="140" y2="120" class="wire"/>
<text x="10" y="124" class="dim">VDD</text>
<line x1="260" y1="120" x2="360" y2="120" class="wire"/>
<text x="370" y="124" class="dim">VREF</text>
"""
    return _svg(420, 200, body, f"VRef · {result.get('topology','')}")


_RENDERERS = {
    "opamp": _opamp_svg,
    "comparator": _comparator_svg,
    "switch": _switch_svg,
    "charge_pump": _charge_pump_svg,
    "vref": _vref_svg,
}


def render_svg(result: dict[str, Any]) -> str:
    netlist = result.get("netlist") or ""
    graph = render_netlist_graph_svg(netlist, result) if netlist else None
    if graph:
        svg = graph
    else:
        cat = result.get("category", "opamp")
        fn = _RENDERERS.get(cat, _opamp_svg)
        svg = fn(result)
    meets = result.get("meets_all")
    badge = "PASS" if meets else "PARTIAL"
    color = "#3fd17a" if meets else "#ffcc66"
    m = re.search(r'viewBox="0 0 \d+ (\d+)"', svg)
    badge_y = max(int(m.group(1)) - 18, 18) if m else 242
    svg = svg.replace("</svg>", f'<text x="20" y="{badge_y}" fill="{color}" font-weight="bold" font-size="11px" font-family="sans-serif">{badge}</text></svg>')
    return svg
