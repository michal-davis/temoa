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
Created on:  5/5/24

Class to contain Workers that execute solves in separate processes

"""
import logging
from datetime import datetime
from logging import getLogger, handlers
from multiprocessing import Process, Queue

from pyomo.opt import SolverFactory, SolverResults, check_optimal_termination

from temoa.temoa_model.temoa_model import TemoaModel


def worker_configurer(log_queue, log_level):
    h = handlers.QueueHandler(log_queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(log_level)
class Worker(Process):
    worker_idx = 1

    def __init__(self, model_queue: Queue, results_queue: Queue,
                 configurer, log_queue, log_level, **kwargs):
        super(Worker, self).__init__()
        configurer(log_queue, log_level)
        self.logger = getLogger(__name__)
        self.worker_number = Worker.worker_idx
        Worker.worker_idx += 1
        self.model_queue: Queue = model_queue
        self.results_queue: Queue = results_queue
        self.solver_name = kwargs["solver_name"]
        self.solver_options = kwargs["solver_options"]
        self.opt = SolverFactory(self.solver_name, options=self.solver_options)

    def run(self):
        self.logger.info('Worker %d spun up', self.worker_number)
        while True:
            model: TemoaModel = self.model_queue.get()
            tic = datetime.now()
            try:
                res: SolverResults = self.opt.solve(model)
            except Exception as e:
                self.logger.warning('Failed to solve model: %s... skipping', model.name)
                self.logger.warning('Exception: %s', e)
            toc = datetime.now()

            good_solve = check_optimal_termination(res)
            if good_solve:
                self.results_queue.put(model)
                self.logger.info('Worker %d solved a model in %0.2f minutes', self.worker_number, (toc - tic).minutes)
            else:
                status = res['Solver'].termination_condition
                self.logger.info('Worker %d did not solve.  Results status: %s', self.worker_number, status)

