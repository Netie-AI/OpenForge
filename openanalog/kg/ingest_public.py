"""Ingest public datasheet specs into the knowledge graph."""

from __future__ import annotations

from typing import Any

from openanalog.forge.knowledge_graph import KnowledgeGraph
from openanalog.interface.datasheet import parse_inline_spec
from openanalog.kg.schema import normalize_product


def fetch_datasheet_specs(part_id: str, *, spec_text: str, category: str) -> dict[str, Any]:
    """Extract electrical table fields from inline/public spec text."""
    parsed = parse_inline_spec(spec_text, category=category)
    targets = {
        k: v.get("value")
        for k, v in (parsed.get("targets") or {}).items()
        if v.get("value") is not None
    }
    return {
        "part_id": part_id,
        "category": category,
        "electrical_specs": targets,
        "supply_V": parsed.get("supply_V", 5.0),
    }


def normalize_to_schema(raw_specs: dict[str, Any]) -> dict[str, Any]:
    return normalize_product(raw_specs)


def upsert_to_kg(product_dict: dict[str, Any], *, kg: KnowledgeGraph | None = None) -> str:
    graph = kg or KnowledgeGraph()
    graph.load()
    node = normalize_to_schema(product_dict)
    return graph.add_product_node(node)


def ingest_product(
    *,
    part_id: str,
    category: str,
    spec_text: str,
    manufacturer: str = "RunIC",
    subcategory: str = "general",
    kg: KnowledgeGraph | None = None,
) -> str:
    raw = fetch_datasheet_specs(part_id, spec_text=spec_text, category=category)
    raw["manufacturer"] = manufacturer
    raw["subcategory"] = subcategory
    return upsert_to_kg(raw, kg=kg)
