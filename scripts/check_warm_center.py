#!/usr/bin/env python3
from openanalog.forge.param_mutator import OPAMP_WARM_CENTER
from openanalog.forge.forge_eval import evaluate_topology_params
from openanalog.forge.topologies import get_topology

topo = get_topology("opamp")
p = topo.params_from_dict(OPAMP_WARM_CENTER)
ev = evaluate_topology_params("opamp", p)
print("warm center score", ev["score"], "measured", ev["measured"])
print("failed", ev["failed_checks"])
