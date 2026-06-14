from openanalog.forge.topologies.analog_switch import AnalogSwitchTopology, SwitchParams

p = SwitchParams(Wn=2000, Wp=716, len_n=0.18, len_p=0.23, Wdrv=128)
m = AnalogSwitchTopology().measure(p, with_full=True)
print(m.values)
print("---")
print(m.raw[-500:] if m.raw else "no raw")
