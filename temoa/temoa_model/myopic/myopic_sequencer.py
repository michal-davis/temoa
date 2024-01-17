"""
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


Written by:  J. F. Hyink
jeff@westernspark.us
https://westernspark.us
Created on:  1/15/24

"""
import logging
import sqlite3
from collections import namedtuple
from pathlib import Path
from queue import Queue
from shutil import copyfile
from sqlite3 import Connection, Cursor
from sys import stderr as SE

import definitions
from temoa.temoa_model.myopic.myopic_loader import LoadStatementGenerator
from temoa.temoa_model.temoa_config import TemoaConfig
from temoa.temoa_model.temoa_model import TemoaModel

logger = logging.getLogger(__name__)

MyopicIndex = namedtuple('MyopicIndex', ['base_year', 'depth', 'last_year'])
table_script_file = Path(definitions.PROJECT_ROOT, 'temoa/temoa_model', 'make_myopic_tables.sql')


class MyopicSequencer:
    """
    A sequencer for solving myopic problems
    """

    # these are the tables that are incrementally built by the myopic instances
    myopic_tables = [
        'MyopicCapacity',
        'MyopicCost',
        'MyopicEmissions',
        'MyopicCurtailment',
        'MyopicRetirement',
        'MyopicFlowIn',
        'MyopicFlowOut',
    ]

    def __init__(self, config: TemoaConfig):
        self.instance_queue: Queue[MyopicIndex] = Queue()  # a FIFO queue
        self.config = config
        # establish a connection to the controlling db
        self.con = self.get_connection()
        # break out what is needed from the config
        myopic_options = config.myopic_inputs
        if not myopic_options:
            logger.error(
                'The myopic mode was selected, but no options were received.\n %s',
                config.myopic_inputs,
            )
            raise RuntimeError('No myopic options received.  See log file.')
        else:
            self.view_depth: int = myopic_options.get('view_depth')
            if not isinstance(self.view_depth, int):
                raise RuntimeError(f'view_depth is not an integer {self.view_depth}')

    @property
    def cursor(self) -> Cursor:
        return self.con.cursor()

    def get_connection(self) -> Connection:
        """
        Get a connection to the output database

        :return: a database connection
        """
        input_file = self.config.input_file
        output_db = self.config.output_database
        output_path = self.config.output_path

        if input_file.suffix not in {'.db', '.sqlite'}:
            logger.error(
                'The myopic mode processing only currently supports sourcing from a '
                'sqlite database.  Input file specified: %s',
                input_file,
            )
            raise RuntimeError('Received improper input file type.  See log file.')

        # check to see if the output_db IS the input_db, if so go forward with it.  If not,
        # make a copy of the input db in the output_path folder and use that, disregarding
        # the output db and warning user
        # TODO:  handle a "null" for output DB here and in the temoa_sequencer
        if input_file == output_db:
            con = sqlite3.connect(input_file)
            logger.info('Connected to database: %s', input_file)
        else:
            msg = (
                'Currently, myopic mode output can either target the original input db or a\n'
                'copy of the input db.  Connecting to a secondary db is not currently\n'
                'permitted to ensure data integrity for the run, as the run will use data from\n'
                'the input db and generated data in the output db.\n\n'
                'A copy of the input db will be used and place in the output folder.\n'
            )
            SE.write(msg)
            logger.warning(
                'The output db was disregarded, and the output will be sent to a '
                'copied db in the output folder.'
            )
            new_db_name = input_file.name
            new_db_path = output_path / new_db_name
            copyfile(input_file, new_db_path)
            con = sqlite3.connect(new_db_path)
            logger.info('Established connection to copied db at: %s', new_db_path)

        return con

    def start(self):
        # load up the instance queue
        self.characterize_run()
        # create the Myopic Output tables
        self.execute_script(table_script_file)
        first_model = TemoaModel()
        data_loader = LoadStatementGenerator(self.config.input_file, M=first_model)
        data_loader.load_data_portal()

    def characterize_run(self):
        """
        inspect the db and create the MyopicIndex items
        :return:
        """
        all_periods = self.cursor.execute('SELECT * FROM main.time_periods').fetchall()
        future_periods = self.cursor.execute(
            "SELECT t_periods FROM main.time_periods WHERE flag = 'f'"
        ).fetchall()
        future_periods = sorted(t[0] for t in future_periods)

        # check that we have enough periods to do myopic run
        if len(future_periods) < 3:  # 2 iterations, excluding end year
            logger.error('Not enough future years to run myopic mode: %d', len(future_periods))
        last_idx = len(future_periods) - 1
        for idx, year in enumerate(future_periods[:-1]):
            depth = min(self.view_depth, last_idx - idx + 1)
            myopic_idx = MyopicIndex(
                base_year=year, depth=depth, last_year=future_periods[idx + depth - 1]
            )
            self.instance_queue.put(myopic_idx)
            logger.debug('Added myopic index %s', myopic_idx)
        logger.info('myopic run is divided into %d instances', self.instance_queue.qsize())

    def execute_script(self, script_file: Path):
        """
        Execute a sql script on the current db connection
        :return:
        """
        with open(script_file, 'r') as table_script:
            sql_commands = table_script.read()
        logger.debug('Executing sql from file: %s on connection: %s', script_file, self.con)
        self.cursor.executescript(sql_commands)

    def __del__(self):
        """ensure the connection is closed when destructor is called."""
        if hasattr(self, 'con'):  # it may not be constructed yet...
            self.con.close()
