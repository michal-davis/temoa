"""
The Temoa Sequencer's job is to sequence the actions needed to execute a scenario.  Each scenario has a declared
processing mode (regular, myopic, mga, etc.) and the Temoa Sequencer sets up the necessary run(s) to
accomplish that.  Several processing requirements have requirements for multiple runs, each of which will have
a possibly unique sequencer based on the processing mode selected
"""
from enum import Enum, auto, unique
from logging import getLogger

from kiwisolver import Constraint
from pyomo.core import DataPortal, Suffix, Var

from temoa.temoa_model.temoa_config import TemoaConfig
from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_run import parse_args, temoa_setup, temoa_checks


# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/14/23

logger = getLogger(__name__)

@unique
class TemoaMode(Enum):
    """The processing mode for the scenario"""
    PERFECT_FORESIGHT = 1   # Normal run, single execution for full time horizon
    MGA = 2                 # Modeling for Generation of Alternatives, mutliple runs w/ changing constrained obj
    MYOPIC = 3              # Step-wise execution through the future
    METHOD_OF_MORRIS = 4    # Method-of-Morris run
    BUILD_ONLY = 5          # Just build the model, no solve

def start() -> None:
    """
    Start the process
    :return: None
    """

    # Run the preliminaries
    options = temoa_setup(config_filename='')
    temoa_checks(options)

    # Declare the TemoaMode
    options.temoa_mode = TemoaMode.BUILD_ONLY

    # Set up the individual runs & execute

    if options.temoa_mode == TemoaMode.BUILD_ONLY:
        model = TemoaModel()
        build_instance(model, options)
    else:
        raise NotImplementedError('not yet built')

def build_instance(model: TemoaModel, options) -> TemoaModel:
    modeldata = DataPortal(model=model)
    for fname in options.dot_dat:
        if fname[-4:] != '.dat':
            msg = "InputError: expecting a dot dat (e.g., data.dat) file, found '{}'\n"
            f_msg = msg.format(fname)
            logger.error(f_msg)
            raise Exception(f_msg)
        logger.debug('Started loading the DataPortal from the .dat file')
        modeldata.load(filename=fname)
        logger.debug('Finished reading the .dat file')

    # TODO:  Look at this.  There is likely a better way to get the dual than using Suffix (?)
    model.dual = Suffix(direction=Suffix.IMPORT)
    # self.model.rc = Suffix(direction=Suffix.IMPORT)
    # self.model.slack = Suffix(direction=Suffix.IMPORT)

    logger.info('Started creating model instance from data')
    instance = model.create_instance(modeldata)
    logger.info('Finished creating model instance from data')

    # gather some stats...
    c_count = 0
    v_count = 0
    for constraint in instance.component_objects(ctype=Constraint):
        c_count += len(constraint)
    for var in instance.component_objects(ctype=Var):
        v_count += len(var)
    logger.info("model built...  Variables: %d, Constraints: %d", v_count, c_count)


if __name__ == '__main__':
    start()
