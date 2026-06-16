"""Tests for Runic product line catalog."""

from openanalog.interface.datasheet import detect_category
from openanalog.interface.designer import design
from openanalog.product_line import get_product, product_line_payload, resolve_product
import pytest


def test_product_line_has_runic_families():
    payload = product_line_payload()
    assert payload["designable_count"] >= 6
    assert payload["planned_count"] >= 7
    families = set(payload["families"].keys())
    assert "Amplifiers" in families
    assert "Power" in families
    assert "Compute" in families
    assert "Data Converters" in families


def test_resolve_precision_opamp():
    p = resolve_product(text="RS722 high precision low offset op-amp")
    assert p is not None
    assert p.id == "precision_opamp"
    assert p.topology == "opamp"


def test_detect_hs_switch():
    assert detect_category("RS2227 high speed analog switch 300MHz") == "switch"


def test_detect_ldo_type_tag():
    assert detect_category("type=ldo vout=1.8V") == "ldo"


def test_planned_product_blocks_design():
    with pytest.raises(ValueError, match="roadmap"):
        design(
            inline_spec="type=adc bits=12",
            product_id="adc",
            use_llm=False,
            record_kg=False,
        )


def test_precision_opamp_routes_to_opamp_topology():
    p = get_product("precision_opamp")
    assert p is not None
    assert p.topology == "opamp"
    assert p.to_dict()["designable"] is True
