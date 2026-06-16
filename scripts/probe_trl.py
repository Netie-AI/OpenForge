#!/usr/bin/env python3
import trl
print("trl", trl.__version__)
import inspect
from trl import SFTTrainer
sig = inspect.signature(SFTTrainer.__init__)
print("SFTTrainer params:", list(sig.parameters.keys())[:30])
# search submodules
import pkgutil
for m in pkgutil.walk_packages(trl.__path__, trl.__name__ + "."):
    if "collat" in m.name.lower() or "completion" in m.name.lower():
        print("module", m.name)
