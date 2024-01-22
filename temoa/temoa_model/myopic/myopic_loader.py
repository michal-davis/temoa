"""

The purpose of this module is encapsulate the sql statements to properly load the model and perhaps
be reusable for modes other than myopic.


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
Created on:  1/16/24

"""
import logging
import time
from collections import namedtuple
from itertools import cycle
from pathlib import Path

from pyomo.dataportal import DataPortal

from temoa.temoa_model.myopic.myopic_index import MyopicIndex
from temoa.temoa_model.temoa_model import TemoaModel

logger = logging.getLogger(__name__)

# some conveniences for organizing...
SetStatement = namedtuple('SetStatement', ['file_path', 'set_ref', 'query'])
ParamStatement = namedtuple('ParamStatement', ['file_path', 'param_ref', 'query'])


class DataPortalLoader:
    def __init__(self, input_db_path: Path):
        """
        A framework to load a data portal with data for a Temoa model
        :param input_db_path: the path to the .sqlite database
        :param base_year: The first year to load
        :param last_demand_year: The last year to gather demands for, typically period before last year
        :param last_year: The last year
        """

        # pop in some defaults
        self.myopic_load: bool = False
        self.base_year = -1
        self.last_demand_year = 1000000
        self.end_year = 1000000

        self.file_path: str = str(input_db_path)  # pyomo wants *string* path for loading portal
        self.M = TemoaModel()  # just an empty to get references to the sets
        self.debugging = False  # for extra output.  Remove later?  Maybe

    def load_data_portal(
        self, myopic_index: MyopicIndex | None = None, portal: DataPortal | None = None
    ) -> DataPortal:
        # use the start/stop from the myopic_index, if one was provided...
        match myopic_index:
            case MyopicIndex():
                self.base_year = myopic_index.base_year
                self.last_demand_year = myopic_index.last_demand_year
                self.end_year = myopic_index.last_year
                self.myopic_load = True
            case None:  # possible future use for all loading...
                # TODO:  perhaps pulse the DB to get actual values here or such to make this bullet-proof
                self.base_year = -1
                self.last_demand_year = 1000000
                self.end_year = 1000000
                self.myopic_load = False
            case _:
                raise ValueError(f'Received invalid myopic_index: {myopic_index}')

        tic = time.time()
        if portal is None:
            portal = DataPortal()
        portal.connect(using='sqlite3', filename=self.file_path)
        set_statements = self.generate_set_statements(self.myopic_load)
        for ss in set_statements:
            if self.debugging:
                print(ss.query, ss.set_ref)
            portal.load(query=ss.query, set=ss.set_ref)
        # Dev Note:  transitioning from sets to params appears to induce data corruption if the connection is
        # not reset, unless I'm doing it wrong.  GitHub Issue for pyomo submitted....
        portal.disconnect()
        portal.connect(using='sqlite3', filename=self.file_path)
        for ps in self.generate_param_statements(self.myopic_load):
            if self.debugging:
                print(ps.query)
            portal.load(query=ps.query, param=ps.param_ref)
        toc = time.time()
        portal.disconnect()
        print(f'Load time: {toc - tic: .4f} seconds')
        logging.debug('Load time for DataPortal using SQL queries: %0.4f seconds', (toc - tic))
        if self.debugging:
            for item in portal.items():
                print(item)

        return portal

    def generate_set_statements(self, myopic_load: bool) -> list[SetStatement]:
        sy = self.base_year
        ey = self.end_year
        query_set_pairs = []
        # If the load is "myopic" we need to take granular control of the times loaded...
        # else we can rely on the flags
        if myopic_load:
            time_pairs = (
                # time based sets
                (
                    self.M.time_exist,
                    f'SELECT t_periods from main.time_periods WHERE t_periods < {sy}',
                ),
                (
                    self.M.time_future,
                    'SELECT t_periods from main.time_periods WHERE '
                    f't_periods >= {sy} AND t_periods <= {ey}',
                ),
            )
        else:
            time_pairs = (
                # time based sets
                (self.M.time_exist, f"SELECT t_periods from main.time_periods WHERE flag = 'e'"),
                # note:  We still want to screen for "f" to ensure we can never bring
                # "existing" into scope.
                (self.M.time_future, f"SELECT t_periods from main.time_periods WHERE flag = 'f'"),
            )
        query_set_pairs.extend(time_pairs)

        tech_filter = 'JOIN main.MyopicEfficiency ON tech'
        other_set_pairs = (
            (self.M.time_of_day, 'SELECT t_day FROM main.time_of_day'),
            (self.M.time_season, 'SELECT t_season FROM main.time_season'),
            # regions...
            (self.M.regions, 'SELECT regions FROM main.regions'),
            # TODO:  will need to do RegionalGlobalIndices later as we did in db_to_dat
            # TODO:  The below is janky way to build all tech, but this is how model runs RN.
            (self.M.tech_resource, f"SELECT tech FROM main.technologies {tech_filter} WHERE flag = 'r'"),
            (self.M.tech_production, "SELECT tech FROM main.technologies WHERE flag LIKE 'p%'"),
            (self.M.tech_baseload, "SELECT tech FROM main.technologies WHERE flag ='pb'"),
            (self.M.tech_storage, "SELECT tech FROM main.technologies WHERE flag = 'ps'"),
            (self.M.tech_reserve, 'SELECT tech FROM main.tech_reserve'),
            (self.M.tech_annual, f'SELECT tech FROM main.tech_annual'),
            (self.M.commodity_demand, "SELECT comm_name FROM main.commodities WHERE flag = 'd'"),
            (self.M.commodity_emissions, "SELECT comm_name FROM main.commodities WHERE flag = 'e'"),
            (self.M.commodity_physical, "SELECT comm_name FROM main.commodities WHERE flag = 'p'"),
        )
        query_set_pairs.extend(other_set_pairs)

        # process them...
        result = [
            SetStatement(fp, q, s)
            for (fp, (q, s)) in zip(cycle((self.file_path,)), query_set_pairs)
        ]
        return result

    def generate_param_statements(self, myopic_load: bool) -> list[ParamStatement]:
        by = self.base_year
        ldy = self.last_demand_year
        ey = self.end_year
        query_param_pairs = []

        # let's handle the EFFICIENCY differently if it is myopic or not.
        if myopic_load:
            # Load the efficiency from the MyopicEfficiency table that is being built...
            efficiency_pair = (
                self.M.Efficiency,
                'SELECT region, input_comm, tech, vintage, output_comm, efficiency FROM MyopicEfficiency',
            )
        else:
            efficiency_pair = (
                self.M.Efficiency,
                'SELECT regions, input_comm, tech, vintage, output_comm, efficiency '
                'FROM main.Efficiency',
            )
        query_param_pairs.append(efficiency_pair)

        # handle EXISTING CAPACITY differently...  Myopic needs ExistingCap + what has been built
        # in previous periods
        if myopic_load:
            capacity_pair = (
                self.M.ExistingCapacity,
                f'SELECT region, tech, vintage, capacity FROM main.MyopicCapacity '
                'UNION '
                'SELECT regions, tech, vintage, exist_cap FROM main.ExistingCapacity',
            )
        else:
            capacity_pair = (
                self.M.ExistingCapacity,
                'SELECT regions, tech, vintage, exist_cap FROM main.ExistingCapacity',
            )
        query_param_pairs.append(capacity_pair)

        standard_param_pairs = (
            (self.M.GlobalDiscountRate, 'SELECT rate FROM main.GlobalDiscountRate'),
            (self.M.SegFrac, 'SELECT season_name, time_of_day_name, segfrac FROM main.SegFrac'),
            # DemandDefaultDistribution?
            (
                self.M.DemandSpecificDistribution,
                'SELECT regions, season_name, time_of_day_name, demand_name, dds FROM '
                'main.DemandSpecificDistribution',
            ),
            (
                self.M.Demand,
                f'SELECT regions, periods, demand_comm, demand FROM main.Demand '
                f'WHERE {by} <= Demand.periods AND Demand.periods <= {ldy}',
            ),
            # ResourceBound
            (self.M.CapacityToActivity, 'SELECT regions, tech, c2a FROM main.CapacityToActivity'),
            (
                self.M.CapacityFactorTech,
                'SELECT regions, season_name, time_of_day_name, tech, cf_tech '
                'from main.CapacityFactorTech',
            ),
            # cap factor process
            # lifetime tech
            # lifetime process
            # loan tech / process
            # tech input
            # tech split avg
            # tech output split
            # RPS
            (
                self.M.CostFixed,
                'SELECT regions, periods, CostFixed.tech, CostFixed.vintage, cost_fixed FROM '
                'main.CostFixed JOIN main.MyopicEfficiency '
                '    ON CostFixed.regions = MyopicEfficiency.region '
                '    AND CostFixed.tech = MyopicEfficiency.tech '
                '    AND CostFixed.vintage = MyopicEfficiency.vintage '
                f'WHERE {by} <= CostFixed.periods AND CostFixed.periods <= {ldy}',
            ),
            (
                self.M.CostInvest,
                'SELECT regions, tech, vintage, cost_invest FROM main.CostInvest '
                f'WHERE {by} <= CostInvest.vintage AND CostInvest.vintage <= {ldy}',
            ),
            (
                self.M.CostVariable,
                'SELECT regions, periods, CostVariable.tech, CostVariable.vintage, cost_variable '
                'FROM main.CostVariable JOIN main.MyopicEfficiency '
                '    ON CostVariable.regions = MyopicEfficiency.region '
                '    AND CostVariable.tech = MyopicEfficiency.tech '
                '    AND CostVariable.vintage = MyopicEfficiency.vintage '
                f'WHERE {by} <= CostVariable.periods AND CostVariable.periods <= {ldy}',
            ),
            # Discount Rate
            # ...
        )
        query_param_pairs.extend(standard_param_pairs)

        result = [
            ParamStatement(fp, q, s)
            for (fp, (q, s)) in zip(cycle((self.file_path,)), query_param_pairs)
        ]

        return result
