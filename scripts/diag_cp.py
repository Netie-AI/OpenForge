from openanalog.forge.topologies.charge_pump import ChargePumpParams, ChargePumpTopology

cp = ChargePumpTopology()
for model in [
    "IS=1e-14 N=1.2 RS=2",
    "IS=1e-11 N=1.05 RS=1",
    "IS=1e-9 N=1.02 RS=0.2",
]:
    p = ChargePumpParams(stages=2, rload_ohm=50e3, cap_F=300e-9, freq_Hz=1.5e6)
    deck = cp.measure.__func__.__globals__["_build_tran_deck"](p, 5.0).replace(
        ".model Dmod D (IS=1e-14 N=1.2 RS=2)",
        f".model Dmod D ({model})",
    )
    from openanalog.forge.topologies.base import run_ngspice, grab_meas
    ok, out = run_ngspice(deck, timeout=60)
    print(model, "vout", grab_meas("vout_avg", out))
