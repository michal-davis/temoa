"""
The possible operating modes for a scenario
"""
from enum import Enum, unique


# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/28/23

@unique
class TemoaMode(Enum):
    """The processing mode for the scenario"""
    PERFECT_FORESIGHT = 1  # Normal run, single execution for full time horizon
    MGA = 2  # Modeling for Generation of Alternatives, mutliple runs w/ changing constrained obj
    MYOPIC = 3  # Step-wise execution through the future
    METHOD_OF_MORRIS = 4  # Method-of-Morris run
    BUILD_ONLY = 5  # Just build the model, no solve

