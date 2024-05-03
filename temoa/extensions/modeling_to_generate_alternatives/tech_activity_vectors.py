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
import queue
import sqlite3
from collections import defaultdict
from logging import getLogger
from pathlib import Path
from queue import Queue
from typing import Iterable

import numpy as np
from matplotlib import pyplot as plt
from pyomo.core import Expression, Var, value, Objective, Constraint
from pyomo.dataportal import DataPortal

from definitions import PROJECT_ROOT
from temoa.extensions.modeling_to_generate_alternatives.hull import Hull
from temoa.extensions.modeling_to_generate_alternatives.vector_manager import VectorManager
from temoa.temoa_model.hybrid_loader import HybridLoader
from temoa.temoa_model.run_actions import build_instance
from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_rules import TotalCost_rule

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
    def __init__(
        self,
        conn: sqlite3.Connection,
        base_model: TemoaModel,
        optimal_cost: float,
        cost_relaxation: float,
    ):
        self.conn = conn
        self.base_model = base_model
        self.optimal_cost = optimal_cost
        self.cost_relaxation = cost_relaxation

        # {category : [technology, ...]}
        # the number of keys in this are the dimension of the hull
        self.category_mapping: dict | None = None

        # {technology: [number of associated variables, ...]}
        self.technology_size: dict[str, int] = defaultdict(int)
        # in order to peel the data out of a solved model, we also need a rollup of the NAME
        # of the variable and indices in order...
        # {tech : {var_name : [indices, ...]}, ...}
        self.variable_index_mapping: dict[str, dict[str, list]] = {}

        self.coefficient_vector_queue: Queue[np.ndarray] = Queue()

        self.hull_points: np.ndarray | None = None
        self.hull: Hull | None = None

        self.initialize()
        self.basis_coefficients: Queue[np.ndarray] = self._generate_basis_coefficients()

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
                self.variable_index_mapping[tech] = defaultdict(list)

        for cat in self.category_mapping:
            logger.debug('Category %s members: %d', cat, len(self.category_mapping[cat]))

        # now pull the flow variables and map them

        for idx in self.base_model.activeFlow_rpsditvo:
            tech = idx[5]
            self.technology_size[tech] += 1
            self.variable_index_mapping[tech][self.base_model.V_FlowOut.name].append(idx)
        for idx in self.base_model.activeFlow_rpitvo:
            tech = idx[3]
            self.technology_size[tech] += 1
            self.variable_index_mapping[tech][self.base_model.V_FlowOutAnnual.name].append(idx)
        logger.debug('Catalogued %d Technology Variables', sum(self.technology_size.values()))

    def instance_generator(self, config) -> TemoaModel:
        """
        Generate instances to solve.  Start with the basis vectors, then ...
        :return: a TemoaModel instance
        """
        # traverse the basis vectors first
        new_model = self.base_model.clone()
        obj_vector = self.basis_vector(new_model)
        while obj_vector is not None:
            new_model.obj = Objective(expr=obj_vector)
            yield new_model
            new_model = self.base_model.clone()
            obj_vector = self.basis_vector(new_model)

        # if asking for more, we *should* have enough data to create a good hull now...
        if len(self.hull_points) < 1.5 * len(self.category_mapping):
            # we are at risk of not having enough solves to make a hull.  We should have 2x category_mapping
            logger.error(
                'Not enough successful initial solves to make a hull.  Pts: %d, categories: %d',
                len(self.hull_points),
                len(self.category_mapping),
            )

        logger.info('Generating hull points')
        self.basis_runs_complete()
        while True:
            new_model = self.base_model.clone()
            v = self._next_input_vector(M=new_model)
            if v is None:
                yield None
            new_model.obj = Objective(expr=v)
            yield new_model

    def __stuff_new_model(self, vec, config) -> TemoaModel:
        """make a new model with the objective from the vec"""
        new_model = self.base_model.clone()
        # # remove the old objective...
        # new_model.del_component(new_model.TotalCost)
        # insert the new objective...
        new_model.obj = Objective(expr=vec)
        print('************ obj:')
        # new_model.obj.pprint()
        # print('************ cost constraint:')
        # new_model.cost_cap.pprint()

        # 1. Load data
        hybrid_loader = HybridLoader(db_connection=self.conn, config=config)
        data_portal: DataPortal = hybrid_loader.load_data_portal(myopic_index=None)
        instance: TemoaModel = build_instance(
            loaded_portal=data_portal, model_name=config.scenario, silent=config.silent
        )
        tot_cost = self.optimal_cost

        cost_expression = TotalCost_rule(instance)
        instance.cost_cap = Constraint(
            expr=cost_expression <= (1 + self.cost_relaxation) * tot_cost
        )
        instance.del_component(instance.TotalCost)

        instance.obj = Objective(expr=vec)
        instance.obj.pprint()
        # instance.cost_cap.pprint()
        return instance

    def process_results(self, M: TemoaModel):
        """
        retrieve the necessary variable values to make another hull point
        :param M:
        :return: None
        """
        res = []
        for cat in self.category_mapping:
            element = 0
            for tech in self.category_mapping[cat]:
                for var_name in self.variable_index_mapping[tech]:
                    model_var = M.find_component(var_name)
                    if not isinstance(model_var, Var):
                        raise RuntimeError('hooked a bad fish')
                    element += sum(
                        value(model_var[idx]) for idx in self.variable_index_mapping[tech][var_name]
                    )
            res.append(element)

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

    @property
    def groups(self) -> Iterable[str]:
        return self.category_mapping.keys()

    def group_members(self, group) -> list[str]:
        return self.category_mapping.get(group, [])

    # noinspection PyTypeChecker
    def basis_vector(self, M: TemoaModel) -> Iterable[Expression] | None:
        """generator for basis vectors which will be the coefficients in the obj expression in the basis solves"""
        if self.basis_coefficients.empty():
            return None
        try:
            coeffs = self.basis_coefficients.get()
        except queue.Empty:
            return None

        # now we need to roll out a vector of the variables and pair them with coefficients...
        vars = self.var_vector(M)

        # verify a unit vector
        err = abs(abs(sum(coeffs)) - 1)
        print(f'unit vector size error: {err}')
        assert err < 1e-4
        expr = sum(c * v for v, c in zip(vars, coeffs) if c != 0)
        return expr

    def var_vector(self, M: TemoaModel) -> list[Var]:
        """Produce a properly sequenced array of variables from the current model for use in obj vector"""
        res = []
        for cat in self.category_mapping:
            for tech in self.category_mapping[cat]:
                for var_name in self.variable_index_mapping[tech]:
                    var = M.find_component(var_name)
                    if not isinstance(var, Var):
                        raise RuntimeError(
                            'Failed to retrieve a named variable from the model: %s', var_name
                        )
                    for idx in self.variable_index_mapping[tech][var_name]:
                        res.append(var[idx])
        return res

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

    def load_normals(self, normals: np.array):
        for vector in normals:
            self.coefficient_vector_queue.put(vector)

    def input_vectors_available(self) -> int:
        return self.coefficient_vector_queue.qsize()

    def _next_input_vector(self, M: TemoaModel) -> Expression | None:
        if self.coefficient_vector_queue.qsize() <= 3:
            print('running low...refreshing the vectors')
            logger.info('running low...refreshing the vectors')
            self.basis_runs_complete()
        if not self.coefficient_vector_queue or self.input_vectors_available() == 0:
            return None
        vector = self.coefficient_vector_queue.get()
        # print(vector)
        # translate the norm vector into coefficients
        coeffs = []
        for idx, cat in enumerate(self.category_mapping):
            for tech in self.category_mapping[cat]:
                reps = self.technology_size[tech]
                element = [
                    vector[idx],
                ] * reps
                coeffs.extend(element)
        coeffs = np.array(coeffs)
        coeffs /= np.sum(coeffs)  # normalize

        obj_vars = self.var_vector(M)

        assert len(obj_vars) == len(coeffs)
        return sum(c * v for v, c in zip(obj_vars, coeffs))

    def tech_variables(self, tech) -> list[Var]:
        return self.technology_size.get(tech, [])

    def _generate_basis_coefficients(self) -> Queue:
        # Sequentially build the coefficient vector in the order of the categories and associated techs

        q = Queue()
        for selected_cat in self.category_mapping:
            res = []
            if selected_cat == default_cat:
                continue
            for cat in self.category_mapping:
                num_marks = sum(self.technology_size[tech] for tech in self.category_mapping[cat])
                if cat == selected_cat:
                    marks = [
                        1,
                    ] * num_marks
                else:
                    marks = [
                        0,
                    ] * num_marks
                res.extend(marks)

            entry = np.array(res)
            entry = entry / np.array(np.sum(entry))
            q.put(entry)  # high value
            q.put(-entry)  # low value

        return q

    def tracker(self):
        if len(self.hull_points) > 10:
            hull = Hull(self.hull_points)
            volume = hull.volume
            logger.info(f'Tracking hull at {volume}')
            print(f'Tracking hull at {volume}')
            self.perf_data.update({len(self.hull_points): volume})

    def finalize_tracker(self):
        fout = Path(PROJECT_ROOT, 'output_files', 'hull_perf.png')
        pts = sorted(self.perf_data.keys())
        y = [self.perf_data[pt] for pt in pts]
        plt.plot(pts, y)
        plt.savefig(str(fout))
