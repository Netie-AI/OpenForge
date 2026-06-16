#!/usr/bin/env python3
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.forge_eval import evaluate_topology_params
from openanalog.interface.designer import design

r = design(inline_spec=DEV_MODE_SPECS["opamp"], budget=200, seed=42, record_kg=False)
print("meets_all", r["meets_all"])
print("params", r["params"])
print("metrics", r["metrics"])
ev = evaluate_topology_params("opamp", __import__("openanalog.forge.topologies", fromlist=["get_topology"]).get_topology("opamp").params_from_dict(r["params"]))
print("forge_eval score", ev["score"], ev["measured"])
