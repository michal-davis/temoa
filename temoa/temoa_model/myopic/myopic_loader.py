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

    def __init__(self, file_path: Path, M: TemoaModel, start_year=-1, end_year=1000000):
        self.start_year = start_year
        self.end_year = end_year
        self.file_path: str = str(file_path)  # pyomo wants string name for loading portal
        self.M = M

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

    def generate_set_statements(self) -> list[SetStatement]:
        result: list[SetStatement] = []
        query_set_pairs = (
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

            # Dev Note:  using .format() here instead of f-string appears to preserve linkage of
            # field names to schema for auto-complete and visibility during refactor
            (self.M.Demand,
             "SELECT regions, periods, demand_comm, demand FROM main.Demand "
             "WHERE %d <= Demand.periods and %d >= Demand.periods".format(sy, ey)),

            # ResourceBound

            (self.M.CapacityToActivity,
             "SELECT regions, tech, c2a FROM main.CapacityToActivity"),

            (self.M.ExistingCapacity,
             "SELECT regions, tech, vintage, exist_cap  FROM main.ExistingCapacity WHERE vintage <= {}".format(ey)),

            (self.M.Efficiency,
             "SELECT regions, input_comm, tech, vintage, output_comm, efficiency FROM main.Efficiency WHERE vintage <= {}".format(ey)),

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
             "WHERE vintage <= %d".format(ey)),

            (self.M.CostInvest,
             "SELECT regions, tech, vintage, cost_invest FROM main.CostInvest "
             "WHERE %d <= vintage <= %d".format(sy, ey)),

            (self.M.CostVariable,
             "SELECT regions, periods, tech, vintage FROM main.CostVariable")
        )

        result = [ParamStatement(fp, q, s) for (fp, (q, s)) in zip(cycle((self.file_path,)),
                                query_param_pairs)]

        return result


bob = "SELECT regions, periods, tech, vintage FROM main.CostVariable WHERE vintage <= {}"



#filename='PP.sqlite', using='sqlite3', table='PPtable', param=model.p, index=model.A
