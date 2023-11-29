"""
The Temoa Sequencer's job is to sequence the actions needed to execute a scenario.  Each scenario has a declared
processing mode (regular, myopic, mga, etc.) and the Temoa Sequencer sets up the necessary run(s) to
accomplish that.  Several processing requirements have requirements for multiple runs, each of which will have
a possibly unique sequencer based on the processing mode selected
"""
import sys
from logging import getLogger
from pathlib import Path

import pyomo.opt

from temoa.temoa_model.dat_file_maker import db_2_dat
from temoa.temoa_model.run_actions import build_instance, solve_instance, handle_results
from temoa.temoa_model.temoa_config import TemoaConfig
from temoa.temoa_model.temoa_mode import TemoaMode
from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_run import temoa_checks

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/14/23

logger = getLogger(__name__)

class TemoaSequencer:
    """A Sequencer instance to control all runs for a scenario based on the TemoaMode"""

    def __init__(self, config_file: str | Path,
                 output_path: str | Path,
                 mode_override: TemoaMode,
                 **kwargs):
        """
        Create a new Sequencer
        :param config_file: Optional path to config file.  If not provided, it will be read from Command Line Args
        :param mode_override: Optional override to execution mode.  If not provided, it will be read from config file
        """
        self.config: TemoaConfig | None = None
        self.temoa_mode: TemoaMode
        self.config_file: Path = Path(config_file)
        # check it...
        if not self.config_file.is_file():
            logger.error('Config file location passed %s does not point to a file',
                         self.config_file)
            raise FileNotFoundError(f'Invalid config file: {self.config_file}')
        self.output_path: Path = Path(output_path)
        # check it...
        if not self.output_path.is_dir():
            logger.error('Output directory does not exist: %s', self.output_path)
            raise FileNotFoundError(f'Invalid output directory: {self.output_path}')
        self.mode_override: TemoaMode = mode_override

        # for feedback to user
        self.silent = kwargs.get('silent', False)

        # for results catching
        self.pf_results: pyomo.opt.SolverResults | None = None
        self.pf_solved_instance: TemoaModel | None = None

    def start(self) -> TemoaModel | None:
        """ Start the processing of the scenario """

        # Run the preliminaries...
        # Build a TemoaConfig
        self.config = TemoaConfig.build_config(config_file=self.config_file,
                                                output_path=self.output_path)

        # TODO:  Screen this vs. what is already done at this point
        temoa_checks(self.config)

        # Distill the TemoaMode
        self.temoa_mode = self.mode_override if self.mode_override else self.config.scenario_mode
        if not isinstance(self.temoa_mode, TemoaMode):
            logger.error('Temoa Mode not set properly.  Override: %d, Config File: %d',
                         self.mode_override, self.config.scenario_mode)
            raise RuntimeError('Problem with mode selection, see log file.')

        # convert the input file from .sqlite -> .dat if needed
        if self.config.input_file.suffix == '.sqlite':
            dat_file = self.config.input_file.with_suffix('.dat')
            db_2_dat(self.config.input_file, dat_file, self.config)
            # update the config to point to the .dat file newly created
            self.config.input_file = dat_file

        # Get user confirmation if not silent
        if not self.silent:
            try:
                print(self.config.__repr__())
                print('\nPlease press enter to continue or Ctrl+C to quit.\n')
                input()  # Give the user a chance to confirm input
            except KeyboardInterrupt:
                logger.warning('User aborted from confirmation page.  Exiting')
                print('\n\nUser requested quit.  Exiting Temoa ...\n')
                sys.exit()

        # Set up the individual runs & execute
        match self.temoa_mode:
            case TemoaMode.BUILD_ONLY:
                temoa_instance = build_instance(self.config.input_file)
                return temoa_instance
            case TemoaMode.PERFECT_FORESIGHT:
                instance = build_instance(self.config.input_file)
                self.pf_solved_instance, self.pf_results = solve_instance(instance,
                                                                          self.config.solver_name,
                                                                          self.config.save_lp_file)
                handle_results(self.pf_solved_instance, self.pf_results, self.config)
            case _:
                raise NotImplementedError('not yet built')
