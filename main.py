"""
new entry point for running the model.
"""
import logging
import os
from datetime import datetime

from definitions import PROJECT_ROOT
# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us

# Created on:  7/18/23


from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_run import TemoaSolver

def runModelUI(config_filename):
    """This function launches the model run from the Temoa GUI"""
    raise NotImplementedError
    solver = TemoaSolver(model, config_filename)
    for k in solver.createAndSolve():
        yield k
        # yield " " * 1024


def runModel():
    """This function launches the model run, and is invoked when called from
    __main__.py"""

    dummy = ""  # If calling from command line, send empty string
    model = TemoaModel()
    solver = TemoaSolver(model, dummy)
    for k in solver.createAndSolve():
        pass

if __name__ == '__main__':
    # set the target folder for logging output from this run
    output_path = os.path.join(PROJECT_ROOT, "output_files", datetime.now().strftime("%Y-%m-%d %H%Mh"))
    if not os.path.exists(output_path):
        os.mkdir(output_path)

    # set up logger
    logger = logging.getLogger(__name__)
    logging.getLogger("pyomo").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    filename = "log.log"
    logging.basicConfig(
        filename=os.path.join(output_path, filename),
        filemode="w",
        format="%(asctime)s | %(module)s | %(levelname)s | %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        level=logging.DEBUG,  # <-- global change for project is here
    )

    runModel()