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
from pathlib import Path

import pyomo.environ as pyo

from definitions import PROJECT_ROOT
from temoa.temoa_model.temoa_sequencer import TemoaSequencer, TemoaMode

print(
    "WARNING:  Continuing to execute this file will "
    "update the cached values in the testing_data folder"
    "from the sqlite databases in the same folder.  "
    "This should only need to be done if the schema or"
    "model have changed and that database has been updated.")

t = input('Type "Y" to continue, any other key to exit now.')
if t not in {'y', 'Y'}:
    sys.exit(0)

output_path = Path(PROJECT_ROOT, 'tests', 'testing_log')  # capture the log here

scenarios = [
    {
        'output_file': Path(PROJECT_ROOT, 'tests', 'testing_data', 'utopia_sets.json'),
        'config_file': Path(PROJECT_ROOT, 'tests', 'utilities', 'config_utopia.toml')
    },
    {
        'output_file': Path(PROJECT_ROOT, 'tests', 'testing_data', 'test_system_sets.json'),
        'config_file': Path(PROJECT_ROOT, 'tests', 'utilities',
                            'config_test_system.toml')
    }
]
for scenario in scenarios:
    ts = TemoaSequencer(config_file=scenario['config_file'],
                        output_path=output_path)

    built_instance = ts.start()  # catch the built model

    model_sets = built_instance.component_map(ctype=pyo.Set)
    sets_dict = {k: list(v) for k, v in model_sets.items()}

    # stash the result in a json file...
    with open(scenario['output_file'], 'w') as f_out:
        json.dump(sets_dict, f_out, indent=2)
