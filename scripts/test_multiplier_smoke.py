#!/usr/bin/env python3
from openanalog.forge.topologies.multiplier import MultiplierTopology

t = MultiplierTopology()
m = t.measure(t.default_params())
print("ok:", m.ok, "metrics:", m.values)
