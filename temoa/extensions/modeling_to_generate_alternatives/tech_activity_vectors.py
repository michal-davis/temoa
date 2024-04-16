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
Created on:  4/16/24

"""
import sqlite3
from collections import defaultdict
from itertools import chain
from logging import getLogger
from typing import Iterable

from pyomo.core import Expression, Var

from temoa.extensions.modeling_to_generate_alternatives.vector_manager import VectorManager
from temoa.temoa_model.temoa_model import TemoaModel

logger = getLogger(__name__)


class DefaultItem:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


default_cat = DefaultItem('DEFAULT')


class TechActivityVectors(VectorManager):
    def __init__(self, M: TemoaModel, con: sqlite3.Connection) -> None:
        self.M = M
        self.con = con
        self.basis_coefficients: list[dict[tuple, float]] | None = None

        # {category : [technology, ...]}
        self.category_mapping: dict | None = None

        # {technology: [flow variables, ...]}
        self.variable_mapping: dict[str, list[Var]] | None = None
        self.initialize()

    def initialize(self) -> None:
        """
        Fill the internal data stores from db and model
        :return:
        """
        self.basis_coefficients = []
        techs_implemented = self.M.tech_all  # some may have been culled by source tracing
        logger.debug('Initializing Technology Vectors data elements')
        raw = self.con.execute('SELECT category, tech FROM Technology').fetchall()
        self.category_mapping = defaultdict(list)
        for row in raw:
            cat, tech = row
            if cat in {None, ''}:
                cat = default_cat
            if tech in techs_implemented:
                self.category_mapping[cat].append(tech)

        for cat in self.category_mapping:
            logger.debug('Category %s members: %d', cat, len(self.category_mapping[cat]))

        # now pull the flow variables and map them
        self.variable_mapping = defaultdict(list)
        for idx in self.M.activeFlow_rpsditvo:
            tech = idx[5]
            self.variable_mapping[tech].append(self.M.V_FlowOut[idx])
        for idx in self.M.activeFlow_rpitvo:
            tech = idx[3]
            self.variable_mapping[tech].append(self.M.V_FlowOutAnnual[idx])
        logger.debug(
            'Catalogued %d Technology Variables', len(list(chain(*self.variable_mapping.values())))
        )

    def tech_variables(self, tech) -> list[Var]:
        return self.variable_mapping.get(tech, [])

    @property
    def groups(self) -> Iterable[str]:
        return self.category_mapping.keys()

    def group_members(self, group) -> list[str]:
        return self.category_mapping.get(group, [])

    # noinspection PyTypeChecker
    def basis_vectors(self) -> Expression:
        if not self.basis_coefficients:
            self.basis_coefficients = self._generate_basis(
                category_mapping=self.category_mapping, variable_mapping=self.variable_mapping
            )
        for row in self.basis_coefficients:
            row_sum = sum(c for _, c in row)
            # verify a unit vector
            assert abs(abs(row_sum) - 1) < 1e-5
            expr = sum(c * v for v, c in row)
            yield expr

    @classmethod
    def _generate_basis(
        cls, category_mapping: dict, variable_mapping: dict
    ) -> list[list[tuple[Var, float]]]:
        """
        Vector engine to construct a cases x variables coefficient matrix
        :return:
        """
        res = []
        for cat in category_mapping:
            if cat == default_cat:
                pass
            techs = category_mapping[cat]
            associated_indices = []
            for tech in techs:
                associated_indices.extend(variable_mapping[tech])
            tot_entries = len(associated_indices)
            # high
            entry = [(v, 1.0 / tot_entries) for v in associated_indices]
            res.append(entry)
            # low
            entry = [(v, -1.0 / tot_entries) for v in associated_indices]
            res.append(entry)
        return res
