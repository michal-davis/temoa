"""
These "validators" are used as validation tools for several elements in the TemoaModel
"""
import re
from collections import defaultdict
from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from temoa.temoa_model.temoa_model import TemoaModel

# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  9/27/23

logger = getLogger(__name__)


def validate_linked_tech(M: "TemoaModel") -> bool:
    """
    A validation that for all the linked techs, they have the same lifetime in each possible vintage
    :param M:
    :return:
    """
    logger.debug('Starting to validate linked techs.')
    # gather the tech-linked_tech pairs
    tech_pairs = {
        (k[0], k[1], v) for (k, v) in M.LinkedTechs.items()
    }  # (r, t, linked_tech) tuples

    # get the lifetimes by (r, t) and v for comparison
    lifetimes: dict[tuple, dict] = defaultdict(dict)
    for (r, t, v) in M.LifetimeProcess_final:
        lifetimes[r, t][v] = M.LifetimeProcess_final[r, t, v]
    {
        (r, t): {v: M.LifetimeProcess_final[r, t, v]}
        for (r, t, v) in M.LifetimeProcess_final
    }
    # compare the dictionary of v: lifetime for each pair
    success = all(
        (
            lifetimes[r, t] == lifetimes[r, linked_tech]
            for (r, t, linked_tech) in tech_pairs
        )
    )

    if success:
        logger.debug(
            "Successfully screened all linked techs for lifetime compatibility."
        )
        return True
    else:  # log the problems...
        for r, t, linked_tech in tech_pairs:
            # compare vintages (should be same)
            tech_vintages = lifetimes.get((r, t))
            # make sure they have vintages in LifetimeProcess
            if not tech_vintages:
                logger.error(
                    "Tech %s in region %s has no valid vintages in LifetimeProcess",
                    t,
                    r,
                )
            linked_tech_vintages = lifetimes.get((r, linked_tech))
            if not linked_tech_vintages:
                logger.error(
                    "Linked tech %s in region %s has no valid vintages in LifetimeProcess",
                    t,
                    r,
                )

            # make sure they have the SAME eligible vintages
            if tech_vintages and linked_tech_vintages:
                vintage_disparities = (
                    lifetimes[r, t].keys() ^ lifetimes[r, linked_tech].keys()
                )
                if vintage_disparities:
                    logger.error(
                        "Tech %s and %s are linked but have differing vintages in Lifetime process in vintages:\n  %s",
                        t,
                        linked_tech,
                        vintage_disparities,
                    )

                # check for same lifetimes, using the base tech as a baseline
                vintage_lifetimes = lifetimes[r, t]
                for v in vintage_lifetimes.keys():
                    # get the corresponding lifetime for the linked tech
                    linked_vintage_lifetime = lifetimes.get((r, linked_tech)).get(v)
                    if vintage_lifetimes[v] != linked_vintage_lifetime:
                        logger.error(
                            "Techs %s and %s do not have the same lifetime in vintage %s",
                            t,
                            linked_tech,
                            v,
                        )
        logger.error('Temoa Exiting...')
        return False

def region_check(M: 'TemoaModel', region):
    """
    Validate the region name (letters + numbers only + underscore)
    """
    # screen against illegal names
    illegal_region_names = {'global', }
    if region in illegal_region_names:
        return False

    # if this matches, return is true, fail -> false
    return re.match(r'[a-zA-Z0-9_]+\Z', region)  # string that has only letters and numbers

def linked_region_check(M: 'TemoaModel', region_pair):
    """
    Validate a pair of regions (r-r format where r ∈ M.R )
    """
    linked_regions = re.match(r'([a-zA-Z0-9_]+)\-([a-zA-Z0-9_]+)\Z', region_pair)
    if linked_regions:
        r1 = linked_regions.group(1)
        r2 = linked_regions.group(2)
        if all(r in M.R for r in (r1, r2)) and r1 != r2:  # both captured regions are in the set of M.R
            return True
    return False

def region_group_check(M: 'TemoaModel', rg):
    """
    Validate the region-group name (region or regions separated by '+')
    """
    if re.search(r'\A[a-zA-Z0-9\+_]+\Z', rg):
        # it has legal characters only
        if '+' in rg:
            # break up the group
            contained_regions = rg.strip().split('+')
            if all(t in M.R for t in contained_regions) and \
                len(set(contained_regions)) == len(contained_regions):  # no dupes
                return True
        else:  # it is a singleton
            return (rg in M.R) or rg == 'global'
    return False

def tech_groups_set_check(M: 'TemoaModel', rg, g, t):
    """
    Validate this entry to the tech_groups set
    :param M: the model
    :param rg: region-group index
    :param g: tech group name
    :param t: tech
    :return: True if valid entry, else False
    """
    return all((
        region_group_check(M, rg),
        g in M.groups,
        t in M.tech_all
    ))