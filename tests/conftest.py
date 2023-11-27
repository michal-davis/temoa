import logging
import os
import shutil

from definitions import PROJECT_ROOT

# set the target folder for output from testing
output_path = os.path.join(PROJECT_ROOT, "tests", "test_log")
if not os.path.exists(output_path):
    os.mkdir(output_path)

    # set up logger in conftest.py so that it is properly anchored in the test folder.
    filename = "testing.log"
    logging.basicConfig(
        filename=os.path.join(output_path, filename),
        filemode="w",
        format="%(asctime)s | %(module)s | %(levelname)s | %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        level=logging.DEBUG,  # <-- global change for testing activities is here
    )

logging.getLogger("pyomo").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("pyutilib").setLevel(logging.WARNING)

# ensure that dummy copies of utopia and test_system databases are available in testing_outputs
# to catch data.  These are just sumps to absorb non-inspected output to keep the input sources "pristine"
data_output_path = os.path.join(PROJECT_ROOT, 'tests', 'testing_outputs')
data_source_path = os.path.join(PROJECT_ROOT, 'tests', 'testing_data')
databases = 'temoa_utopia.sqlite', 'temoa_test_system.sqlite'
for db in databases:
    if not os.path.exists(os.path.join(data_output_path, db)):
        shutil.copy(os.path.join(data_source_path, db), os.path.join(data_output_path, db))
