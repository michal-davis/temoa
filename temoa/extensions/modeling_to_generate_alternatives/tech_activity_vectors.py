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
import sys
from collections import defaultdict
from itertools import chain
from logging import getLogger
from pathlib import Path
from queue import Queue
from typing import Iterable

import numpy as np
from deprecated.classic import deprecated
from matplotlib import pyplot as plt
from pyomo.core import Expression, Var, value, Objective

from definitions import PROJECT_ROOT
from temoa.extensions.modeling_to_generate_alternatives.hull import Hull
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
    def __init__(self, conn: sqlite3.Connection, base_model: TemoaModel, optimal_cost: float, cost_relaxation: float):
        self.conn = conn
        self.base_model = base_model
        self.optimal_cost = optimal_cost
        self.cost_relaxation = cost_relaxation

        self.basis_coefficients: list[dict[tuple, float]] | None = None

        # {category : [technology, ...]}
        # the number of keys in this are the dimension of the hull
        self.category_mapping: dict | None = None

        # {technology: [flow variables, ...]}
        # by unrolling this, we should get the variable vector
        self.variable_mapping: dict[str, list[Var]] = defaultdict(list)
        # in order to peel the data out of a solved model, we also need a rollup of the NAME
        # of the variable and indices in order...
        self.variable_name_mapping: dict[str, list] = defaultdict(list)

        self.vector_queue: Queue[np.ndarray] = Queue()

        self.hull_points: np.ndarray | None = None
        self.hull: Hull | None = None

        self.initialize()

        # monitor/report the size of the hull for each new point.  May cause some slowdown due to
        # hull re-computes, but it seems quite fast RN.
        self.hull_monitor = True
        self.perf_data = {}

    def initialize(self) -> None:
        """
        Fill the internal data stores from db and model
        :return:
        """
        self.basis_coefficients = []
        techs_implemented = self.base_model.tech_all  # some may have been culled by source tracing
        logger.debug('Initializing Technology Vectors data elements')
        raw = self.conn.execute('SELECT category, tech FROM Technology').fetchall()
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

        for idx in self.base_model.activeFlow_rpsditvo:
            tech = idx[5]
            self.variable_mapping[tech].append(self.base_model.V_FlowOut[idx])
            self.variable_name_mapping[self.base_model.V_FlowOut.name].append(idx)
        for idx in self.base_model.activeFlow_rpitvo:
            tech = idx[3]
            self.variable_mapping[tech].append(self.base_model.V_FlowOutAnnual[idx])
            self.variable_name_mapping[self.base_model.V_FlowOutAnnual.name].append(idx)
        logger.debug(
            'Catalogued %d Technology Variables', len(list(chain(*self.variable_mapping.values())))
        )

    def instance_generator(self) -> TemoaModel:
        """
        Generate instances to solve.  Start with the basis vectors, then ...
        :return: a TemoaModel instance
        """
        # traverse the basis vectors first
        yield self.base_model.clone()
        for v in self.basis_vectors():
            new_model = self.__stuff_new_model(v)
            yield new_model

        # if asking for more, we *should* have enough data to create a good hull now...
        if len(self.hull_points) < 1.5 * len(self.category_mapping):
            # we are at risk of not having enough solves to make a hull.  We should have 2x category_mapping
            logger.error('Not enough successful initial solves to make a hull.  Pts: %d, categories: %d', len(self.hull_points), len(self.category_mapping))
            sys.exit(-1)
        logger.info('Generating hull points')
        self.basis_runs_complete()
        v = self._next_input_vector()
        if v is None:
            yield None
        new_model = self.__stuff_new_model(v)
        yield new_model

    def __stuff_new_model(self, vec) -> TemoaModel:
        """make a new model with the objective from the vec"""
        new_model = self.base_model.clone()
        # # remove the old objective...
        # new_model.del_component(new_model.TotalCost)
        # insert the new objective...
        new_model.obj = Objective(expr=vec)
        print('************ obj:')
        new_model.obj.pprint()
        # print('************ cost constraint:')
        # new_model.cost_cap.pprint()
        return new_model
        
    def process_results(self, M: TemoaModel):
        """
        retrieve the necessary variable values to make another hull point
        :param M:
        :return: None
        """
        res = []
        for v_name in self.variable_name_mapping:
            model_var = M.find_component(v_name)   # get the variable by name out of the model
            if not isinstance(model_var, Var):
                raise RuntimeError('Failed to retrieve a named variable from the model: %s', v_name)
            for idx in self.variable_mapping[v_name]:
                res.append(value(model_var[idx]))

        # add it to the points
        hull_point = np.array(res)
        if self.hull_points is None:
            self.hull_points = np.atleast_2d(hull_point)
        else:
            self.hull_points = np.vstack((self.hull_points, hull_point))
        if self.hull_monitor:
            self.tracker()
        return res



    def stop_resolving(self) -> bool:
        pass

    def variable_vector(self) -> list[Var]:
        return list(chain(*self.variable_mapping.values()))

    @property
    def groups(self) -> Iterable[str]:
        return self.category_mapping.keys()

    def group_members(self, group) -> list[str]:
        return self.category_mapping.get(group, [])

    # noinspection PyTypeChecker
    def basis_vectors(self) -> Expression:
        """generator for basis vectors which will be the objective expression in the basis solves"""
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

    def basis_runs_complete(self):
        """make the hull..."""
        logger.debug('Generating the cvx hull from %d points', len(self.hull_points))
        self.hull = Hull(self.hull_points)
        fresh_vecs = self.hull.get_all_norms()
        np.random.shuffle(fresh_vecs)
        print(f'   made {len(fresh_vecs)} fresh vectors')
        print('   huge at: ', self.hull.cv_hull.volume)
        print(f'   rejection frac: {self.hull.norm_rejection_proportion}')
        self.load_normals(fresh_vecs)

    @deprecated('no longer used')
    def notify(self) -> list[float]:
        # when notify is received, use the stored values in the variables to generate the point
        res = []
        for cat in self.category_mapping:
            element = 0
            for tech in self.category_mapping[cat]:
                element += sum(value(variable) for variable in self.variable_mapping[tech])
            res.append(element)
        hull_point = np.array(res)
        if self.hull_points is None:
            self.hull_points = np.atleast_2d(hull_point)
        else:
            self.hull_points = np.vstack((self.hull_points, hull_point))
        if self.hull_monitor:
            self.tracker()
        return res

    def tracker(self):
        if len(self.hull_points) > 10:
            hull = Hull(self.hull_points)
            volume = hull.volume
            logger.info(f'Tracking hull at {volume}')
            self.perf_data.update({len(self.hull_points): volume})

    def finalize_tracker(self):
        fout = Path(PROJECT_ROOT, 'output_files', 'hull_perf.png')
        pts = sorted(self.perf_data.keys())
        y = [self.perf_data[pt] for pt in pts]
        plt.plot(pts, y)
        plt.savefig(str(fout))

    def load_normals(self, normals: np.array):
        for vector in normals:
            self.vector_queue.put(vector)

    def input_vectors_available(self) -> int:
        return self.vector_queue.qsize()

    def _next_input_vector(self) -> Expression | None:
        if self.vector_queue.qsize() <= 3:
            print('running low...refreshing the vectors')
            logger.info('running low...refreshing the vectors')
            self.basis_runs_complete()
        if not self.vector_queue or self.input_vectors_available() == 0:
            return None
        vector = self.vector_queue.get()
        # print(vector)
        # translate the norm vector into coefficients
        coeffs = []
        for idx, cat in enumerate(self.category_mapping):
            for tech in self.category_mapping[cat]:
                for _ in range(len(self.variable_mapping[tech])):
                    coeffs.append(vector[idx])
        coeffs = np.array(coeffs)
        coeffs /= np.sum(coeffs)  # normalize

        all_variables = list(chain(*self.variable_mapping.values()))
        assert len(all_variables) == len(coeffs)
        return sum(c * v for v, c in zip(all_variables, coeffs))

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

    def tech_variables(self, tech) -> list[Var]:
        return self.variable_mapping.get(tech, [])
