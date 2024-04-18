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
Created on:  4/17/24

A thin wrapper on Scipy's ConvexHull to make it more manageable
"""
from logging import getLogger

import numpy as np
import scipy
from scipy.spatial import ConvexHull

logger = getLogger(__name__)


class Hull:
    def __init__(self, points: np.ndarray, **kwargs):
        # the number of columns in the first volley of points sets the dimensions of the hull
        self.dim = points.shape[1]
        if self.dim > points.shape[0]:
            logger.error('Hull dimension less than points')
            raise ValueError('Hull dimension less than points')
        logger.info(
            'Initializing Hull with points: %d and dimensions: %d', points.shape[0], points.shape[1]
        )

        self.cv_hull = None
        # containers to manage new and explored directions
        self.seen_directions = None
        self.valid_vectors = None

        self.tolerance = 5e-2  # minimum cosine dissimilarity

        self.good_points = None  # safe keeping in case we crash later
        self.all_points = points.copy()
        self.vec_index = 0  # pointer to the next new vector from the stack
        self.update()

    @property
    def valid_directions_avialable(self) -> int:
        if not self.valid_vectors:
            return 0
        elif np.ndim(self.valid_vectors) == 1:
            return 1 - self.vec_index
        else:
            return len(self.valid_vectors) - self.vec_index

    def update(self):
        """
        Update the Hull based on new points.
        :return:
        """
        if self.all_points is None:
            return
        try:
            self.cv_hull = ConvexHull(self.all_points, qhull_options='Q12')
            # Q12:  Allow "wide" facets, which seems to happen with large disparity in scale in model
            # QJ:  option to "joggle" inputs if errors arise from singularities, etc.
            # Dev Note:  After significant experiments with building new each time or allowing "incremental"
            #            additions to the hull, it appears more ROBUST to just rebuild.  More frequent
            #            exits when trying to use incremental, and time difference is negligible for this few pts.
            self.good_points = self.cv_hull.points
        except scipy.spatial._qhull.QhullError as e:
            logger.error(
                'Initial attempt at hull construction from basis vectors failed.'
                '\nMay be non-recoverable.  Possibly try a set of random vectors to initialize the Hull.'
            )
            logger.error(e)
            raise RuntimeError('Hull construction from basis vectors failed.  See log file')

        equations = self.cv_hull.equations[:, 0:-1]
        for row in equations:
            row = row / np.linalg.norm(row)  # ensure it is a unit vector
            if self.is_new_direction(row):
                if self.valid_vectors is None:
                    self.valid_vectors = row
                else:
                    self.valid_vectors = np.vstack((self.valid_vectors, row))

    def add_point(self, point: np.ndarray):
        if self.all_points is None:
            self.all_points = point
        else:
            self.all_points = np.vstack((self.all_points, point))

    def get_vector(self) -> np.ndarray:
        """
        pop a new direction vector from the stack
        :return: a new direction vector
        """
        if self.vec_index < len(self.valid_vectors):
            if np.ndim(self.valid_vectors) == 1:  # only one on the stack
                res = self.valid_vectors
            else:
                res = self.valid_vectors[self.vec_index, :]
            self.vec_index += 1
            return res
        return None

    def is_new_direction(self, vec: np.ndarray) -> bool:
        """
        compare vector to all directions already processed
        :param vec: the new vector to consider
        :return: True if the new vector is a valid direction, False otherwise"""
        if self.seen_directions is None:
            self.seen_directions = vec
            return True
        max_similarity = np.max(self.seen_directions.dot(vec))
        if 1 - max_similarity < self.tolerance:
            return False
        else:
            if self.seen_directions is None:
                self.seen_directions = vec
            else:
                self.seen_directions = np.vstack((self.seen_directions, vec))
            return True
