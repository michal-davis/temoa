"""
pytest configuration

Written by:  J. F. Hyink
jeff@westernspark.us
https://westernspark.us
Created on:  6/27/23

Tools for Energy Model Optimization and Analysis (Temoa):
An open source framework for energy systems optimization modeling

Copyright (C) 2015,  NC State University

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

A complete copy of the GNU General Public License v2 (GPLv2) is available
in LICENSE.txt.  Users uncompressing this from an archive may not have
received this license file.  If not, see <http://www.gnu.org/licenses/>.


"""

import logging
import os
import shutil

from definitions import PROJECT_ROOT

# set the target folder for output from testing
output_path = os.path.join(PROJECT_ROOT, 'tests', 'testing_log')
if not os.path.exists(output_path):
    os.mkdir(output_path)

    # set up logger in conftest.py so that it is properly anchored in the test folder.
    filename = 'testing.log'
    logging.basicConfig(
        filename=os.path.join(output_path, filename),
        filemode='w',
        format='%(asctime)s | %(module)s | %(levelname)s | %(message)s',
        datefmt='%d-%b-%y %H:%M:%S',
        level=logging.DEBUG,  # <-- global change for testing activities is here
    )

logging.getLogger('pyomo').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('pyutilib').setLevel(logging.WARNING)

# ensure that dummy copies of utopia and test_system databases are available in testing_outputs
# to catch data.  These are just sumps to absorb non-inspected output to keep the input sources "pristine"
data_output_path = os.path.join(PROJECT_ROOT, 'tests', 'testing_outputs')
data_source_path = os.path.join(PROJECT_ROOT, 'tests', 'testing_data')
databases = 'temoa_utopia.sqlite', 'temoa_test_system.sqlite'
for db in databases:
    if not os.path.exists(os.path.join(data_output_path, db)):
        shutil.copy(os.path.join(data_source_path, db), os.path.join(data_output_path, db))
