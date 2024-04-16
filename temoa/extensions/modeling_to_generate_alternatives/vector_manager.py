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
from abc import ABC
from typing import Iterable

from pyomo.core import Expression
from pyomo.environ import Var


class VectorManager(ABC):
    @property
    def groups(self) -> Iterable[str]:
        """The main groups of the axis"""
        raise NotImplementedError

    def group_members(self, group) -> list[str]:
        """The members in the group"""
        raise NotImplementedError

    def tech_variables(self, tech) -> list[Var]:
        """The variables associated with the individual group members"""
        raise NotImplementedError

    def basis_vectors(self) -> Expression:
        """the basis vectors"""
        raise NotImplementedError
