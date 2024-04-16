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
import pytest

from temoa.extensions.modeling_to_generate_alternatives.tech_activity_vectors import (
    TechActivityVectors,
)


def test__vector_engine():
    cat_map = {'A': ['dog', 'pig'], 'B': ['cat', 'horse', 'mouse']}
    res = [
        [0.5, 0.5, 0, 0, 0],
        [-0.5, -0.5, 0, 0, 0],
        [0, 0, 0.33, 0.33, 0.33],
        [0, 0, -0.33, -0.33, -0.33],
    ]
    matrix = TechActivityVectors._vector_engine(cat_map)
    for idx, row in enumerate(matrix):
        assert row == pytest.approx(res[idx], abs=1e-2)
