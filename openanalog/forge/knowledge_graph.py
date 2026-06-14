from __future__ import annotations

import hashlib
import json
import pickle
import re
from pathlib import Path
from typing import Any

import networkx as nx

from openanalog.config import KG_DIR

MAX_LIVE = 500
MAX_ARCHIVED = 2000

_SPEC_ALIASES = {
    "bw": "bw_MHz",
    "bandwidth": "bw_MHz",
    "gain": "gain_dB",
    "aol": "aol_dB",
    "gbp": "gbp_MHz",
    "power": "power_mW",
    "pm": "pm_deg",
    "phase_margin": "pm_deg",
    "iq": "iq_uA",
    "slew": "slew_Vus",
    "ron": "ron_ohm",
    "tp": "tp_us",
    "vos": "vos_mV",
    "vout": "vout_V",
    "ripple": "ripple_mV",
    "vref": "vref_V",
    "tempco": "tempco_ppm",
}

_TOPOLOGY_ALIASES = {
    "tia": "tia",
    "transimpedance": "tia",
    "amp": "amplifier",
    "amplifier": "amplifier",
    "filter": "filter",
    "mirror": "mirror",
    "diff_amp": "diff_amp",
    "differential": "diff_amp",
    "ldo": "ldo",
    "osc": "osc",
    "oscillator": "osc",
    "charge_pump": "charge_pump",
    "comparator": "comparator",
    "switch": "switch",
    "analog_switch": "switch",
    "vref": "vref",
    "voltage_reference": "vref",
    "reference": "vref",
    "opamp": "opamp",
    "op_amp": "opamp",
}


