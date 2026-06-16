"""Knowledge graph schema for public datasheet product nodes."""

from __future__ import annotations

from typing import Any

from openanalog.forge.spec_envelopes import DATASHEET_PARTS, DEV_MODE_SPECS

PRODUCT_FIELDS: tuple[str, ...] = (
    "part_id",
    "manufacturer",
    "category",
    "subcategory",
    "package",
    "application_axis",
    "source",
    "public_only",
)

ELECTRICAL_FIELDS: dict[str, tuple[str, ...]] = {
    "opamp": ("aol_dB", "gbp_MHz", "pm_deg", "iq_uA", "slew_Vus", "vos_mV", "cmrr_dB"),
    "comparator": ("tp_us", "iq_uA", "vos_mV", "trise_ns", "tfall_ns"),
    "switch": ("ron_ohm", "bw_MHz", "ton_ns", "toff_ns", "iq_uA"),
    "charge_pump": ("vout_V", "ripple_mV", "settle_ms", "iout_mA", "iq_uA"),
    "vref": ("vref_V", "line_reg_mV", "tempco_ppm", "iq_uA"),
    "ldo": ("vout_V", "dropout_mV", "line_reg_mV", "load_reg_mV", "iq_uA", "psrr_dB"),
    "multiplier": ("gain_err_pct", "bw_MHz", "iq_uA", "output_swing_V"),
}

EDGE_TYPES: tuple[str, ...] = (
    "SIMILAR_TO",
    "USED_WITH",
    "SUCCESSOR_OF",
    "IMPLEMENTS",
    "GENERATED_BY",
)


def normalize_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and fill defaults for a Product node."""
    part_id = str(raw.get("part_id") or raw.get("part") or "").strip()
    if not part_id:
        raise ValueError("part_id required")
    category = str(raw.get("category") or "opamp").lower()
    out: dict[str, Any] = {
        "part_id": part_id,
        "manufacturer": raw.get("manufacturer") or "RunIC",
        "category": category,
        "subcategory": raw.get("subcategory") or "general",
        "package": raw.get("package") or "SOT23-5",
        "application_axis": raw.get("application_axis") or "general-purpose",
        "source": raw.get("source") or "public_datasheet",
        "public_only": True,
    }
    specs = raw.get("electrical_specs") or raw.get("targets") or {}
    allowed = ELECTRICAL_FIELDS.get(category, ())
    out["electrical_specs"] = {k: specs[k] for k in specs if k in allowed or not allowed}
    if category in DEV_MODE_SPECS:
        out["spec_envelope"] = DEV_MODE_SPECS[category]
    out["datasheet_part"] = DATASHEET_PARTS.get(category, part_id)
    return out
