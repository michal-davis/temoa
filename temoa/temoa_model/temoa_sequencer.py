"""
The Temoa Sequencer's job is to sequence the actions needed to execute a scenario.  Each scenario has a declared
processing mode (regular, myopic, mga, etc.) and the Temoa Sequencer sets up the necessary run(s) to
accomplish that.  Several processing requirements have requirements for multiple runs, each of which will have
a possibly unique sequencer based on the processing mode selected
"""
import sys
from argparse import Namespace
from enum import Enum, unique
from logging import getLogger
from pathlib import Path

import pyomo.opt

from temoa.temoa_model.run_actions import build_instance, solve_instance, handle_results
from temoa.temoa_model.temoa_config import TemoaConfig
from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_run import temoa_setup, temoa_checks

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/14/23

logger = getLogger(__name__)


@unique
class TemoaMode(Enum):
    """The processing mode for the scenario"""
    PERFECT_FORESIGHT = 1  # Normal run, single execution for full time horizon
    MGA = 2  # Modeling for Generation of Alternatives, mutliple runs w/ changing constrained obj
    MYOPIC = 3  # Step-wise execution through the future
    METHOD_OF_MORRIS = 4  # Method-of-Morris run
    BUILD_ONLY = 5  # Just build the model, no solve


class TemoaSequencer:
    """A Sequencer instance to control all runs for a scenario based on the TemoaMode"""

    def __init__(self, config_file: str, mode_override: TemoaMode = None, **kwargs):
        """
        Create a new Sequencer
        :param config_file: Optional path to config file.  If not provided, it will be read from Command Line Args
        :param mode_override: Optional override to execution mode.  If not provided, it will be read from config file
        """

        self.config: TemoaConfig = None
        self.temoa_mode: TemoaMode

        self.config_file: Path
        if config_file:
            self.config_file = Path(config_file)
        else:
            logger.error('No config file passed in.  Exiting')
            raise RuntimeError('No config file location')
        # check it...
        if not self.config_file.is_file():
            logger.error('Config file location passed %d does not point to a file', self.config_file)
            raise RuntimeError(f'Invalid config file: {self.config_file}')
        self.mode_override: TemoaMode = mode_override

        # for feedback to user
        self.confirmations = True if kwargs.get('confirmations') else False

        # for results catching
        self.pf_results: pyomo.opt.SolverResults = None
        self.pf_solved_instance: TemoaModel = None


    def start(self):
        """ Start the processing of the scenario """

        # Run the preliminaries
        # Build a TemoaConfig
        self.config = TemoaConfig()
        self.config.build(config=self.config_file)

        temoa_checks(self.config)

        # Distill the TemoaMode
        self.temoa_mode = self.mode_override if self.mode_override else self.config.temoa_mode
        if not isinstance(self.temoa_mode, TemoaMode):
            logger.error('Temoa Mode not set properly.  Override: %d, Config File: %d',
                         self.mode_override, self.config.temoa_mode)
            raise RuntimeError('Problem with mode selection, see log file.')

        # Get user confirmation if requested
        if self.confirmations:
            try:
                print(self.config.__repr__())
                print('\nPlease press enter to continue or Ctrl+C to quit.\n')
                input() # Give the user a chance to confirm input
            except KeyboardInterrupt:
                logger.warning('User aborted from confirmation page.  Exiting')
                print('\n\nUser requested quit.  Exiting Temoa ...\n')
                sys.exit(-1)

        # Set up the individual runs & execute

        if self.temoa_mode == TemoaMode.BUILD_ONLY:
            self.pf_solved_instance = build_instance(self.config.dot_dat)
            return self.pf_solved_instance
        elif self.temoa_mode == TemoaMode.PERFECT_FORESIGHT:
            instance = build_instance(self.config.dot_dat)
            # sys.exit(-1)
            self.pf_solved_instance, self.pf_results = solve_instance(instance, self.config.solver, self.config.keepPyomoLP)
            handle_results(self.pf_solved_instance, self.pf_results, self.config)
        else:
            raise NotImplementedError('not yet built')
