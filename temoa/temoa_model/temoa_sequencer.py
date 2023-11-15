"""
The Temoa Sequencer's job is to sequence the actions needed to execute a scenario.  Each scenario has a declared
processing mode (regular, myopic, mga, etc.) and the Temoa Sequencer sets up the necessary run(s) to
accomplish that.  Several processing requirements have requirements for multiple runs, each of which will have
a possibly unique sequencer based on the processing mode selected
"""
from enum import Enum, auto, unique

from temoa.temoa_model.temoa_config import TemoaConfig


# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/14/23

def bob(z):
    """

    """
@unique
class TemoaMode(Enum):
    """The processing mode for the scenario"""
    PERFECT_FORESIGHT = 1   # Normal run, single execution for full time horizon
    MGA = 2                 # Modeling for Generation of Alternatives, mutliple runs w/ changing constrained obj
    MYOPIC = 3              # Step-wise execution through the future
    METHOD_OF_MORRIS = 4    # Method-of-Morris run

def start(args: list[str]) -> None:
    """
    Start the process
    :param args: the command line args passed in
    :return: None
    """

    # Run the preliminaries


    # Process the args and make a TemoaConfig


    # Delare the TemoaMode


    # Set up the individual runs & execute