"""
This module is used to verify that all demand commodities are traceable back to designated
source technologies
"""
from logging import getLogger

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
Created on:  2/3/24

"""

logger = getLogger(__name__)


class CommodityNetwork:
    """
    class to hold the network for a particular region/period
    """

    def __init__(self, region, period: int, M: TemoaModel):
        self.region = region
        self.period = period
        self.demand_commodities: set[str] = {
            o
            for r, p, i, t, v, o in M.activeFlow_rpitvo
            if o in M.demand_commodities and r == self.region and p == self.period
        }
        self.source_commodities: set[str] = {
            i
            for r, p, i, t, v, o in M.activeFlow_rpitvo
            if i in M.source_commodities and r == self.region and p == self.period
        }
        self.known_good_commodities: set[str] = set()
        self.network: dict[str, set[str]] = dict()
        # set of exchange techs FROM this region that supply commodity through link
        # {tech: set(output commodities)}
        self.sockets: dict[str, set[str]] = dict()

        for flow in M.activeFlow_rpitvo:
            r, p, i, t, v, o = flow


def source_trace(M: 'TemoaModel') -> bool:
    """
    trace the demand commodities back to designated source technologies
    :param M: the model to inspect
    :return: True if all demands are traceable, False otherwise
    """
    # dev note:  Currently, all demand commodities must be used [see temoa_initialize]
    #            so we don't need to worry about tracing unused stuff
    demand_commodities = set(M.demand_commodities)
    source_commodities = set(M.source_commodities)
    # the set of "known good" intermediate commodities
    traceable_commodities = set()

    # Intent is to do a DFS (depth-first-search) on all demands down to either
    # (a) a source commodity
    # (b) a known good commodity
    # If we 'strike gold', mark all currently chained commodities as traceable good

    return True
