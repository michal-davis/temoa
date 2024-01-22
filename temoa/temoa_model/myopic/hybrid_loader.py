"""
A module to build/load a Data Portal for myopic run using both SQL to pull data
and python to filter results
"""

from logging import getLogger
from sqlite3 import Connection
from typing import Sequence

from pyomo.core import Param, Set
from pyomo.dataportal import DataPortal

from temoa.temoa_model.myopic.myopic_index import MyopicIndex
from temoa.temoa_model.temoa_model import TemoaModel

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
Created on:  1/21/24

"""

logger = getLogger(__name__)


class HybridLoader:
    """
    An instance of the HybridLoader
    """

    def __init__(self, db_connection: Connection):
        self.debugging = True  # for T/S
        self.con = db_connection

        # filters for myopic ops
        self.viable_techs: set[str] = set()
        self.viable_comms: set[str] = set()
        self.viable_vintages: set[int] = set()
        self.viable_rtv: set[tuple[str, str, int]] = set()

    def _refresh_filters(self):
        """
        refresh all the sets used for filtering from the current contents
        of the MyopicEfficiency table.  This should normally be called
        after a Myopic iteration where MyopicEfficiency is updated
        :return:
        """
        cur = self.con.cursor()
        contents = cur.execute(
            'SELECT region, input_comm, tech, vintage, output_comm FROM MyopicEfficiency'
        ).fetchall()
        logger.debug('polled %d elements from MyopicEfficiency table', len(contents))
        self._clear_filters()

        for r, c1, t, v, c2 in contents:
            self.viable_techs.add(t)
            self.viable_comms.add(c1)
            self.viable_comms.add(c2)
            self.viable_vintages.add(v)
            self.viable_rtv.add((r, t, v))

    def _clear_filters(self):
        self.viable_techs.clear()
        self.viable_comms.clear()
        self.viable_rtv.clear()
        self.viable_vintages.clear()

    def load_data_portal(self, myopic_index: MyopicIndex | None = None) -> DataPortal:
        # the general plan:
        # 1. iterate through the model elements that are directly read from data
        # 2. use SQL query to get the full table
        # 3. (OPTIONALLY) filter it, as needed for myopic
        # 4. load it into the data dictionary

        if myopic_index is not None and not isinstance(myopic_index, MyopicIndex):
            raise ValueError(f'received an illegal entry for the myopic index: {myopic_index}')
        else:
            mi = myopic_index  # abbreviated name

        # housekeeping
        self._refresh_filters()

        data: dict[str, list | dict] = dict()

        def load_element(
            c: Set | Param, values: Sequence, validation: set | None = None, rtv_loc: tuple = None
        ):
            """
            Helper to alleviate some typing!
            :param c: the model component
            :param values: the keys for param or the item values for set
            :param validation: the set to validate the keys/set value against
            :param rtv_loc: tuple of the positions of r, t, v in the key for validation
            :return: None
            """
            match c:
                case Set():  # it is a pyomo Set
                    if len(raw) > 0 and len(values[0]) > 1:
                        raise ValueError(
                            'Encountered a multi-dimensional set during data load. '
                            '\nNot currently supported'
                        )
                    if validation and mi:
                        # check for multi-dim sets (none expected)
                        data[c.name] = [t[0] for t in values if t[0] in validation]
                    else:
                        data[c.name] = [t[0] for t in values]
                case Param():  # c is a pyomo Param
                    if validation and mi:
                        if validation is self.viable_rtv:
                            if not rtv_loc:
                                raise ValueError(
                                    'Trying to validate against r, t, v and got no locations'
                                )
                            data[c.name] = {
                                t[:-1]: t[-1]
                                for t in values
                                if (t[rtv_loc[0]], t[rtv_loc[1]], t[rtv_loc[2]]) in self.viable_rtv
                            }
                        else:
                            data[c.name] = {t[:-1]: t[-1] for t in values if t[:-1] in validation}
                    else:
                        data[c.name] = {t[:-1]: t[-1] for t in values}
                case _:
                    raise ValueError(f'Component type unrecognized: {c}, {type(c)}')

        M: TemoaModel = TemoaModel()  # for typing purposes only
        cur = self.con.cursor()

        #### TIME SETS ####

        # time_exist
        if mi:
            raw = cur.execute(
                f'SELECT t_periods from main.time_periods WHERE t_periods < {mi.base_year}'
            ).fetchall()
        else:
            raw = cur.execute(
                f"SELECT t_periods from main.time_periods WHERE flag = 'e'"
            ).fetchall()
        load_element(M.time_exist, raw)

        # time_future
        if mi:
            raw = cur.execute(
                'SELECT t_periods from main.time_periods WHERE '
                f't_periods >= {mi.base_year} AND t_periods <= {mi.last_year}',
            ).fetchall()
        else:
            raw = cur.execute(
                f"SELECT t_periods from main.time_periods WHERE flag = 'f'"
            ).fetchall()
        load_element(M.time_future, raw)

        # time_of_day
        raw = cur.execute('SELECT t_day from main.time_of_day').fetchall()
        load_element(M.time_of_day, raw)

        # time_season
        raw = cur.execute('SELECT t_season from main.time_season').fetchall()
        load_element(M.time_season, raw)

        ### REGIONS AND TECH ###

        # regions
        raw = cur.execute('SELECT regions from main.regions').fetchall()
        load_element(M.regions, raw)

        # tech_resource
        raw = cur.execute("SELECT tech from main.technologies WHERE flag = 'r'").fetchall()
        load_element(M.tech_resource, raw, self.viable_techs)

        # tech_production
        raw = cur.execute("SELECT tech from main.technologies WHERE flag = 'p'").fetchall()
        load_element(M.tech_production, raw, self.viable_techs)

        # tech_baseload
        raw = cur.execute(f"SELECT tech from main.technologies where flag = 'pb'").fetchall()
        load_element(M.tech_baseload, raw, self.viable_techs)

        # tech_storage
        raw = cur.execute(f"SELECT tech from main.technologies where flag = 'ps'").fetchall()
        load_element(M.tech_storage, raw, self.viable_techs)

        # tech_reserve
        raw = cur.execute('SELECT tech from main.tech_reserve').fetchall()
        load_element(M.tech_reserve, raw, self.viable_techs)

        # tech_annual
        raw = cur.execute('SELECT tech from main.tech_annual').fetchall()
        load_element(M.tech_annual, raw, self.viable_techs)

        ### COMMODITIES ###

        # commodity_demand
        raw = cur.execute("SELECT comm_name FROM main.commodities WHERE flag = 'd'").fetchall()
        load_element(M.commodity_demand, raw, self.viable_comms)

        # commodity_emissions
        raw = cur.execute("SELECT comm_name FROM main.commodities WHERE flag = 'e'").fetchall()
        load_element(M.commodity_emissions, raw, self.viable_comms)

        # commodity_physical
        raw = cur.execute("SELECT comm_name FROM main.commodities WHERE flag = 'p'").fetchall()
        load_element(M.commodity_physical, raw, self.viable_comms)

        ### PARAMS ###

        if mi:
            raw = cur.execute(
                'SELECT region, input_comm, tech, vintage, output_comm, efficiency '
                'FROM MyopicEfficiency',
            ).fetchall()
        else:
            raw = cur.execute(
                'SELECT regions, input_comm, tech, vintage, output_comm, efficiency '
                'FROM main.Efficiency',
            ).fetchall()
        load_element(M.Efficiency, raw)

        # ExistingCapacity
        if mi:
            raw = cur.execute(
                'SELECT region, tech, vintage, capacity FROM main.MyopicCapacity '
                'UNION '
                'SELECT regions, tech, vintage, exist_cap FROM main.ExistingCapacity'
            ).fetchall()
        else:
            raw = cur.execute(
                'SELECT regions, tech, vintage, exist_cap FROM main.ExistingCapacity'
            ).fetchall()
        load_element(M.ExistingCapacity, raw)

        # GlobalDiscountRate
        raw = cur.execute('SELECT rate from main.GlobalDiscountRate').fetchall()
        load_element(M.GlobalDiscountRate, raw)

        # SegFrac
        raw = cur.execute(
            'SELECT season_name, time_of_day_name, segfrac FROM main.SegFrac'
        ).fetchall()
        load_element(M.SegFrac, raw)

        # DemandSpecificDistribution
        raw = cur.execute(
            'SELECT regions, season_name, time_of_day_name, demand_name, dds from main.DemandSpecificDistribution'
        ).fetchall()
        load_element(M.DemandSpecificDistribution, raw)

        # Demand
        raw = cur.execute(
            f'SELECT regions, periods, demand_comm, demand FROM main.Demand '
            f'WHERE {mi.base_year} <= Demand.periods AND Demand.periods <= {mi.last_demand_year}'
        ).fetchall()
        load_element(M.Demand, raw)

        # CostFixed
        raw = cur.execute(
            'SELECT regions, periods, tech, vintage, cost_fixed FROM main.CostFixed '
            f'WHERE {mi.base_year} <= CostFixed.periods AND CostFixed.periods <= {mi.last_demand_year}'
        ).fetchall()
        load_element(
            M.CostFixed,
            raw,
            self.viable_rtv,
            rtv_loc=(0, 2, 3)
        )

        # pyomo namespace format has data[namespace][idx]=value
        namespace = {None: data}
        dp = DataPortal(data_dict=namespace)
        return dp
