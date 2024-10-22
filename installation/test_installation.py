import pathlib as pl
import numpy as np
import matplotlib.pyplot as plt
import flopy
from flopy.mf6.utils import Mf6Splitter

nprocessors = 2

# load the base parallel model in MODFLOW 6 repo
ws = pl.Path("../modflow6/.mf6minsim/")
sim = flopy.mf6.MFSimulation.load(sim_ws=ws)

new_ws = pl.Path("temp/original")
sim.set_sim_path(new_ws)

# add oc file
for name in sim.model_names:
    gwf = sim.get_model(name)
    oc = flopy.mf6.ModflowGwfoc(
        gwf, 
        head_filerecord=f"{name}.hds", 
        saverecord=[("head", "all")],
        )

sim.write_simulation()
success, buff = sim.run_simulation(processors=nprocessors)
assert success, "base parallel model did not run"

# create base_hds array
base_hds = np.zeros((1,1,10), dtype=float)
for idx, name in enumerate(sim.model_names):
    gwf = sim.get_model(name)
    v = gwf.output.head().get_data()
    base_hds[0, 0, idx*5:(idx+1)*5] = gwf.output.head().get_data()

# create single domain model equivalent to base parallel model in the MODFLOW 6 repo
name = "single"
ws_single = pl.Path(f"temp/{name}")
sim_base = flopy.mf6.MFSimulation(sim_name=name, sim_ws=ws_single)
tdis = flopy.mf6.ModflowTdis(sim_base)
ims = flopy.mf6.ModflowIms(sim_base, inner_dvclose=1e-8, outer_dvclose=1e-8)
gwf = flopy.mf6.ModflowGwf(sim_base, modelname=name)
dis = flopy.mf6.ModflowGwfdis(gwf, nrow=1, ncol=10, nlay=1, top=10.0, botm=-100.0, delr=100.0, delc=100.00)
npf = flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=1.0)
ic = flopy.mf6.ModflowGwfic(gwf, strt=0.0)
chd = flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[(0, 0, 0, 1.0), (0, 0, 9, 10.0)])
oc =  flopy.mf6.ModflowGwfoc(gwf, head_filerecord=f"{name}.hds", saverecord=[("head", "all")])

sim_base.write_simulation()
success, buff = sim_base.run_simulation()
assert success, "single domain model did not run"

# evaluate if single and base_hds are equal
success = np.allclose(gwf.output.head().get_data(), base_hds)
assert success, "base_hds and single_hds do not match"

# split the model
ws_parallel = pl.Path("temp/split")
mfsplit = Mf6Splitter(sim_base)
split_array = mfsplit.optimize_splitting_mask(nparts=2)
new_sim = mfsplit.split_model(split_array)
new_sim.set_sim_path(ws_parallel)

new_sim.write_simulation()
success, buff = new_sim.run_simulation(processors=nprocessors)
assert success, "split domain model did not run"

# construct a single head array from models
model_names = list(new_sim.model_names)
head_dict = {}
for modelname in model_names:
    mnum = int(modelname.split("_")[-1])
    head = new_sim.get_model(modelname).output.head().get_data()
    head_dict[mnum] = head
split_hds = mfsplit.reconstruct_array(head_dict)

# evaluate if single and split_hds are equal
success = np.allclose(base_hds, split_hds)
assert success, "base_hds and split_hds do not match"

msg = "Successful testing of pixi environment and MODFLOW 6"
print(msg)
