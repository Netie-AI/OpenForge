"""
openanalog/interface/datasheet.py

Turn an analog datasheet (text now, PDF later) into a structured design spec
for any supported circuit category.
"""

from __future__ import annotations

import re
from typing import Any

_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("comparator", ["comparator", "compare", "rs890", "lm2903", "lm393"]),
    ("switch", ["analog switch", "transmission gate", "rs2105", "rs2227", "analog mux"]),
    ("charge_pump", ["charge pump", "dickson", "voltage doubler", "inverting charge"]),
    ("vref", ["voltage reference", "bandgap", "vref", "reference voltage", "shunt reference"]),
    ("opamp", ["operational amplifier", "op-amp", "op amp", "opamp", "ota"]),
]

_DEFAULT_MODES: dict[str, dict[str, str]] = {
    "opamp": {
        "aol_dB": "min", "gbp_MHz": "target", "pm_deg": "min", "iq_uA": "max",
        "slew_Vus": "min", "cmrr_dB": "min", "vos_mV": "max", "settle_us": "max",
    },
    "comparator": {
        "tp_us": "max", "iq_uA": "max", "vos_mV": "max", "trise_ns": "max", "tfall_ns": "max",
    },
    "switch": {
        "ron_ohm": "max", "bw_MHz": "min", "ton_ns": "max", "toff_ns": "max", "iq_uA": "max",
    },
    "charge_pump": {
        "vout_V": "target", "ripple_mV": "max", "settle_ms": "max", "iout_mA": "min", "iq_uA": "max",
    },
    "vref": {
        "vref_V": "target", "line_reg_mV": "max", "tempco_ppm": "max", "iq_uA": "max",
    },
}

_INLINE_PATTERNS: dict[str, dict[str, str]] = {
    "opamp": {
        "gbp_MHz": r"gbp\s*([<>=]?)\s*([\d.]+)\s*MHz",
        "aol_dB": r"aol\s*([<>=]?)\s*([\d.]+)\s*dB",
        "pm_deg": r"pm\s*([<>=]?)\s*([\d.]+)",
        "iq_uA": r"iq\s*([<>=]?)\s*([\d.]+)\s*uA",
        "slew_Vus": r"slew\s*([<>=]?)\s*([\d.]+)",
        "cmrr_dB": r"cmrr\s*([<>=]?)\s*([\d.]+)",
    },
    "comparator": {
        "tp_us": r"tp\s*([<>=]?)\s*([\d.]+)\s*u?s",
        "vos_mV": r"vos\s*([<>=]?)\s*([\d.]+)\s*mV",
        "iq_uA": r"iq\s*([<>=]?)\s*([\d.]+)\s*uA",
        "trise_ns": r"trise\s*([<>=]?)\s*([\d.]+)\s*ns",
        "tfall_ns": r"tfall\s*([<>=]?)\s*([\d.]+)\s*ns",
    },
    "switch": {
        "ron_ohm": r"ron\s*([<>=]?)\s*([\d.]+)\s*(?:ohm|Ω)?",
        "bw_MHz": r"bw\s*([<>=]?)\s*([\d.]+)\s*MHz",
        "ton_ns": r"ton\s*([<>=]?)\s*([\d.]+)\s*ns",
        "toff_ns": r"toff\s*([<>=]?)\s*([\d.]+)\s*ns",
        "iq_uA": r"iq\s*([<>=]?)\s*([\d.]+)\s*uA",
    },
    "charge_pump": {
        "vout_V": r"vout\s*[=]?\s*([\d.]+)\s*V",
        "ripple_mV": r"ripple\s*([<>=]?)\s*([\d.]+)\s*mV",
        "settle_ms": r"settle\s*([<>=]?)\s*([\d.]+)\s*ms",
        "iout_mA": r"iout\s*([<>=]?)\s*([\d.]+)\s*mA",
        "iq_uA": r"iq\s*([<>=]?)\s*([\d.]+)\s*uA",
    },
    "vref": {
        "vref_V": r"vref\s*[=]?\s*([\d.]+)\s*V",
        "line_reg_mV": r"line[_\s-]*reg\s*([<>=]?)\s*([\d.]+)\s*mV",
        "tempco_ppm": r"tempco\s*([<>=]?)\s*([\d.]+)\s*ppm",
        "iq_uA": r"iq\s*([<>=]?)\s*([\d.]+)\s*uA",
    },
}


