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

"""
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterator, Iterable

import numpy as np
from pyomo.environ import Expression, Var, quicksum

from temoa.temoa_model.temoa_model import TemoaModel


class VectorManager(ABC):

    @abstractmethod
    def __init__(self, conn: sqlite3.Connection, base_model: TemoaModel, optimal_cost: float, cost_relaxation: float):
        """
        Initialize a new manager
        :param conn: connection to the current database
        :param base_model: the base model to clone for repetitive solves
        :param optimal_cost: the optimal cost of the primal solve
        :param cost_relaxation: the proportion to relax the optimal cost
        """
        raise NotImplementedError


    @property
    @abstractmethod
    def groups(self) -> Iterable[str]:
        """The main groups of the axis"""
        raise NotImplementedError()

    def group_members(self, group) -> list[str]:
        """The members in the group"""
        raise NotImplementedError()

    def group_variables(self, tech) -> list[Var]:
        """The variables associated with the individual group members"""
        raise NotImplementedError()


    def random_input_vector(self) -> Expression:
        """Random vector with proper dimensionality"""
        var_vec = self.variable_vector()
        coeffs = np.random.random(len(var_vec))
        coeffs /= sum(coeffs)
        return quicksum(c * v for c, v in zip(coeffs, var_vec))

    def load_normals(self, normals: np.array):
        raise NotImplementedError()

    @abstractmethod
    def stop_resolving(self) -> bool:
        """Query to stop re-solve loop.  True => stop re-solving."""
        raise NotImplementedError('the manager subclass must implement stop_resolving')

    @abstractmethod
    def instance_generator(self) -> Iterator[TemoaModel]:
        """generator for model instances to be solved"""
        raise NotImplementedError('the manager subclass must implement instance_generator')

    @abstractmethod
    def process_results(self, M: TemoaModel):
        raise NotImplementedError('the manager subclass must implement process_results')

