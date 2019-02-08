# view.py - maintain view on game world
# Copyright (C) 2019  Nguyễn Gia Phong
#
# This file is part of Axuy
#
# Axuy is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Axuy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Axuy.  If not, see <https://www.gnu.org/licenses/>.

from itertools import chain, combinations_with_replacement, permutations
from random import random

import moderngl
import numpy as np
from pyrr import Matrix44

from .misc import hex2f4, resource_filename
from .pico import Picobot

# map.npy is generated by ../tools/mapgen
SPACE = np.load(resource_filename('map.npy'))
OXY = np.float32([[0, 0, 0], [1, 0, 0], [1, 1, 0],
                  [1, 1, 0], [0, 1, 0], [0, 0, 0]])
OYZ = np.float32([[0, 0, 0], [0, 1, 0], [0, 1, 1],
                  [0, 1, 1], [0, 0, 1], [0, 0, 0]])
OZX = np.float32([[0, 0, 0], [1, 0, 0], [1, 0, 1],
                  [1, 0, 1], [0, 0, 1], [0, 0, 0]])
NEIGHBORS = set(chain.from_iterable(map(
    permutations, combinations_with_replacement((-1, 0, 1), 3))))

with open(resource_filename('space.vert')) as f: VERTEX_SHADER = f.read()
with open(resource_filename('space.frag')) as f: FRAGMENT_SHADER = f.read()


class View:
    """World map and camera placement.

    Parameters
    ----------
    mapid : iterable of ints
        order of nodes to sort map.npy.
    context : moderngl.Context
        OpenGL context from which ModernGL objects are created.

    Attributes
    ----------
    space : np.ndarray of bools
        3D array of occupied space.
    prog : moderngl.Program
        Processed executable code in GLSL.
    vao : moderngl.VertexArray
        Vertex data of the map.
    """

    def __init__(self, mapid, context):
        space = np.stack([SPACE[i] for i in mapid]).reshape(4, 4, 3, 3, 3, 3)
        oxy, oyz, ozx = set(), set(), set()
        self.space = np.zeros([12, 12, 9])
        for (a, b, c, d, e, f), occupied in np.ndenumerate(space):
            if occupied:
                x, y, z = a*3 + d, b*3 + e, c*3 + f
                i, j, k = (x+1) % 12, (y+1) % 12, (z+1) % 9
                for tx, ty, tz in NEIGHBORS:
                    xt, yt, zt = x + tx*12, y + ty*12, z + tz*9
                    it, jt, kt = i + tx*12, j + ty*12, k + tz*9
                    oxy.update(((xt, yt, zt), (xt, yt, kt)))
                    oyz.update(((xt, yt, zt), (it, yt, zt)))
                    ozx.update(((xt, yt, zt), (xt, jt, zt)))
                self.space[x][y][z] = 1
        vertices = []
        for i in oxy: vertices.extend(i+j for j in OXY)
        for i in oyz: vertices.extend(i+j for j in OYZ)
        for i in ozx: vertices.extend(i+j for j in OZX)

        self.prog = context.program(vertex_shader=VERTEX_SHADER,
                                    fragment_shader=FRAGMENT_SHADER)
        self.prog['color'].write(hex2f4('eeeeec').tobytes())
        vbo = context.buffer(np.stack(vertices).astype('f4').tobytes())
        self.vao = context.simple_vertex_array(self.prog, vbo, 'in_vert')

        x, y, z = random()*12, random()*12, random()*9
        while self.space[int(x)][int(y)][int(z)]:
            x, y, z = random()*12, random()*12, random()*9
        self.camera = Picobot(x, y, z, self.space)

    @property
    def pos(self):
        """Return camera position in a numpy array."""
        return self.camera.pos

    @property
    def right(self):
        """Return camera right direction."""
        return self.camera.rotation[0]

    @property
    def upward(self):
        """Return camera upward direction."""
        return self.camera.rotation[1]

    @property
    def forward(self):
        """Return camera forward direction."""
        return self.camera.rotation[2]

    def render(self, width, height, fov):
        """Render the map."""
        proj = Matrix44.perspective_projection(fov, width/height, 0.0001, 4)
        look = Matrix44.look_at(self.pos, self.pos + self.forward, self.upward)
        self.prog['mvp'].write((proj*look).astype(np.float32).tobytes())
        self.prog['eye'].write(np.float32(self.pos).tobytes())
        self.vao.render(moderngl.TRIANGLES)