def _num(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _search(pattern: str, text: str, group: int = 1) -> float | None:
    m = re.search(pattern, text, re.I)
    return _num(m.group(group)) if m else None


def detect_category(text: str) -> str:
    """Keyword-based circuit category detection. Falls back to opamp."""
    lower = text.lower()
    tm = re.search(r"type\s*=\s*([a-z_]+)", lower)
    if tm:
        raw = tm.group(1).replace("-", "_")
        aliases = {
            "op_amp": "opamp", "operational_amplifier": "opamp",
            "analog_switch": "switch", "voltage_reference": "vref", "reference": "vref",
        }
        return aliases.get(raw, raw)
    scores: dict[str, int] = {}
    for cat, kws in _CATEGORY_KEYWORDS:
        for kw in kws:
            if kw in lower:
                scores[cat] = scores.get(cat, 0) + len(kw)
    if not scores:
        return "opamp"
    return max(scores, key=scores.get)


def _supply_V(text: str) -> float:
    supply = _search(r"VS\s*=\s*([\d.]+)\s*V", text) or _search(r"supply[^\n]*?([\d.]+)\s*V", text)
    if supply and 1.0 <= supply <= 12.0:
        return supply
    return 5.0


def _part_name(text: str) -> str:
    for pat in [r"\b(RS\d{3,4}[A-Z]?)\b", r"\b(LM\d{3,4}[A-Z]?)\b", r"\b(TL\d{3,4})\b"]:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return "unknown"


def extract_opamp_specs_regex(text: str) -> dict[str, Any]:
    notes: list[str] = []
    gbp = _search(r"gain[\s\-]*bandwidth[^\n]*?([\d.]+)\s*MHz", text) or _search(r"GBP[^\n]*?([\d.]+)\s*MHz", text)
    slew = _search(r"slew\s*rate[^\n]*?([\d.]+)\s*V\s*/\s*us", text)
    pm = _search(r"phase\s*margin[^\n]*?([\d.]+)\s*(?:°|deg)", text)
    iq_typ = _search(r"quiescent\s*current[^\n]*?([\d.]+)", text)
    iq_max = None
    m_iq = re.search(r"quiescent\s*current[^\n]*?([\d.]+)\s+([\d.]+)", text, re.I)
    if m_iq:
        iq_typ, iq_max = _num(m_iq.group(1)), _num(m_iq.group(2))
    cmrr = _search(r"common[\s\-]*mode\s*rejection[^\n]*?([\d.]+)", text)
    vos = _search(r"input\s*offset\s*voltage[^\s\S]{0,80}?([\d.]+)\s*mV", text)
    settle = _search(r"settling\s*time[^\n]*?([\d.]+)\s*us", text)
    aol = None
    m_aol = re.search(r"open[\s\-]*loop\s*(?:voltage\s*)?gain([^\n]{0,80})", text, re.I)
    if m_aol:
        vals = [float(x) for x in re.findall(r"\b(\d{2,3})\b", m_aol.group(1))]
        vals = [v for v in vals if 80 <= v <= 160]
        if vals:
            aol = min(vals)
    raw_targets = {
        "aol_dB": aol if aol is not None else 90.0,
        "gbp_MHz": gbp, "pm_deg": 60.0 if pm is None else max(55.0, min(pm, 70.0)),
        "iq_uA": iq_max if iq_max is not None else iq_typ,
        "slew_Vus": slew, "cmrr_dB": cmrr, "vos_mV": vos, "settle_us": settle,
    }
    if gbp is None:
        notes.append("GBP not found; leaving unset")
    targets = {
        k: {"value": float(v), "mode": _DEFAULT_MODES["opamp"].get(k, "target")}
        for k, v in raw_targets.items() if v is not None
    }
    return {
        "circuit_type": "opamp", "supply_V": _supply_V(text), "targets": targets,
        "part": _part_name(text), "source": "regex", "notes": notes,
    }


def extract_comparator_specs_regex(text: str) -> dict[str, Any]:
    tp = _search(r"propagation\s*delay[^\n]*?([\d.]+)\s*(?:us|µs)", text)
    if tp is None:
        tp = _search(r"response\s*time[^\n]*?([\d.]+)\s*(?:us|µs)", text)
    if tp is None:
        tp_ns = _search(r"propagation\s*delay[^\n]*?([\d.]+)\s*ns", text)
        tp = tp_ns / 1000 if tp_ns else None
    vos = _search(r"offset\s*voltage[^\n]*?([\d.]+)\s*mV", text)
    iq = _search(r"quiescent\s*current[^\n]*?([\d.]+)", text)
    tr = _search(r"rise\s*time[^\n]*?([\d.]+)\s*ns", text)
    tf = _search(r"fall\s*time[^\n]*?([\d.]+)\s*ns", text)
    raw = {"tp_us": tp or 1.0, "vos_mV": vos or 3.0, "iq_uA": iq or 1.0, "trise_ns": tr, "tfall_ns": tf}
    targets = {
        k: {"value": float(v), "mode": _DEFAULT_MODES["comparator"].get(k, "target")}
        for k, v in raw.items() if v is not None
    }
    return {
        "circuit_type": "comparator", "supply_V": _supply_V(text), "targets": targets,
        "part": _part_name(text), "source": "regex", "notes": [],
    }


def extract_switch_specs_regex(text: str) -> dict[str, Any]:
    ron = _search(r"on[\s\-]*resistance[^\n]*?([\d.]+)\s*(?:ohm|Ω)", text) or _search(r"RON[^\n]*?([\d.]+)", text)
    bw = _search(r"bandwidth[^\n]*?([\d.]+)\s*MHz", text) or _search(r"-3\s*dB[^\n]*?([\d.]+)\s*MHz", text)
    ton = _search(r"turn[\s\-]*on[^\n]*?([\d.]+)\s*ns", text)
    toff = _search(r"turn[\s\-]*off[^\n]*?([\d.]+)\s*ns", text)
    iq = _search(r"quiescent\s*current[^\n]*?([\d.]+)", text)
    raw = {"ron_ohm": ron or 50.0, "bw_MHz": bw or 10.0, "ton_ns": ton, "toff_ns": toff, "iq_uA": iq}
    targets = {
        k: {"value": float(v), "mode": _DEFAULT_MODES["switch"].get(k, "target")}
        for k, v in raw.items() if v is not None
    }
    return {
        "circuit_type": "switch", "supply_V": _supply_V(text), "targets": targets,
        "part": _part_name(text), "source": "regex", "notes": [],
    }


def extract_charge_pump_specs_regex(text: str) -> dict[str, Any]:
    vout = _search(r"output\s*voltage[^\n]*?([\d.]+)\s*V", text)
    ripple = _search(r"ripple[^\n]*?([\d.]+)\s*mV", text)
    settle = _search(r"settling[^\n]*?([\d.]+)\s*ms", text)
    iout = _search(r"output\s*current[^\n]*?([\d.]+)\s*mA", text)
    iq = _search(r"quiescent\s*current[^\n]*?([\d.]+)", text)
    raw = {
        "vout_V": vout or 5.0, "ripple_mV": ripple or 50.0, "settle_ms": settle or 5.0,
        "iout_mA": iout, "iq_uA": iq,
    }
    targets = {
        k: {"value": float(v), "mode": _DEFAULT_MODES["charge_pump"].get(k, "target")}
        for k, v in raw.items() if v is not None
    }
    return {
        "circuit_type": "charge_pump", "supply_V": _supply_V(text), "targets": targets,
        "part": _part_name(text), "source": "regex", "notes": [],
    }


def extract_vref_specs_regex(text: str) -> dict[str, Any]:
    vref = _search(r"reference\s*voltage[^\n]*?([\d.]+)\s*V", text) or _search(r"Vref[^\n]*?([\d.]+)\s*V", text)
    line_reg = _search(r"line\s*regulation[^\n]*?([\d.]+)\s*mV", text)
    tempco = _search(r"temp(?:erature)?\s*coefficient[^\n]*?([\d.]+)\s*ppm", text)
    iq = _search(r"quiescent\s*current[^\n]*?([\d.]+)", text)
    raw = {
        "vref_V": vref or 1.2, "line_reg_mV": line_reg or 5.0,
        "tempco_ppm": tempco or 100.0, "iq_uA": iq,
    }
    targets = {
        k: {"value": float(v), "mode": _DEFAULT_MODES["vref"].get(k, "target")}
        for k, v in raw.items() if v is not None
    }
    notes = ["tempco accuracy limited on bundled level-1 models; use foundry PDK for production."]
    return {
        "circuit_type": "vref", "supply_V": _supply_V(text), "targets": targets,
        "part": _part_name(text), "source": "regex", "notes": notes,
    }


_EXTRACTORS = {
    "opamp": extract_opamp_specs_regex,
    "comparator": extract_comparator_specs_regex,
    "switch": extract_switch_specs_regex,
    "charge_pump": extract_charge_pump_specs_regex,
    "vref": extract_vref_specs_regex,
}


def extract_with_claude(text: str, *, category: str = "opamp") -> dict[str, Any]:
    from openanalog import claude

    schema_hint = (
        f"Extract {category} design targets from this datasheet text. Output JSON ONLY:\n"
        '{"circuit_type":"' + category + '","supply_V":float,"part":str,"targets":{...}}\n'
        "Each target: {\"value\":float,\"mode\":\"min|max|target\"}. Omit unknown targets.\n\n"
        + text[:12000]
    )
    data = claude.ask_json("You extract analog IC specs. JSON only.", schema_hint)
    data.setdefault("circuit_type", category)
    data.setdefault("supply_V", 5.0)
    data.setdefault("targets", {})
    data["source"] = "claude"
    data.setdefault("notes", [])
    return data


def extract_specs(text: str, *, use_claude: bool = False, category: str | None = None) -> dict[str, Any]:
    cat = category or detect_category(text)
    if use_claude:
        try:
            return extract_with_claude(text, category=cat)
        except Exception as e:
            spec = _EXTRACTORS.get(cat, extract_opamp_specs_regex)(text)
            spec["notes"].append(f"claude extraction failed ({e}); used regex")
            return spec
    fn = _EXTRACTORS.get(cat, extract_opamp_specs_regex)
    return fn(text)


def parse_inline_spec(s: str, *, category: str | None = None) -> dict[str, Any]:
    cat = category or detect_category(s)
    targets: dict[str, Any] = {}
    supply_V = 5.0
    sm = re.search(r"(?:vdd|supply|vs)\s*=?\s*([\d.]+)\s*v", s, re.I)
    if sm:
        supply_V = float(sm.group(1))
    patterns = _INLINE_PATTERNS.get(cat, _INLINE_PATTERNS["opamp"])
    modes = _DEFAULT_MODES.get(cat, _DEFAULT_MODES["opamp"])
    for key, pat in patterns.items():
        m = re.search(pat, s, re.I)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 2:
            op, val = groups[0], float(groups[1])
        else:
            op, val = "=", float(groups[0])
        mode = {"<": "max", ">": "min", "=": "target", "": modes.get(key, "target")}[op or "="]
        targets[key] = {"value": val, "mode": mode}
    return {
        "circuit_type": cat,
        "supply_V": supply_V,
        "targets": targets,
        "part": "inline",
        "source": "inline",
        "notes": [],
    }
