"""
These tests are designed to check the construction of the numerous sets in the 2 exemplar models:
Utopia and Test System.

They construct all the pyomo Sets associated with the model and compare them with cached results that are stored
in json files
"""

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  9/26/23

import json
import pathlib

from pyomo import environ as pyo

from definitions import PROJECT_ROOT
from temoa.temoa_model.temoa_model import TemoaModel, TemoaModel
from temoa.temoa_model.temoa_sequencer import TemoaSequencer, TemoaMode


def test_upoptia_set_consistency():
    """
    test the set membership of the utopia model against cached values to ensure consistency
    """
    config_file = pathlib.Path(PROJECT_ROOT, 'tests', 'testing_configs', 'config_utopia')
    ts = TemoaSequencer(config_file=config_file, mode_override=TemoaMode.BUILD_ONLY)
    ts.start()
    built_instance = ts.pf_solved_instance  # actually not solved in this case
    model_sets = built_instance.component_map(ctype=pyo.Set)
    model_sets = {k: set(v) for k, v in model_sets.items()}

    # retrieve the cache and convert the set values from list -> set (json can't store sets)
    cache_file = pathlib.Path(PROJECT_ROOT, 'tests', 'testing_data', 'utopia_sets.json')
    with open(cache_file, 'r') as src:
        cached_sets = json.load(src)
    cached_sets = {k: set(tuple(t) if isinstance(t, list) else t for t in v) for (k, v) in cached_sets.items()}

    shortage_in_model = dict()
    overage_in_model = dict()
    for set_name, s in model_sets.items():
        if cached_sets.get(set_name) != s:
            if cached_sets.get(set_name):
                shortage_in_model[set_name] = s - cached_sets.get(set_name)
                overage_in_model[set_name] = cached_sets.get(set_name) - s
    missing_in_model = cached_sets.keys() - model_sets.keys()
    # drop any set that has "_index" in the name as they are no longer reported by newer version of pyomo
    missing_in_model = {s for s in missing_in_model if "_index" not in s}
    assert not missing_in_model, f'one or more cached set not in model: {missing_in_model}'
    if shortage_in_model:
        print('shortages')
        for k, v in shortage_in_model.items():
            print(k, v)
        print('overages')
        for k, v in overage_in_model.items():
            print(k, v)
    assert not shortage_in_model and not overage_in_model, 'The Utopia run-produced sets did not match cached values'



def test_test_system_set_consistency():
    """
    Test the set membership of the Test System model against cache.
    """
    # this could be combined with the similar test for utopia to use the fixture at some time...
    config_file = pathlib.Path(PROJECT_ROOT, 'tests', 'testing_configs', 'config_test_system')
    ts = TemoaSequencer(config_file=config_file, mode_override=TemoaMode.BUILD_ONLY)
    ts.start()
    built_instance = ts.pf_solved_instance  # actually not solved in this case
    model_sets = built_instance.component_map(ctype=pyo.Set)

    model_sets = {k: set(v) for k, v in model_sets.items()}

    cache_file = pathlib.Path(PROJECT_ROOT, 'tests', 'testing_data', 'test_system_sets.json')
    with open(cache_file, 'r') as src:
        cached_sets = json.load(src)
    cached_sets = {k: set(tuple(t) if isinstance(t, list) else t for t in v) for (k, v) in cached_sets.items()}
    shortage_in_model = dict()
    overage_in_model = dict()
    for set_name, s in model_sets.items():
        if cached_sets.get(set_name) != s:
            if cached_sets.get(set_name):
                shortage_in_model[set_name] = s - cached_sets.get(set_name)
                overage_in_model[set_name] = cached_sets.get(set_name) - s
    missing_in_model = cached_sets.keys() - model_sets.keys()
    # drop any set that has "_index" in the name as they are no longer reported by newer version of pyomo
    missing_in_model = {s for s in missing_in_model if "_index" not in s}
    assert not missing_in_model, f'one or more cached set not in model: {missing_in_model}'
    if shortage_in_model:
        print('shortages')
        for k, v in shortage_in_model.items():
            print(k, v)
        print('overages')
        for k, v in overage_in_model.items():
            print(k, v)
    assert not shortage_in_model and not overage_in_model, 'The Utopia run-produced sets did not match cached values'