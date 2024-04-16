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
from logging import getLogger

from pyomo.dataportal import DataPortal
from scipy.spatial import ConvexHull

from temoa.extensions.modeling_to_generate_alternatives.manager_factory import get_manager
from temoa.extensions.modeling_to_generate_alternatives.mga_constants import MgaAxis, MgaWeighting
from temoa.extensions.modeling_to_generate_alternatives.vector_manager import VectorManager
from temoa.temoa_model.hybrid_loader import HybridLoader
from temoa.temoa_model.run_actions import build_instance
from temoa.temoa_model.temoa_config import TemoaConfig

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

        self.hull: ConvexHull

        logger.info(
            'Initialized MGA sequencer with MGA Axis %s and weighting %s',
            self.mga_axis.name,
            self.mga_weighting.name,
        )

    def start(self):
        """Run the sequencer"""
        # ==== basic sequence ====
        # 1. Load the model data, which may involve filtering it down if source tracing
        # 2. Load the extra data needed by the MGA Axis (categories, etc.)
        # 3a. Coalesce these to get the MGA Vector established
        # 3b. Solve the base model using persistent solver
        # 4. Adjust the model
        # 5. Solve and record outcomes for all basis vectors

        # 1. Load data
        hybrid_loader = HybridLoader(db_connection=self.con, config=self.config)
        data_portal: DataPortal = hybrid_loader.load_data_portal(myopic_index=None)
        instance = build_instance(
            loaded_portal=data_portal, model_name=self.config.scenario, silent=self.config.silent
        )

        vector_manager: VectorManager = get_manager(
            axis=self.mga_axis, model=instance, weighting=self.mga_weighting, con=self.con
        )
        for v in vector_manager.basis_vectors():
            pass
            # print(v)

    def __del__(self):
        self.con.close()
