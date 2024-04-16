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
import uuid
from collections import defaultdict
from logging import getLogger
from typing import Sequence

from pyomo.core import Expression

from temoa.extensions.modeling_to_generate_alternatives.vector_manager import VectorManager
from temoa.temoa_model.temoa_model import TemoaModel

logger = getLogger(__name__)


class TechActivityVectors(VectorManager):
    default_cat = uuid.uuid4()

    def __init__(self, M: TemoaModel, con: sqlite3.Connection) -> None:
        self.M = M
        self.con = con
        self.basis_coefficient_matrix: list[list]
        self.variable_vector: list | None = None
        self.category_mapping: dict | None = None

    @property
    def groups(self) -> Sequence[str]:
        return self.category_mapping.keys()

    def group_members(self, group) -> list[str]:
        pass

    def basis_vectors(self) -> Expression:
        if not self.basis_coefficient_matrix:
            self._generate_vectors()
        for row in self.basis_coefficient_matrix:
            expr = sum(c * v for c, v in zip(row, self.variable_vector) if c != 0)
            yield expr

    @classmethod
    def _vector_engine(cls, category_mapping: dict) -> list[list]:
        """
        Vector engine to construct a cases x variables coefficient matrix
        :param techs:
        :param cat_tech_tuples:
        :return:
        """
        res = []
        for cat in category_mapping:
            if cat == cls.default_cat:
                pass
            high = cls._row_maker(category_mapping, selected_cat=cat, high=True)
            low = cls._row_maker(category_mapping, selected_cat=cat, high=False)
            res.append(high)
            res.append(low)
        return res

    @staticmethod
    def _row_maker(category_mapping: dict, selected_cat: str, high=True) -> list[float]:
        """
        Make a unit vector based on category and selected technology
        :param cat_sequence: the categories in fixed sequence
        :param selected_cat: the "hot" category
        :return: row vector
        """
        res = []
        for cat in category_mapping:
            if cat == selected_cat:
                res.extend(
                    [(1.0 if high else -1.0) / len(category_mapping[cat])]
                    * len(category_mapping[cat])
                )
            else:
                res.extend([0.0] * len(category_mapping[cat]))
        return res

    def _generate_vectors(self) -> list[list]:
        """Generate the basis vectors based on category from the data and techs included in the model"""

        self.variable_vector = []
        self.basis_coefficient_matrix = []
        techs_implemented = {
            t.name: t for t in self.M.Techs
        }  # some may have been culled by source tracing
        logger.debug('Generating basis vectors')
        raw = self.con.execute('SELECT category, tech from Technology').fetchall()
        self.category_mapping = defaultdict(list)
        for row in raw:
            cat, tech = row
            if cat is None:
                cat = self.default_cat
            if tech in techs_implemented:
                self.category_mapping[cat].append(tech)
                self.variable_vector.append(techs_implemented[tech])

        for cat in self.category_mapping:
            logger.debug('Category %s members: %d', cat, len(self.category_mapping[cat]))

        self.basis_coefficient_matrix = self._vector_engine(self.category_mapping)
        return self.basis_coefficient_matrix  # for testing purposes
