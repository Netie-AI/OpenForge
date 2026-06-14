#!/usr/bin/env python3
from openanalog.interface.designer import design
from openanalog.forge.forge_eval import evaluate_forge_fitness

r = design(inline_spec="gbp=1.1MHz pm>60 aol>95dB iq<80uA", budget=250, record_kg=False, seed=42)
ev = evaluate_forge_fitness(r["netlist"], "opamp")
print("design meets_all", r["meets_all"])
print("forge score", ev["score"])
print("measured", ev.get("measured"))
print("failed", ev.get("failed_checks"))
