from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design

r = design(inline_spec=DEV_MODE_SPECS["charge_pump"], budget=120, seed=19, record_kg=False)
print("params", r["params"])
print("metrics", r["metrics"])
print("meets_all", r["meets_all"])