class KnowledgeGraph:
    def __init__(self) -> None:
        self.g = nx.DiGraph()
        self.archived = nx.DiGraph()
        self._path = KG_DIR / "graph.gpickle"

    def add_node(
        self,
        topology: str,
        netlist_template: str,
        param_ranges: dict[str, Any],
        sim_stats: dict[str, Any],
        fitness_pass_rate: float,
        generation: int,
        parent_id: str | None = None,
        paper_sources: list[str] | None = None,
        tier: str | None = None,
        category: str | None = None,
    ) -> str:
        cat = category or topology
        nid = f"{cat}_{hashlib.sha256(netlist_template.encode()).hexdigest()[:12]}"
        live = [n for n, d in self.g.nodes(data=True) if d.get("category", d.get("topology")) == cat]
        if len(live) >= MAX_LIVE and fitness_pass_rate < 0.1:
            self._archive_weakest(cat, key="category")
        self.g.add_node(
            nid,
            topology=topology,
            category=cat,
            netlist_template=netlist_template,
            param_ranges=param_ranges,
            sim_stats=sim_stats,
            fitness_pass_rate=fitness_pass_rate,
            generation=generation,
            parent_id=parent_id,
            paper_sources=paper_sources or [],
            tier=tier,
        )
        if parent_id and self.g.has_node(parent_id):
            self.g.add_edge(parent_id, nid, type="evolved_from")
        return nid

    def add_product_node(self, product: dict[str, Any]) -> str:
        """Create or update a public Product node (datasheet facts only)."""
        part_id = product["part_id"]
        nid = f"product_{part_id}"
        self.g.add_node(
            nid,
            node_type="Product",
            **{k: v for k, v in product.items() if k != "part_id"},
            part_id=part_id,
        )
        return nid

    def link_generated_circuit(
        self,
        product_part_id: str,
        circuit_node_id: str,
        *,
        measured_specs: dict[str, Any] | None = None,
    ) -> None:
        """Link a forge winner / design to a Product spec via GENERATED_BY."""
        pid = f"product_{product_part_id}"
        if not self.g.has_node(pid):
            return
        self.g.add_edge(
            circuit_node_id,
            pid,
            type="GENERATED_BY",
            measured_specs=measured_specs or {},
        )

    def _archive_weakest(self, topology: str, *, key: str = "topology") -> None:
        nodes = [
            (n, d.get("fitness_pass_rate", 0))
            for n, d in self.g.nodes(data=True)
            if d.get(key, d.get("topology")) == topology
        ]
        if not nodes:
            return
        worst = min(nodes, key=lambda x: x[1])[0]
        data = dict(self.g.nodes[worst])
        self.archived.add_node(worst, **data)
        self.g.remove_node(worst)

    def prune(self, min_attempts: int = 20, min_rate: float = 0.05) -> int:
        removed = 0
        for n, d in list(self.g.nodes(data=True)):
            attempts = d.get("attempts", 0)
            rate = d.get("fitness_pass_rate", 0)
            if attempts >= min_attempts and rate < min_rate:
                self.archived.add_node(n, **d)
                self.g.remove_node(n)
                removed += 1
        return removed

    def save(self) -> None:
        KG_DIR.mkdir(parents=True, exist_ok=True)
        with self._path.open("wb") as f:
            pickle.dump(self.g, f, protocol=pickle.HIGHEST_PROTOCOL)
        arch = KG_DIR / "graph_archived.gpickle"
        with arch.open("wb") as f:
            pickle.dump(self.archived, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self) -> None:
        if self._path.exists():
            with self._path.open("rb") as f:
                self.g = pickle.load(f)
        arch = KG_DIR / "graph_archived.gpickle"
        if arch.exists():
            with arch.open("rb") as f:
                self.archived = pickle.load(f)

    def stats(self) -> dict[str, int]:
        return {"live": self.g.number_of_nodes(), "archived": self.archived.number_of_nodes()}

    @staticmethod
    def parse_spec_query(text: str) -> dict[str, Any]:
        q = text.strip()
        lower = q.lower()
        filters: dict[str, Any] = {}
        for word in re.findall(r"[a-z_]+", lower):
            if word in _TOPOLOGY_ALIASES:
                filters["topology"] = _TOPOLOGY_ALIASES[word]
                break
        for m in re.finditer(
            r"(bw|bandwidth|gain|power|pm|phase[_ ]?margin)\s*([><=]+)\s*([\d.]+)\s*(mhz|db|mw|deg)?",
            lower,
        ):
            key = _SPEC_ALIASES.get(m.group(1).replace(" ", "_"), m.group(1))
            op = m.group(2)
            val = float(m.group(3))
            filters[f"{key}{op}"] = val
        return filters

    def _spec_match_score(self, sim_stats: dict[str, Any], filters: dict[str, Any]) -> float:
        if not sim_stats:
            return 0.0
        checks = 0
        passed = 0
        for key, target in filters.items():
            if key == "topology":
                continue
            m = re.match(r"(\w+)([><=]+)", key)
            if not m:
                continue
            stat_key, op = m.group(1), m.group(2)
            val = sim_stats.get(stat_key)
            if val is None:
                continue
            checks += 1
            if ">" in op and val >= target:
                passed += 1
            elif "<" in op and val <= target:
                passed += 1
            elif "=" in op and abs(val - target) < 1e-6:
                passed += 1
        if checks == 0:
            return 0.5
        return passed / checks

    def query(self, spec_text: str, *, top: int = 5) -> list[dict[str, Any]]:
        filters = self.parse_spec_query(spec_text)
        topo_filter = filters.get("topology")
        ranked: list[tuple[float, str, dict[str, Any]]] = []
        for nid, data in self.g.nodes(data=True):
            node_cat = data.get("category", data.get("topology"))
            if topo_filter and node_cat != topo_filter:
                continue
            sim_stats = data.get("sim_stats") or {}
            spec_score = self._spec_match_score(sim_stats, filters)
            rate = float(data.get("fitness_pass_rate") or 0)
            gen = int(data.get("generation") or 0)
            score = spec_score * 0.6 + rate * 0.3 + min(gen / 1000.0, 0.1)
            ranked.append((score, nid, dict(data)))
        ranked.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, nid, data in ranked[:top]:
            out.append({"id": nid, "score": score, **data})
        return out

    def export_neo4j_cypher(self) -> Path:
        out = KG_DIR / "neo4j_export" / "import.cypher"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for n, d in self.g.nodes(data=True):
            props = json.dumps({k: v for k, v in d.items() if isinstance(v, (str, int, float, list))})
            lines.append(f"MERGE (n:Topology {{id: '{n}'}}) SET n += {props}")
        out.write_text("\n".join(lines), encoding="utf-8")
        return out
