"""
a container for test values from legacy code (Python 3.7 / Pyomo 5.5) captured for continuity/development testing
"""
from enum import Enum

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  6/27/23


class TestVals(Enum):
    OBJ_VALUE = 'obj_value'
    EFF_DOMAIN_SIZE = 'eff_domain_size'
    EFF_INDEX_SIZE = 'eff_index_size'
    VAR_COUNT = 'count of variables in model'
    CONSTR_COUNT = 'count of constraints in model'


# these values were captured on base level runs of the .dat files in the tests/testing_data folder
test_vals = {'config_test_system': {TestVals.OBJ_VALUE: 491977.7000753,
                                    TestVals.EFF_DOMAIN_SIZE: 30720,
                                    TestVals.EFF_INDEX_SIZE: 74,
                                    TestVals.CONSTR_COUNT: 3066,
                                    TestVals.VAR_COUNT: 1960},
             'config_utopia': {TestVals.OBJ_VALUE: 36535.631200,
                               TestVals.EFF_DOMAIN_SIZE: 12312,
                               TestVals.EFF_INDEX_SIZE: 64,
                               TestVals.CONSTR_COUNT: 1620,
                               TestVals.VAR_COUNT: 1104},
             }

