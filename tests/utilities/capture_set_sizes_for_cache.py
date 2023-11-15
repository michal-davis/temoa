"""

"""

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/14/23

import json
import sys
from os import path
import pyomo.environ as pyo

from definitions import PROJECT_ROOT
from temoa.temoa_model.temoa_model import TemoaModel, TemoaModel
from temoa.temoa_model.temoa_run import TemoaSolver

print("WARNING:  Continuing to execute this file will update the cached values for the set sizes for US_9R model in "
      "the testing_data folder from the sqlite databases in the same folder.  This should only need to be done if the "
      "schema or model have changed and that database has been updated.")

t = input('Type "Y" to continue, any other key to exit now.')
if t not in {'y', 'Y'}:
    sys.exit(0)
output_file = path.join(PROJECT_ROOT, 'tests', 'testing_data', 'US_9R_set_sizes.json')
config_file = path.join(PROJECT_ROOT, 'tests', 'utilities', 'config_US_9R_for_utility')

model = TemoaModel('utility')
temoa_solver = TemoaSolver(model=model, config_filename=config_file)

# TODO:  This relies on the solve mechanism to be hard-coded to skip the solve
#        update after a better sequencer is developed
for _ in temoa_solver.createAndSolve():
    pass
instance_object = temoa_solver.instance_hook
model_sets = instance_object.instance.component_map(ctype=pyo.Set)
sets_dict = {k: len(v) for k, v in model_sets.items()}

# stash the result in a json file...
with open(output_file, 'w') as f_out:
    json.dump(sets_dict, f_out, indent=2)

