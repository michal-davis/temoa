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
from collections import namedtuple
from itertools import cycle
from pathlib import Path

from pyomo.dataportal import DataPortal

from temoa.temoa_model.temoa_model import TemoaModel

logger = logging.getLogger(__name__)

# some conveniences for organizing...
SetStatement = namedtuple('SetStatement', ['file_path', 'set_ref','query' ])
ParamStatement = namedtuple('ParamStatement', ['file_path', 'param_ref','query'])


class LoadStatementGenerator:

    def __init__(self, input_db_path: Path, start_year=-1, end_year=1000000):
        """
        A framework to load a data portal with data for a Temoa model
        :param input_db_path: the path to the .sqlite database
        :param start_year:
        :param end_year:
        """
        self.start_year = start_year
        self.end_year = end_year
        self.file_path: str = str(input_db_path)  # pyomo wants string name for loading portal
        self.M = TemoaModel()  # just an empty to get references to the sets

    def load_data_portal(self, portal: DataPortal | None = None) -> DataPortal:
        if portal is None:
            portal = DataPortal()
        set_statements = self.generate_set_statements()
        for ss in set_statements:
            portal.load(filename=ss.file_path, using='sqlite3', query=ss.query, set=ss.set_ref)
        for ps in self.generate_param_statements():
            print(ps.query)
            portal.load(filename=ps.file_path, using='sqlite3', query=ps.query, param=ps.param_ref)

        for item in portal.items():
            print(item)

        return portal

    def generate_set_statements(self) -> list[SetStatement]:
        sy = self.start_year
        ey = self.end_year
        result: list[SetStatement] = []
        query_set_pairs = (
            # time based sets
            (self.M.time_exist,         f"SELECT t_periods from main.time_periods WHERE flag = 'e'"),
            # note:  We still want to screen for "f" to ensure we can never bring "existing" into scope.
            (self.M.time_future,        f"SELECT t_periods from main.time_periods WHERE flag = 'f' AND t_periods >= {sy} AND t_periods <= {ey}"),
            (self.M.time_of_day,        "SELECT t_day FROM main.time_of_day"),
            (self.M.time_season,        "SELECT t_season FROM main.time_season"),

            # regions...
            (self.M.regions,            "SELECT regions FROM main.regions"),
            # TODO:  will need to do RegionalGlobalIndices later as we did in db_to_dat, by scanning tables...
            # TODO:  The below is janky way to build all tech, but this is how model runs RN.
            (self.M.tech_resource,      "SELECT tech FROM main.technologies WHERE flag = 'r'" ),
            (self.M.tech_production,    "SELECT tech FROM main.technologies WHERE flag LIKE 'p%'"),
            (self.M.tech_baseload,      "SELECT tech FROM main.technologies WHERE flag ='pb'"),
            (self.M.tech_storage,       "SELECT tech FROM main.technologies WHERE flag = 'ps'"),
            (self.M.tech_reserve,       "SELECT tech FROM main.tech_reserve"),

            (self.M.tech_annual,        f"SELECT tech FROM main.tech_annual"),

            (self.M.commodity_demand,   "SELECT comm_name FROM main.commodities WHERE flag = 'd'"),
            (self.M.commodity_emissions,"SELECT comm_name FROM main.commodities WHERE flag = 'e'"),
            (self.M.commodity_physical, "SELECT comm_name FROM main.commodities WHERE flag = 'p'"),

        )
        result = [SetStatement(fp, q, s) for (fp, (q, s)) in zip(cycle((self.file_path,)),
                                                          query_set_pairs)]
        return result

    def generate_param_statements(self) -> list[ParamStatement]:
        sy = self.start_year
        ey = self.end_year
        query_param_pairs = (
            (self.M.GlobalDiscountRate, "SELECT rate FROM main.GlobalDiscountRate"),

            (self.M.SegFrac,
             "SELECT season_name, time_of_day_name, segfrac FROM main.SegFrac"),

            # DemandDefaultDistribution?

            (self.M.DemandSpecificDistribution,
             "SELECT regions, season_name, time_of_day_name, demand_name, dds FROM "
             "main.DemandSpecificDistribution"),

            (self.M.Demand,
             f"SELECT regions, periods, demand_comm, demand FROM main.Demand "
             f"WHERE {sy} <= Demand.periods and {ey} >= Demand.periods"),

            # ResourceBound

            (self.M.CapacityToActivity,
             "SELECT regions, tech, c2a FROM main.CapacityToActivity"),

            (self.M.ExistingCapacity,
             f"SELECT regions, tech, vintage, exist_cap  FROM main.ExistingCapacity WHERE vintage <= {ey}"),

            (self.M.Efficiency,
             f"SELECT regions, input_comm, tech, vintage, output_comm, efficiency FROM main.Efficiency WHERE vintage <= {ey}"),

            (self.M.CapacityFactorTech,
             "SELECT regions, season_name, time_of_day_name, tech, cf_tech from main.CapacityFactorTech"),

            # cap factor process
            # lifetime tech
            # lifetime process
            # loan tech / process
            # tech input
            # tech split avg
            # tech output split
            # RPS

            (self.M.CostFixed,
             "SELECT regions, periods, tech, vintage, cost_fixed FROM main.CostFixed "
             f"WHERE vintage <= {ey}"),

            (self.M.CostInvest,
             "SELECT regions, tech, vintage, cost_invest FROM main.CostInvest "
             f"WHERE {sy} <= vintage <= {ey}"),

            (self.M.CostVariable,
             "SELECT regions, periods, tech, vintage, cost_variable FROM main.CostVariable "
             f"WHERE {sy} <= vintage <= {ey}"),

            # Discount Rate
            # ...


        )

        result = [ParamStatement(fp, q, s) for (fp, (q, s)) in zip(cycle((self.file_path,)),
                                query_param_pairs)]

        return result




#filename='PP.sqlite', using='sqlite3', table='PPtable', param=model.p, index=model.A
