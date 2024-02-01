"""
a build check item to test for anomalies in pricing.

Intent is to identify several possible errors.  Note:  These will need to be enhanced as this
will likely generate many false positives initially.

1.  Technologies that have an entry in Efficiency table that have no corresponding
    (or inconsistent) fixed-cost / inv cost pairs.  The primary motivation is that
    things without either an FC or IC have no downward pressure on activity in the model,
    which is regulated by cost

2.  Technologies that have fixed or variable costs that are inconsistent
    (entry for specific period in one, but not other)

3.  Technologies that any entry for a fixed or variable cost,
    but do not extend through all years in the tech_lifetime

Written by:  J. F. Hyink
jeff@westernspark.us
https://westernspark.us
Created on:  11/5/23

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

from collections import defaultdict

from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from temoa.temoa_model.temoa_model import TemoaModel

logger = getLogger(__name__)


def price_checker(M: 'TemoaModel'):
    logger.info('Started price checking model: %s', M.name)
    # some sets for x-checking
    registered_inv_costs = {(region, tech, vintage) for (region, tech, vintage) in M.CostInvest.sparse_iterkeys()}
    efficiency_rtv = {(region, tech, vintage) for (region, _, tech, vintage, __) in M.Efficiency.sparse_iterkeys()}
    sorted_efficiency_rtv = sorted(efficiency_rtv, key=lambda rtv: (rtv[1], rtv[0], rtv[2]))

    # make convenience dicts to avoid repeated filtering
    # the set of all periods that have a fixed cost for this (r, t, v)
    fixed_costs = defaultdict(set)
    # the set of all periods that have a var cost for this (r, t, v)
    var_costs = defaultdict(set)
    # fixed costs for the period = vintage year
    base_year_fixed_cost_rtv = set()
    # var costs for the period = vintage year
    base_year_variable_cost_rtv = set()

    for r, p, t, v in M.CostFixed:
        fixed_costs[r, t, v].add(p)
        if p == v:
            base_year_fixed_cost_rtv.add((r, t, v))
    for r, p, t, v in M.CostVariable:
        var_costs[r, t, v].add(p)
        if p == v:
            base_year_variable_cost_rtv.add((r, t, v))
    logger.debug('  Finished making costing data structures for price checker')

    # Check 0:  Look for techs that have NO fixed/invest/var cost at all
    logger.debug('  Starting price check #0:  No costs at all. :(')
    no_invest = efficiency_rtv - registered_inv_costs
    no_fixed_costs = no_invest - fixed_costs.keys()
    no_var_costs = no_fixed_costs - var_costs.keys()
    for r, t, v in no_var_costs:
        logger.error('No costs at all for: %s', (r, t, v))

    # Check 1 looks for missing (1a) and inconsistent (1b) fixed cost - investment cost pairings
    logger.debug('  Starting price check #1a')
    # Check 1a:  Look for "missing" FC/IC (no fixed or investment cost) based on what is in the
    #            Efficiency set
    techs_without_fc_or_ic = set()
    # pull the details...
    chk_1_errors = []
    for region, tech, vintage in sorted_efficiency_rtv:
        # disregard "resource" technologies
        if tech in M.tech_resource:
            continue
        # disregard vintages that are not in the optimization period (they are never accessed in
        # model)
        if vintage not in M.time_optimize:
            continue

        has_fc = (region, tech, vintage) in fixed_costs
        has_vc = (region, tech, vintage) in var_costs
        has_ic = (region, tech, vintage) in registered_inv_costs

        if not any((has_fc, has_ic)):
            logger.warning(
                f'Check 1a (detail): tech {tech} of vintage {vintage} in region {region} does not '
                f'have a Fixed Cost or Investment Cost component'
            )
            techs_without_fc_or_ic.add(tech)

    # test 1b:  find items that have inconsistent FC/IC across regions & vintages in the base
    #           (vintage) year only
    logger.debug('  Starting price check #1b')
    # set of {r, t, v} with no base-year FC entry anywhere
    missing_fc = efficiency_rtv - base_year_fixed_cost_rtv
    # if there are missing FC, scan filter to find other regions and vintages of same tech for
    # comparison
    if missing_fc:
        missing_techs = defaultdict(set)
        for r, t, v in missing_fc:
            if v in M.time_optimize:
                missing_techs[t].add((r, v))
        for t in missing_techs:
            # get set of fixed cost for all {rtv} if the tech matches
            compaprable_fc = sorted(filter(lambda x: x[1] == t, base_year_fixed_cost_rtv))
            err = None
            if compaprable_fc:
                err = (
                    f'Check 1b:\ntech {t} has Fixed Cost in some vintage/regions for '
                    f'the base (vintage) year, but not all:\n'
                )
                err += '    missing (r, v):\n'
                for r, v in sorted(missing_techs.get(t)):
                    err += f'      ({r}, {v})\n'
                err += '    available (r, v):\n'
                for r, tt, v in compaprable_fc:
                    err += f'       ({r}, {v}): {M.CostFixed[r, v, tt, v]}\n'
            if err:
                logger.warning(err)

    # inconsistent IC
    missing_ic = efficiency_rtv - registered_inv_costs  # set of {r, t, v} with no FC entry anywhere
    # if there are missing FC, scan filter to find other regions and vintages of same tech for
    # comparison
    if missing_ic:
        missing_techs = defaultdict(set)
        for r, t, v in missing_ic:
            if v in M.time_optimize:
                missing_techs[t].add((r, v))
        for t in missing_techs:
            compaprable_ic = sorted(filter(lambda x: x[1] == t, registered_inv_costs))
            err = None
            if compaprable_ic:
                err = (
                    f'check 1b:\ntech {t} has Investment Cost in some vintage/regions but not all\n'
                )
                err += '    missing (r, v):\n'
                for r, v in sorted(missing_techs.get(t)):
                    err += f'      ({r}, {v})\n'
                err += '    available (r, v):\n'
                for r, tt, v in compaprable_ic:
                    err += f'       ({r}, {v}): {M.CostInvest[r, tt, v]}\n'
            if err:
                logger.warning(err)

    # Check 2:  inconsistent fixed/var costs.  Only check for techs that have ANY
    #           fixed cost that do not have ALL fixed costs that match ALL variable
    #           costs and vice-versa.  Else, we are going to get false positives
    #           on things that have NO fixed (or variable) costs at all.
    #           Note this checks all Periods, not just base year as previous check did.
    logger.debug('  Starting price check #2')
    for region, tech, vintage in sorted_efficiency_rtv:
        # take the differenece in the sets of periods...
        missing_fixed_costs = (
            var_costs[region, tech, vintage] - fixed_costs[region, tech, vintage]
            if fixed_costs[region, tech, vintage]
            else None
        )
        if missing_fixed_costs:
            logger.warning(
                'Check 2: The following have registered variable costs in '
                'the periods listed, but no fixed costs in the same periods: %s',
                missing_fixed_costs,
            )

        missing_var_costs = (
            fixed_costs[region, tech, vintage] - var_costs[region, tech, vintage]
            if var_costs[region, tech, vintage]
            else None
        )
        if missing_var_costs:
            logger.warning(
                'Check 2: The following have registered fixed costs in the '
                'periods listed, but no variable costs in the same periods: %s',
                missing_var_costs,
            )

    # Check 3:  costs that fall short of tech lifetime.  Only check costs that
    #           have ANY valid entry in the period, ones with NO entry in the
    #           period are assumed to be intentionally omitted and may be caught by
    #           test 1 above.

    logger.debug('  Starting price check #3')
    for region, tech, vintage in sorted_efficiency_rtv:
        # skip resources
        if tech in M.tech_resource:
            continue

        # get the lifetime of the tech, or default
        lifetime = M.LifetimeProcess[region, tech, vintage]
        # get all applicable future periods that should be priced for this item
        expected_periods = {p for p in M.time_optimize if vintage <= p < vintage + lifetime}
        missing_fixed_costs = (
            expected_periods - fixed_costs[region, tech, vintage]
            if fixed_costs[region, tech, vintage]
            else None
        )
        missing_var_costs = (
            expected_periods - var_costs[region, tech, vintage]
            if var_costs[region, tech, vintage]
            else None
        )

        if missing_fixed_costs:
            logger.warning(
                'check 3: Technology %s of vintage %s in region %s fixed costs are missing '
                'periods %s relative to lifetime expiration in %d',
                tech,
                vintage,
                region,
                sorted(missing_fixed_costs),
                vintage + lifetime,
            )
        if missing_var_costs:
            logger.warning(
                'check 3: Technology %s of vintage %s in region %s variable costs are'
                ' missing periods %s relative to lifetime expiration in %d',
                tech,
                vintage,
                region,
                sorted(missing_var_costs),
                vintage + lifetime,
            )

    logger.info('Finished Price Checking Build Action')
