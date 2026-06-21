#!/usr/bin/env python3
import os
from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set

os.environ['OPENFORGE_MODEL_SET']='sky130'
set_active_model_set('sky130')
ms=resolve_models()
body='''
.param RPTAT=1000 RSCALE=8400 IREF=3u
Vsup vdd 0 5
Eop net2 0 ra1 qp1 800
''' + mos_line('p1','qp1','net2','vdd','vdd','p',w='20u',l='3u',ms=ms) + '\n' + \
mos_line('p2','ra1','net2','vdd','vdd','p',w='20u',l='3u',ms=ms) + '\n' + \
mos_line('p3','vref','net2','vdd','vdd','p',w='20u',l='3u',ms=ms) + f'''
Iref vdd net2 {{IREF}}
{mos_line('n0','net2','net2','0','0','n',w='6u',l='0.5u',ms=ms)}
Q1 0 0 qp1 0 {ms.pnp} area=1
Q2 0 0 qp2 0 {ms.pnp} area=8
Q3 0 0 qp3 0 {ms.pnp} area=1
Rptat ra1 qp2 {{RPTAT}}
Rscale vref qp3 {{RSCALE}}
Cout vref 0 10p
.control
dc Vsup 4 5.5 0.05
meas dc line_reg pp v(vref)
dc Vsup 4.5 5.5 0.05
meas dc lr45 pp v(vref)
.endc
.end
'''
ok,out=run_ngspice(ms.block+body,timeout=30)
print('4-5.5', grab_meas('line_reg',out)*1000)
print('4.5-5.5', grab_meas('lr45',out)*1000)
