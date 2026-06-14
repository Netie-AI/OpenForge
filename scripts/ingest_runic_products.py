#!/usr/bin/env python3
"""Seed KG Product nodes from RunIC RS-series public specs."""

from __future__ import annotations

from openanalog.forge.knowledge_graph import KnowledgeGraph
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS, VREF_PHASE3_SPEC
from openanalog.kg.ingest_public import ingest_product
from openanalog.product_line import PRODUCT_LINE


def main() -> None:
    kg = KnowledgeGraph()
    kg.load()
    count = 0
    for p in PRODUCT_LINE:
        if p.status == "planned" or not p.topology:
            continue
        spec = p.inline_spec
        if p.id == "vref":
            spec = VREF_PHASE3_SPEC
        elif p.topology in DEV_MODE_SPECS and p.id not in ("precision_opamp", "hs_switch", "logic_switch"):
            spec = DEV_MODE_SPECS.get(p.topology, p.inline_spec)
        nid = ingest_product(
            part_id=p.part,
            category=p.topology,
            spec_text=spec,
            manufacturer="RunIC",
            subcategory=p.family.lower(),
            kg=kg,
        )
        print(f"upsert {p.part} ({p.label}) -> {nid}")
        count += 1
    kg.save()
    print(f"Done: {count} RunIC product nodes")


if __name__ == "__main__":
    main()
