"""
Entry point for running the model.
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from definitions import PROJECT_ROOT
from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_sequencer import TemoaMode, TemoaSequencer

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  7/18/23

logger = logging.getLogger(__name__)


def runModelUI(config_filename):
    """This function launches the model run from the Temoa GUI"""
    raise NotImplementedError
    # solver = TemoaSolver(model, config_filename)
    # for k in solver.createAndSolve():
    #     yield k
    #     # yield " " * 1024


def runModel(arg_list: list[str] | None = None) -> TemoaModel | None:
    """
    Start the program
    :param arg_list: optional arg_list
    :return: A TemoaModel instance (if asked for), more likely None
    """
    logger.info('*** STARTING TEMOA ***')
    options = parse_args(arg_list=arg_list)
    mode = TemoaMode.BUILD_ONLY if options.build_only else None
    ts = TemoaSequencer(config_file=options.config_file, mode_override=mode, silent=options.silent)
    result = ts.start()
    return result


def parse_args(arg_list: list[str] | None) -> argparse.Namespace:
    """
    Parse the command line args (CLA) if None is passed in (normal operation) or the arg_list, if provided
    :param arg_list: default None --> process sys.argv
    :return:  options Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='Path to file containing configuration information.',
                        action='store',
                        dest='config_file', default=None)
    parser.add_argument('-b', '--build-only',
                        help='Build and return an unsolved TemoaModel instance.',
                        action='store_true',
                        dest='build_only')
    parser.add_argument('-s', '--silent', help='Silent run.  No prompts.', action='store_true',
                        dest='silent')
    parser.add_argument('-d', '--debug',
                        help='Set logging level to DEBUG to see debugging output in log file.',
                        action='store_true',
                        dest='debug')

    options = parser.parse_args(args=arg_list)  # note:  The default (if None) is sys.argv

    # initialize the logging now that option is known...
    setup_logging(options.debug)

    # check for config file existence
    if not options.config_file:
        logger.error(
            'No config file found in CLA.  Temoa needs a config file to operate, see documentation.')
        raise AttributeError('no config file provided.')
    else:
        # convert it to a Path, if it isn't one already
        options.config_file = Path(options.config_file)
    if not options.config_file.is_file():
        logger.error('Config file provided: %s is not valid', options.config_file)
        raise FileNotFoundError('Config file not found.  See log for info.')

    logger.debug('Received Command Line Args: %s', sys.argv[1:])

    if options.build_only:
        logger.info('Build-only selected.')
    return options


def setup_logging(debug_level=False):
    # set the target folder for logging output from this run
    output_path = os.path.join(PROJECT_ROOT, "output_files",
                               datetime.now().strftime("%Y-%m-%d %H%Mh"))
    if not os.path.exists(output_path):
        os.mkdir(output_path)

    # set up logger
    if debug_level:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logger = logging.getLogger(__name__)
    logging.getLogger("pyomo").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    filename = "log.log"
    logging.basicConfig(
        filename=os.path.join(output_path, filename),
        filemode="w",
        format="%(asctime)s | %(module)s | %(levelname)s | %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        level=level
    )
    logger.info('Starting Program')


if __name__ == '__main__':
    runModel()
