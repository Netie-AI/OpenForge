from openanalog.forge.topologies.comparator import ComparatorParams, ComparatorTopology

ct = ComparatorTopology()
for iref in [150e-9, 200e-9, 250e-9, 300e-9, 350e-9, 400e-9]:
    p = ComparatorParams(Iref=iref, W6=60, Rload=20e3, W1=4, W3=4, W5=4, W7=8)
    m = ct.measure(p, with_full=True)
    print(
        f"Iref={iref*1e9:.0f}n iq={m.values.get('iq_uA')} "
        f"tp={m.values.get('tp_us')} vos={m.values.get('vos_mV')} ok={m.ok}"
    )
