#!/usr/bin/env python3
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.sizer import size
from openanalog.forge.topologies import get_topology
from openanalog.interface.datasheet import parse_inline_spec

spec = parse_inline_spec(DEV_MODE_SPECS["opamp"], category="opamp")
topo = get_topology("opamp")
cand = size(topo, spec, budget=200, seed=42)
print("cand meets_all", cand.meets_all)
print("cand metrics", cand.metrics.as_dict())
print("cand params", cand.params.as_dict())
m2 = topo.measure(cand.params, with_full=True)
print("remeasure", m2.as_dict())
