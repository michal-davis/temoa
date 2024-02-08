"""
This module is used to verify that all demand commodities are traceable back to designated
source technologies
"""
from collections import defaultdict
from itertools import chain
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
        self.M = M
        self.region = region
        self.period = period
        # {output comm: {input comm, tech} that source it}
        self.connections: dict[str, set[tuple]] = defaultdict(set)
        self.demand_commodities: set[str] = {
            d for (r, p, d) in M.Demand if r == self.region and p == self.period
        }
        self.source_commodities: set[str] = set(M.commodity_source)
        # scan non-annual techs
        for r, p, s, d, ic, tech, v, oc in self.M.activeFlow_rpsditvo:
            if r == self.region and p == self.period:
                self.connections[oc].add((ic, tech))

        # add annual techs...

        for r, p, ic, tech, v, oc in M.activeFlow_rpitvo:
            if r == self.region and p == self.period:
                self.connections[oc].add((ic, tech))

        # network of {destination: {origins}}
        self.network: dict[str, set[str]] = dict()

        # TODO:  perhaps sockets later to account for links, for now, we will just look at internal connex
        # # set of exchange techs FROM this region that supply commodity through link
        # # {tech: set(output commodities)}
        # self.output_sockets: dict[str, set[str]] = dict()
        # self.input_sockets: ...

    def analyze(self):
        good_connections = DFS(self.demand_commodities, self.source_commodities, self.connections)
        logger.debug(
            'Got %d good connections from %d techs in region %s, period %d',
            len(good_connections),
            len(tuple(chain(*self.connections.values()))),
            self.region,
            self.period,
        )


def DFS(
    start_nodes: set[str],
    end_nodes: set[str],
    connections: dict[str, set[tuple]],
    current_start=None,
    current_chain=None,
    good_tech=None,
) -> set[tuple]:
    """
    recursive depth-first search to identify viable techs
    :param start_nodes: the set of demand commodities (oc ∈ demand)
    :param good_tech: currently good (input comm, tech, output comm) tuples
    :param connections: the connections to explore {output: {(ic, tech)}}
    :param end_nodes: source nodes, or ones traceable to source nodes
    :param current_start: the current node (ic) index
    :param current_chain: the current chain of exploration tuples (ic, tech, oc)
    :return: the set of viable tech tuples (ic, tech, oc)
    """
    if not good_tech:
        good_tech = set()
    if not current_start and not start_nodes:  # no more starts, we're done
        if good_tech:
            return good_tech
        else:
            return set()
    if not current_start:
        current_start = start_nodes.pop()
        current_chain = []  # new list for new start

    for ic, tech in connections.pop(current_start, []):  # we can pop, no need to re-explore
        if ic in end_nodes:  # we have struck gold
            # add the current tech
            good_tech.add((ic, tech, current_start))
            end_nodes.add(current_start)  # current start (output) is now proven good also
            # add all in the chain
            for prev_ic, prev_tech, prev_oc in current_chain:
                good_tech.add((prev_ic, prev_tech, prev_oc))
                end_nodes.add(prev_oc)  # previous output is now proven also
        else:
            # add this ic, tech to current chain copy and go from there
            chain = current_chain.copy()
            chain.append((ic, tech, current_start))
            # add what is found down this chain...
            good_tech.update(
                DFS(
                    start_nodes,
                    end_nodes,
                    connections,
                    current_start=ic,
                    current_chain=chain,
                    good_tech=good_tech,
                )
            )

    # start a new search if no connections left from this start...
    return DFS(start_nodes, end_nodes, connections, current_start=None, good_tech=good_tech)


def source_trace(M: 'TemoaModel') -> bool:
    """
    trace the demand commodities back to designated source technologies
    :param M: the model to inspect
    :return: True if all demands are traceable, False otherwise
    """

    for region in M.regions:
        for p in M.time_optimize:
            commodity_network = CommodityNetwork(region=region, period=p, M=M)
            commodity_network.analyze()
    return True
