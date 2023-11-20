"""
PYTEST tests

Can be run in most IDEs with pytest installed in venv or from command line as:
$: pytest . --disable-warnings

"""

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  9/28/23

from temoa.temoa_model.validators import region_check, linked_region_check, region_group_check
import pyomo.environ as pyo


def test_region_check():
    """
    Test good region names
    """
    good_names = {'R3', 'California', 'NY', 'East_US'}
    bad_names = {   'New York',     # has space
                    'R43.2',        # has decimal
                    'R3-R4',        # has dash
                    '  R12',        # leading spaces
                    'global'        # illegal for individual region
                    }
    assert all(region_check(None, region=r) for r in good_names)
    for bad_name in bad_names:
        assert not region_check(None, region=bad_name), f'This should fail {bad_name}'


def test_linked_region_check():
    """
    Test legal pairings for linked regions
    """
    m = pyo.ConcreteModel()
    m.R = pyo.Set(initialize=['AZ', 'R2', 'Mexico'])
    good_names = {'AZ-R2', 'Mexico-AZ'}
    bad_names = {
        'AZ R2',        # bad separator
        'AZ',           # not paired
        'R1-R2',        # R1 non in m.R
        'R2-R2',        # dupe
        'R2--AZ',       # dupe separator
        'R2+AZ',        # bad separator
        'AZ - Mexico',  # bad spacing
        'AZ-R2-Mexico', # triples not allowed
    }
    assert all(linked_region_check(m, region_pair=rp) for rp in good_names)
    for bad_name in bad_names:
        assert not linked_region_check(m, region_pair=bad_name), f'This should fail {bad_name}'


def test_region_group_check():
    """
    Test legal multi-region groupings
    """
    m = pyo.ConcreteModel()
    m.R = pyo.Set(initialize=['AZ', 'R2', 'Mexico', 'E_US'])
    good_names = {'AZ+R2', 'Mexico+AZ', 'AZ+R2+Mexico', 'R2+E_US', 'global'}
    bad_names = {
        'AZ-R2',        # bad separator
        'AZ+AZ',        # dupe
        'AZ + R2',      # bad spacing
        'AZ+R2+R3',     # R3 is not in m.R
        'Region3',      # singleton not in m.R
    }
    for name in good_names:
        assert region_group_check(m, name), f'This name should have been good: {name}'
    for name in bad_names:
        assert not region_group_check(m, name), f'This name should have failed: {name}'