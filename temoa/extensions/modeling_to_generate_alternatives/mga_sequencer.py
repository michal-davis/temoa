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
Created on:  4/15/24

The purpose of this module is to perform top-level control over an MGA model run
"""
import sqlite3
import sys
from datetime import datetime
from logging import getLogger

import numpy as np
import pyomo.contrib.appsi as pyomo_appsi
import pyomo.environ as pyo
from pyomo.contrib.appsi.base import Results
from pyomo.dataportal import DataPortal
from scipy.spatial import ConvexHull

from temoa.extensions.modeling_to_generate_alternatives.hull import Hull
from temoa.extensions.modeling_to_generate_alternatives.manager_factory import get_manager
from temoa.extensions.modeling_to_generate_alternatives.mga_constants import MgaAxis, MgaWeighting
from temoa.extensions.modeling_to_generate_alternatives.vector_manager import VectorManager
from temoa.temoa_model.hybrid_loader import HybridLoader
from temoa.temoa_model.run_actions import build_instance
from temoa.temoa_model.temoa_config import TemoaConfig
from temoa.temoa_model.temoa_model import TemoaModel
from temoa.temoa_model.temoa_rules import TotalCost_rule

logger = getLogger(__name__)


class MgaSequencer:
    def __init__(self, config: TemoaConfig):
        # PRELIMINARIES...
        # let's start with the assumption that input db = output db...  this may change?
        if not config.input_database == config.output_database:
            raise NotImplementedError('MGA assumes input and output databases are same')
        self.con = sqlite3.connect(config.input_database)

        if not config.source_trace:
            logger.warning(
                'Performing MGA runs without source trace.  '
                'Recommend selecting source trace in config file.'
            )
        if config.save_lp_file:
            logger.info('Saving LP file is disabled during MGA runs.')
            config.save_lp_file = False
        if config.save_duals:
            logger.info('Saving duals is disabled during MGA runs.')
            config.save_duals = False
        if config.save_excel:
            logger.info('Saving excel is disabled during MGA runs.')
            config.save_excel = False
        self.config = config
        # TODO:  Check that solver is a persistent solver
        if self.config.solver_name == 'appsi_highs':
            self.solver = pyomo_appsi.solvers.highs.Highs()
        else:
            pass

        # some defaults, etc.
        self.mga_axis = config.mga_inputs.get('axis')
        if not self.mga_axis:
            logger.warning('No MGA Axis specified.  Using default:  Activity by Tech Category')
            self.mga_axis = MgaAxis.TECH_CATEGORY_ACTIVITY
        self.mga_weighting = config.mga_inputs.get('weighting')
        if not self.mga_weighting:
            logger.warning('No MGA Weighting specified.  Using default: Hull Expansion')
            self.mga_weighting = MgaWeighting.HULL_EXPANSION
        self.iteration_limit = config.mga_inputs.get('iteration_limit', 100)
        self.time_limit_hrs = config.mga_inputs.get('time_limit_hrs', 12)
        self.cost_epsilon = config.mga_inputs.get('cost_epsilon', 0.01)

        self.hull: ConvexHull = None

        logger.info(
            'Initialized MGA sequencer with MGA Axis %s and weighting %s',
            self.mga_axis.name,
            self.mga_weighting.name,
        )

    def start(self):
        """Run the sequencer"""
        # ==== basic sequence ====
        # 1. Load the model data, which may involve filtering it down if source tracing
        # 2. Instantiate a Vector Manager pull in extra data to build out data for axis
        # 3. Solve the base model using persistent solver
        # 4. Adjust the model
        # 5. Start the re-solve loop

        # 1. Load data
        hybrid_loader = HybridLoader(db_connection=self.con, config=self.config)
        data_portal: DataPortal = hybrid_loader.load_data_portal(myopic_index=None)
        instance: TemoaModel = build_instance(
            loaded_portal=data_portal, model_name=self.config.scenario, silent=self.config.silent
        )

        # 2.  Instantiate the vector manager
        vector_manager: VectorManager = get_manager(
            axis=self.mga_axis, model=instance, weighting=self.mga_weighting, con=self.con
        )

        # 3. Persistent solver setup
        opt = self.solver
        # opt.set_instance(instance)
        tic = datetime.now()
        res: Results = opt.solve(instance)
        # TODO:  Experiment with this...  Not clear if it is needed to enable warm starts/persistent behavior
        toc = datetime.now()
        # load variables after first solve
        opt.load_vars()
        elapsed = toc - tic
        logger.info(f'Initial solve time: {elapsed.total_seconds():.4f}')
        # pts = np.array(
        #     [pyo.value(instance.V_FlowOut[idx]) for idx in instance.V_FlowOut.index_set()]
        # ).reshape((-1, 1))

        status = res.termination_condition
        logger.debug('Termination condition: %s', status.name)
        if status != pyomo_appsi.base.TerminationCondition.optimal:
            logger.error('Abnormal termination condition')
            sys.exit(-1)

        # 4. Capture cost and make it a constraint
        tot_cost = pyo.value(instance.TotalCost)
        logger.info('Completed initial solve with total cost:  %0.2f', tot_cost)
        logger.info('Relaxing cost by fraction:  %0.3f', self.cost_epsilon)
        # get hook on the expression generator for total cost...
        cost_expression = TotalCost_rule(instance)
        instance.cost_cap = pyo.Constraint(
            expr=cost_expression <= (1 + self.cost_epsilon) * tot_cost
        )
        opt.add_constraints([instance.cost_cap])

        # 5. replace the objective
        instance.del_component(instance.TotalCost)

        # 6. re-solve
        opt.set_instance(instance)
        opt.config.load_solution = False
        pts_mat = []
        for vector in vector_manager.basis_vectors():
            instance.obj = pyo.Objective(expr=vector)
            opt.set_objective(instance.obj)
            # instance.obj.display()
            tic = datetime.now()
            res = opt.solve(instance)
            toc = datetime.now()
            elapsed = toc - tic
            logger.info(f'Solve time: {elapsed.total_seconds()}')
            # need to load vars here or we see repeated stale value of objective
            opt.load_vars()
            status = res.termination_condition
            print(status)
            print(pyo.value(instance.obj))
            print(vector_manager.groups)
            pts = vector_manager.notify()
            pts_mat.append(pts)
            instance.del_component(instance.obj)

        # TODO:
        # make pts_mat an instance variable
        # make separate "new points" obj
        # extract resolve() function
        pts_mat = np.array(pts_mat)
        print(pts_mat)
        print(pts_mat.shape)

        self.hull = Hull(pts_mat)
        print('huge at: ', self.hull.cv_hull.volume)
        print(f'norms avail: {self.hull.norms_available}')
        #
        # new_norms = self.hull.equations[:, 0:-1]
        pts_mat = None
        vector_manager.load_normals(self.hull.get_all_norms())

        # let's loop for a while and rebuild hull when needed
        for i in range(20):
            print(f'iter {i}:', f'vecs_avail: {vector_manager.input_vectors_available()}')
            vector = vector_manager.next_input_vector()
            if vector is None:
                vector = vector_manager.random_input_vector()
                print('  ******* hitting the gas with a random vector')
            instance.obj = pyo.Objective(expr=vector)
            opt.set_objective(instance.obj)
            res = opt.solve(instance)
            opt.load_vars()
            status = res.termination_condition
            if status != pyomo_appsi.base.TerminationCondition.optimal:
                print('Abnormal termination condition')
            pts = [
                vector_manager.notify(),
            ]
            if pts_mat is None:
                pts_mat = np.array(pts)
            else:
                pts_mat = np.vstack((pts_mat, pts))

            if vector_manager.input_vectors_available() < 1000000:
                print(f'  Refreshing hull with {len(pts_mat)} points')
                for pt in pts_mat:
                    self.hull.add_point(pt)
                pts_mat = None
                self.hull.update()
                fresh_vecs = self.hull.get_all_norms()
                print(f'   made {len(fresh_vecs)} fresh vectors')
                print('   huge at: ', self.hull.cv_hull.volume)
                print(f'   rejection frac: {self.hull.norm_rejection_proportion}')
                vector_manager.load_normals(fresh_vecs)
            instance.del_component(instance.obj)

    def __del__(self):
        self.con.close()
