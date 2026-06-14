import os

from openanalog.forge.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph()
kg.load()
print("KG nodes:", kg.stats())
for nid, d in list(kg.g.nodes(data=True))[:5]:
    if d.get("topology") == "opamp":
        print("  opamp node:", nid, "tier=", d.get("tier"), "stats=", d.get("sim_stats"))

p = "data/designs.jsonl"
print("designs logged:", sum(1 for _ in open(p)) if os.path.exists(p) else 0)
