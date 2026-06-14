"""Bundled level-1 MOSFET models shared by forge benches and seed deck prep."""

# ngspice batch mode treats the first line as the circuit title; a comment is required
# before .model directives or models are not registered.
BUNDLED_MODELS = """* openforge bundled models
.model nmos_ana nmos (level=1 vto=0.7 kp=120u gamma=0.45 phi=0.8 lambda=0.02
+ tox=1e-8 cgso=2e-10 cgdo=2e-10 cj=1e-4 cjsw=5e-10)
.model pmos_ana pmos (level=1 vto=-0.7 kp=40u gamma=0.45 phi=0.8 lambda=0.03
+ tox=1e-8 cgso=2e-10 cgdo=2e-10 cj=1e-4 cjsw=5e-10)
"""

NMOS = "nmos_ana"
PMOS = "pmos_ana"
