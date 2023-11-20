"""
Quick utility to capture set values from a pyomo model to enable later comparison.

This file should not need to be run again unless model schema changes
"""
# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  8/26/2023

import json
import sys
from os import path

import pyomo.environ as pyo

from definitions import PROJECT_ROOT
from temoa.temoa_model.temoa_sequencer import TemoaSequencer, TemoaMode

print("WARNING:  Continuing to execute this file will update the cached values in the testing_data folder"
      " from the sqlite databases in the same folder.  This should only need to be done if the schema or"
      " model have changed and that database has been updated.")

t = input('Type "Y" to continue, any other key to exit now.')
if t not in {'y', 'Y'}:
    sys.exit(0)
output_file = path.join(PROJECT_ROOT, 'tests', 'testing_data', 'utopia_sets.json')
config_file = path.join(PROJECT_ROOT, 'tests', 'utilities', 'config_utopia_for_utility')

ts = TemoaSequencer(config_file=config_file, mode_override=TemoaMode.BUILD_ONLY)
ts.start()
built_instance = ts.pf_solved_instance  # actually not solved in this case

model_sets = built_instance.component_map(ctype=pyo.Set)
sets_dict = {k: list(v) for k, v in model_sets.items()}

# stash the result in a json file...
with open(output_file, 'w') as f_out:
    json.dump(sets_dict, f_out, indent=2)

# do the same for the test_system

output_file = path.join(PROJECT_ROOT, 'tests', 'testing_data', 'test_system_sets.json')
config_file = path.join(PROJECT_ROOT, 'tests', 'utilities', 'config_test_system_for_utility')

ts = TemoaSequencer(config_file=config_file, mode_override=TemoaMode.BUILD_ONLY)
ts.start()
built_instance = ts.pf_solved_instance  # actually not solved in this case

model_sets = built_instance.component_map(ctype=pyo.Set)
sets_dict = {k: list(v) for k, v in model_sets.items()}

# stash the result in a json file...
with open(output_file, 'w') as f_out:
    json.dump(sets_dict, f_out, indent=2)