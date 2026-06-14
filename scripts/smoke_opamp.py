from openanalog.forge.opamp import OpAmpParams, measure

p = OpAmpParams()
m = measure(p, supply_V=5.0, cload_F=10e-12)
print("ok      :", m.ok)
print("aol_dB  :", m.aol_dB)
print("gbp_MHz :", m.gbp_MHz)
print("pm_deg  :", m.pm_deg)
print("iq_uA   :", m.iq_uA)
print("slew    :", m.slew_Vus)
if not m.ok:
    print("ERR:", m.error[:500])
    print("RAW:", m.raw[:800])
