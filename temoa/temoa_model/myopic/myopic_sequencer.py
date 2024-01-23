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
from collections import deque, defaultdict
from pathlib import Path
from shutil import copyfile
from sqlite3 import Connection, Cursor
from sys import stderr as SE

from pyomo.core import value
from pyomo.dataportal import DataPortal

import definitions
from temoa.temoa_model import run_actions
from temoa.temoa_model.myopic.hybrid_loader import HybridLoader
from temoa.temoa_model.myopic.myopic_index import MyopicIndex
from temoa.temoa_model.temoa_config import TemoaConfig
from temoa.temoa_model.temoa_model import TemoaModel

logger = logging.getLogger(__name__)

table_script_file = Path(
    definitions.PROJECT_ROOT, 'temoa/temoa_model/myopic', 'make_myopic_tables.sql'
)


class MyopicSequencer:
    """
    A sequencer for solving myopic problems
    """

    # these are the tables that are incrementally built by the myopic instances
    myopic_tables = [
        'MyopicCapacity',
        'MyopicCost',
        'MyopicEmission',
        'MyopicCurtailment',
        'MyopicRetirement',
        'MyopicFlowIn',
        'MyopicFlowOut',
        'MyopicEfficiency',
    ]

    def __init__(self, config: TemoaConfig | None):
        self.capacity_epsilon = 1e-5
        self.debugging = False
        self.optimization_periods: list[int] | None = None
        self.instance_queue: deque[MyopicIndex] = deque()  # a LIFO queue
        self.config = config
        # establish a connection to the controlling db
        # allow a "shunt" here so we can test parts of this by passing a None config
        self.con = self.get_connection() if isinstance(config, TemoaConfig) else None
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
                raise ValueError(f'view_depth is not an integer {self.view_depth}')
            self.step_size: int = myopic_options.get('step_size')
            if not isinstance(self.step_size, int):
                raise ValueError(f'step_size is not an integer {self.step_size}')
            if self.step_size > self.view_depth:
                raise ValueError(
                    f'the Myopic step size({self.step_size}) '
                    f'is larger than the view depth ({self.view_depth}).  '
                    f'Check config'
                )

    @property
    def cursor(self) -> Cursor:
        """
        cursor for the db
        :return: cursor for the session started in the database
        """
        # doing this as a property is a preventative measure to isolate the cursor
        # (it can't be overwritten)
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

        # clear out the old riff-raff
        self.drop_old_results()

        # create the Myopic Output tables
        self.execute_script(table_script_file)

        # start the MyopicEfficiency table.  (need to do this prior to data build to get Existing
        # Capacity accounted for
        self.initialize_myopic_efficiency_table()

        # make a data loader
        data_loader = HybridLoader(self.con)  # DataPortalLoader(self.config.input_file)

        # start the fundamental control loop
        # 1.  get feedback from previous instance execution (optimal/infeasible/...)
        # 2.  decide what to do about it
        # 3.  pull the next instance from the queue (if !empty & if needed)
        # 4.  pull data for next run, adjust as necessary
        # 5.  Add to the MyopicEfficiency table
        # 6.  build instance, run, assess
        # 7.  commit or back out any data as necessary
        # 8.  report findings

        # reusables...
        data_portal = DataPortal()
        offset_periods = 0
        last_instance_status = None  # solve status
        last_base_year = None
        idx: MyopicIndex  # just a type-hint
        logger.info('Starting Myopic Sequence')
        while len(self.instance_queue) > 0:
            if last_instance_status is None:
                offset_periods = 0
                idx = self.instance_queue.pop()
                last_base_year = idx.base_year  # starting here
            elif last_instance_status == 'optimal':
                offset_periods = 0
                idx = self.instance_queue.pop()

            elif last_instance_status == 'roll_back':
                offset_periods -= 1
                curr_start_idx = self.optimization_periods.index(idx.base_year)
                new_start_idx = curr_start_idx + offset_periods
                if new_start_idx < 0:
                    logger.error('Failed myopic iteration.  Cannot back up any further.')
                    raise RuntimeError(
                        'Myopic iteration failed during attempt to back up recursively before start of optimization period.'
                    )
                # roll back the start year by making a new index, increase the depth, keep the same last year
                base_year = self.optimization_periods[new_start_idx]
                idx = MyopicIndex(
                    base_year=base_year,
                    depth=idx.depth + 1,
                    last_demand_year=idx.last_demand_year,
                    last_year=idx.last_year,
                )
            else:
                raise RuntimeError('Illegal state in myopic iteration.')
            logger.info('Processing Myopic Index: %s', idx)

            # 4. update the MyopicEfficiency table so it is ready for the data pull.
            self.update_myopic_efficiency_table(myopic_index=idx, prev_base=last_base_year)

            # 5. pull the data
            print(f'\n\nPulling data for: {idx}')
            data_portal = data_loader.load_data_portal(
                myopic_index=idx
            )  # just make a new data portal...they are untrustworthy...

            # 6. build/solve/assess
            instance = run_actions.build_instance(
                loaded_portal=data_portal,
                model_name=self.config.scenario,
                silent=self.config.silent,
            )
            model, results = run_actions.solve_instance(
                instance=instance,
                solver_name=self.config.solver_name,
                silent=self.config.silent,
                keep_LP_files=self.config.save_lp_file,
            )
            optimal, status = run_actions.check_solve_status(results)
            if not optimal:
                logger.warning('Completed myopic iteration on %s', idx)
                logger.warning('Status: %s', status)
                # clear the results from the previous period...
                # TODO:  Fix this...
                # previous_period_index = self.optimization_periods.index(idx.base_year) - 1
                # previous_period = self.optimization_periods[previous_period_index]
                # self.clear_results(previous_period)
                # restart loop
                last_instance_status = 'roll_back'
                continue

            logger.info('Completed myopic iteration on %s', idx)
            # 7.  Update the output tables...
            self.update_output_tables(idx, model)

            # prep next loop
            last_base_year = idx.base_year  # update
            last_instance_status = 'optimal'  # simulated...

            # TODO:  screen candy here for progress...


    def update_output_tables(self, myopic_idx: MyopicIndex, model: TemoaModel) -> None:
        data = defaultdict(dict)
        for r, p, t, v in model.V_Capacity:
            # start at base year, to prevent re-writing existing
            # stop before step year, which will be written in next iteration
            if myopic_idx.base_year <= v < myopic_idx.step_year:
                val = value(model.V_Capacity[r, p, t, v])
                if abs(val) < self.capacity_epsilon:
                    continue
                # we only need to capture for the vintage
                # TODO:  Come back to this after we look at retirements/curtailment
                if p < myopic_idx.step_year:
                    data['V_Capacity'][r, p, t, v] = val
                    continue
        for (r, p, t, v), val in data['V_Capacity'].items():
            # print(r, t, v, val)
            lifetime = model.LifetimeProcess[r, t, v]
            try:
                self.cursor.execute(
                    'INSERT INTO MyopicCapacity ' f'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (myopic_idx.base_year, self.config.scenario, r, p, t, v, val, lifetime),
                )
            except sqlite3.IntegrityError:
                print(f'choked on : {myopic_idx.base_year, r, p, t, v}')
        self.con.commit()

    def characterize_run(self, future_periods: list[int] | None = None) -> None:
        """
        inspect the db and create the MyopicIndex items
        :param future_periods: list of future period labels (years), normally None. (for test)
        :return:
        """
        if not future_periods:
            future_periods = self.cursor.execute(
                "SELECT t_periods FROM main.time_periods WHERE flag = 'f'"
            ).fetchall()
            future_periods = sorted(t[0] for t in future_periods)

        # check that we have enough periods to do myopic run
        # 2 iterations, excluding end year, will be via shortened depth, if reqd.
        if len(future_periods) < 3:
            logger.error('Not enough future years to run myopic mode: %d', len(future_periods))
        self.optimization_periods = future_periods.copy()
        last_idx = len(future_periods) - 1
        for idx in range(0, len(future_periods[:-1]), self.step_size):
            depth = min(self.view_depth, last_idx - idx)
            step = min(self.step_size, last_idx - idx)
            if depth < 1:
                break
            myopic_idx = MyopicIndex(
                base_year=future_periods[idx],
                step_year=future_periods[idx + step],
                last_demand_year=future_periods[idx + depth - 1],
                last_year=future_periods[idx + depth],
            )
            self.instance_queue.appendleft(
                myopic_idx
            )  # Add to left, we will pop right, so FIFO for these
            logger.debug('Added myopic index %s', myopic_idx)
        logger.info('myopic run is divided into %d instances', len(self.instance_queue))

    def execute_script(self, script_file: Path):
        """
        Execute a sql script on the current db connection
        :return:
        """
        with open(script_file, 'r') as table_script:
            sql_commands = table_script.read()
        logger.debug('Executing sql from file: %s on connection: %s', script_file, self.con)
        self.cursor.executescript(sql_commands)

    def drop_old_results(self):
        """
        Drop old results tables
        :return:
        """
        logger.debug('Dropping old myopic result tables...')
        for table in self.myopic_tables:
            self.cursor.execute(f'DROP TABLE IF EXISTS {table};')

    def clear_results(self, period):
        """
        clear the results tables for the period specified
        :param period: the period (year) to clear
        :return:
        """
        if period not in self.optimization_periods:
            logger.error(
                'Tried to clear period results for %s that is not in %s',
                period,
                self.optimization_periods,
            )
            raise ValueError(f'Trying to clear a year {period} that is not in the optimize periods')
        logger.debug('Clearing period %s', period)
        for table in self.myopic_tables:
            self.cursor.execute(f'DELETE FROM {table} WHERE period = {period}')

    def __del__(self):
        """ensure the connection is closed when destructor is called."""
        if hasattr(self, 'con') and self.con is not None:  # it may not be constructed yet...
            self.con.close()

    def initialize_myopic_efficiency_table(self):
        """
        create a new MyopicEfficiency table and pre-load it with all ExistingCapacity
        :return:
        """
        # the -1 is used to indicate "existing" for flag purposes
        # we will just use the "existing" flag in the orig db to set this up and capture
        # all values in those vintages as "existing"
        default_lifetime = TemoaModel.default_lifetime_tech
        query = (
            'INSERT INTO MyopicEfficiency '
            '  SELECT -1, main.Efficiency.regions, input_comm, Efficiency.tech, Efficiency.vintage, output_comm, efficiency, '
            f'  coalesce(main.LifetimeProcess.life_process, main.LifetimeTech.life, {default_lifetime}) AS lifetime '
            '   FROM main.Efficiency '
            '    LEFT JOIN main.LifetimeProcess '
            '       ON main.Efficiency.tech = LifetimeProcess.tech '
            '       AND main.Efficiency.vintage = LifetimeProcess.vintage '
            '       AND main.Efficiency.regions = LifetimeProcess.regions '
            '    LEFT JOIN main.LifetimeTech '
            '       ON main.Efficiency.tech = main.LifetimeTech.tech '
            '     AND main.Efficiency.regions = main.LifeTimeTech.regions '
            '   JOIN time_periods '
            '   ON Efficiency.vintage = time_periods.t_periods '
            "   WHERE flag = 'e'"
        )

        if self.debugging:
            print(query)
        self.cursor.execute(query)
        self.con.commit()

        if self.debugging:
            q2 = (
                "SELECT '-1', regions, input_comm, tech, vintage, output_comm, efficiency "
                'FROM Efficiency '
                '   JOIN time_periods '
                '   ON Efficiency.vintage = time_periods.t_periods '
                "   WHERE flag = 'e'"
            )
            res = self.cursor.execute(q2).fetchall()
            print(list(res))

    def update_myopic_efficiency_table(self, myopic_index: MyopicIndex, prev_base: int):
        """
        This function adds to (or creates) a MyopicEfficiency table in the db with data specific
        to the MyopicIndex timeframe.
        :return:
        """
        # Dev Note:  The efficiency table drives the show for the model and is also used
        # internally to validate commodities, techs, etc.  So by making a period-accurate
        # efficiency table, we can bounce our other queries off of it to get accurate
        # data out of the DB, instead of dealing with it model-side

        # We already captured the ExistingCapacity efficiency values when the table
        # was initialized, so now we need to incrementally add to it with:
        # 1.  REMOVE things that were NOT added to the MyopicCapacity from the last year (if any)
        # 2.  The new stuff that is visible in the current myopic period

        base = myopic_index.base_year
        last_demand_year = myopic_index.last_demand_year

        # 0.  Clear any future things past the base year for housekeeping
        #     ease with steps, depth, etc.
        # TODO:  We *might* be able to do something more efficient here and just keep adding
        #        but this should be most reliable way for now.
        self.cursor.execute(
            'DELETE FROM MyopicEfficiency WHERE ' f'MyopicEfficiency.vintage >= {base}'
        )
        self.con.commit()

        # 1.  Clean up stuff not implemented
        query = (
            'DELETE FROM MyopicEfficiency WHERE NOT EXISTS ('
            '  SELECT * FROM MyopicCapacity WHERE '
            '    MyopicEfficiency.region = MyopicCapacity.region AND '
            '    MyopicEfficiency.tech = MyopicCapacity.tech AND '
            '    MyopicEfficiency.vintage = MyopicCapacity.vintage) AND '
            f'    MyopicEfficiency.vintage >= {prev_base}'
        )

        if self.debugging:
            debug_query = (
                'SELECT * FROM MyopicEfficiency WHERE NOT EXISTS ('
                '  SELECT * FROM MyopicCapacity WHERE '
                '    MyopicEfficiency.region = MyopicCapacity.region AND '
                '    MyopicEfficiency.tech = MyopicCapacity.tech AND '
                '    MyopicEfficiency.vintage = MyopicCapacity.vintage) AND '
                f'    MyopicEfficiency.vintage >= {prev_base}'
            )
            print('\n\n **** Removing these unused region-tech-vintage combos ****')
            print(debug_query)
            removals = self.cursor.execute(debug_query).fetchall()
            for i, removal in enumerate(removals):
                print(f'{i}. Removing:  {removal}')
        self.cursor.execute(query)
        self.con.commit()

        # 2.  Add the new stuff now visible
        lifetime = TemoaModel.default_lifetime_tech
        query = (
            'INSERT INTO MyopicEfficiency '
            f'SELECT {base}, Efficiency.regions, input_comm, '
            '      Efficiency.tech, Efficiency.vintage, output_comm, efficiency, '
            f'     coalesce(main.LifetimeProcess.life_process, main.LifetimeTech.life, {lifetime}) '
            f'     AS lifetime '
            ' FROM main.Efficiency '
            '    LEFT JOIN main.LifetimeProcess '
            '       ON main.Efficiency.tech = LifetimeProcess.tech '
            '       AND main.Efficiency.vintage = LifetimeProcess.vintage '
            '       AND main.Efficiency.regions = LifetimeProcess.regions '
            '    LEFT JOIN main.LifetimeTech '
            '       ON main.Efficiency.tech = main.LifetimeTech.tech '
            '     AND main.Efficiency.regions = main.LifeTimeTech.regions '
            f'  WHERE Efficiency.vintage >= {base}'
            f'  AND Efficiency.vintage <= {last_demand_year}'
        )
        if self.debugging:
            x = self.cursor.execute(
                f'SELECT {base}, regions, input_comm, tech, vintage, output_comm, efficiency '
                'FROM Efficiency '
                f'  WHERE Efficiency.vintage >= {base}'
                f'  AND Efficiency.vintage <= {last_demand_year}'
            ).fetchall()
            print('\n\n **** adding to MyopicEfficiency table from newly visible techs ****')
            for idx, t in enumerate(x):
                print(idx, t)
            print()
        self.cursor.execute(query)
        self.con.commit()  # MUST commit here to push the INSERTs
