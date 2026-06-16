#!/usr/bin/env python3
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design
from openanalog.forge.topologies import get_topology

r = design(inline_spec=DEV_MODE_SPECS["opamp"], budget=200, seed=42, record_kg=False)
topo = get_topology("opamp")
p = topo.params_from_dict(r["params"])
for i in range(3):
    m = topo.measure(p, with_full=True)
    print(f"run {i}", m.as_dict())
