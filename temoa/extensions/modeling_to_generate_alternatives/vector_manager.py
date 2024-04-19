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
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Iterable

import numpy as np
from pyomo.environ import Expression, Var, quicksum


class VectorManager(ABC):
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

    @abstractmethod
    def variable_vector(self) -> list[Var]:
        """All variables in a fixed order sequence by group, member, internal var index order"""
        raise NotImplementedError()

    @abstractmethod
    def basis_vectors(self) -> list[Expression] | None:
        """The Initial Basis Vectors, likely to establish a hull, or None if n/a"""
        return None

    @abstractmethod
    def basis_runs_complete(self):
        """Simple notification that the requested basis runs are complete"""
        pass

    @abstractmethod
    def input_vectors_available(self) -> int | bool:
        """
        Indicator whether manager can provide more input vectors.
        Either an integer count, if available or True if an uncountable/arbitrary number are available
        :return: an integer count if known or True if an uncountable/arbitrary number are available, else False/0
        """

    @abstractmethod
    def next_input_vector(self) -> Expression:
        """The next input vector"""
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
    def notify(self) -> Sequence[float]:
        """
        Notify the manager that a solve has occurred.  It likely has access to the model...
        :return: The solution Point in axis space
        """

    @abstractmethod
    def stop_resolving(self) -> bool:
        """Query to stop re-solve loop.  True => stop re-solving."""
        raise NotImplementedError('the manager subclass must implement stop_resolving')
