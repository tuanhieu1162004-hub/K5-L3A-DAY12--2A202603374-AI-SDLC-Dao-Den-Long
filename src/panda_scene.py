"""Procedural low-poly models for the island."""

from math import cos, pi, sin
from random import Random

from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter


def model(parent, name, rings, colors, sides=16):
    data = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    vertices = GeomVertexWriter(data, "vertex")
    normals = GeomVertexWriter(data, "normal")
    vertex_colors = GeomVertexWriter(data, "color")
    triangles = GeomTriangles(Geom.UHStatic)
    index = 0
    for layer, ((lower_radius, lower_z), (upper_radius, upper_z)) in enumerate(zip(rings, rings[1:])):
        for face in range(sides):
            a, b = ((face + offset) * 2 * pi / sides for offset in (0, 1))
            angle = (a + b) / 2
            dz = upper_z - lower_z
            dr = lower_radius - upper_radius
            length = max(0.0001, (dz * dz + dr * dr) ** .5)
            normal = (cos(angle) * dz / length, sin(angle) * dz / length, dr / length)
            color = colors[layer % len(colors)]
            contrast = .025 if dz == 0 else .09
            shade = 1 - contrast + contrast * cos(face * 2.4)
            for radius, z, theta in ((lower_radius,lower_z,a),(lower_radius,lower_z,b),
                                      (upper_radius,upper_z,b),(upper_radius,upper_z,a)):
                vertices.addData3(radius * cos(theta), radius * sin(theta), z)
                normals.addData3(*normal)
                vertex_colors.addData4(*(channel * shade for channel in color), 1)
            triangles.addVertices(index, index + 1, index + 2)
            triangles.addVertices(index, index + 2, index + 3)
            index += 4
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    return parent.attachNewNode(node)


def place(node, point):
    x, y, z = point
    node.setPos(x, z, y)


def island(parent, radius, x=0):
    node = model(parent, "floating island",
                 [(0,-11),(radius*.65,-8),(radius*.91,-4),(radius,-.4),(radius,0),(0,0)],
                 [(.18,.15,.25),(.28,.22,.34),(.34,.29,.43),(.31,.39,.31),(.24,.43,.34)], 40)
    node.setX(x)


def lantern(parent):
    node = parent.attachNewNode("lantern")
    model(node,"post",[(.40,0),(.29,.20),(.14,.31),(.14,2.65)],
          [(.43,.28,.20),(.52,.33,.22),(.39,.25,.18)], 8)
    model(node,"frame",[(0,1.75),(.51,1.75),(.57,1.90),(.57,2.47),(.42,2.62),(0,2.77)],
          [(.29,.19,.22),(.71,.32,.23),(.32,.23,.32),(.71,.32,.23),(.38,.23,.23)], 8)
    paper = model(node,"lantern paper",[(0,1.91),(.53,1.91),(.60,2.10),(.60,2.32),(.51,2.45),(0,2.45)],
                  [(1,.68,.30)], 8)
    return node, paper


def keeper(parent):
    node = parent.attachNewNode("May")
    model(node,"tunic",[(.28,.08),(.39,.22),(.37,.65),(.24,.94),(0,.98)], [(.23,.63,.61),(.28,.75,.68)])
    model(node,"face",[(0,.82),(.25,.91),(.29,1.15),(.20,1.38),(0,1.43)], [(.95,.72,.51)])
    model(node,"conical hat",[(0,1.32),(.57,1.34),(.53,1.39),(0,1.81)], [(.72,.49,.26),(.98,.79,.42),(.91,.67,.34)])
    charm = model(node,"small lantern",[(0,.78),(.13,.8),(.15,1),(.09,1.1),(0,1.11)], [(1,.68,.24)], 8)
    charm.setX(.41)
    return node


def landscape(parent, night, lantern_positions):
    rng = Random(731 + night)
    centers = (0, 70) if night == 2 else (0,)
    edge = {1: 40, 2: 28, 3: 45}[night]
    tree = model(parent, "cedar model", [(0,0),(.30,0),(.22,2.5),(.12,3.4)],
                 [(.35,.23,.26)], 7)
    for height, spread, color in ((1.1,1.6,(.15,.36,.35)),(2.0,1.3,(.18,.45,.43)),(2.8,.9,(.28,.56,.49))):
        model(tree,"cedar needles",[(0,height),(spread,height+.15),(0,height+1.8)],
              [(.12,.23,.29),color], 7)
    rock = model(parent,"basalt model",[(0,-.1),(.8,0),(.73,.51),(.42,.87),(0,.94)],
                 [(.29,.28,.40),(.38,.36,.51),(.48,.45,.60)],7)
    stone = model(parent,"path stone model",[(.64,.015),(.62,.06),(0,.075)],
                  [(.48,.46,.50),(.53,.52,.56)],7)
    for center in centers:
        for index in range(27):
            angle = index * 2*pi/27 + rng.uniform(-.05,.05)
            radius = rng.uniform(edge-9,edge-3)
            x, y = center + radius*cos(angle), radius*sin(angle)
            if night == 2 and abs(y) < 3:
                continue
            template = tree if index % 3 != 0 else rock
            detail = template.copyTo(parent)
            detail.setPos(x,y,0)
            detail.setScale(rng.uniform(.8,1.45))
            detail.setH(rng.uniform(0,360))
    for x, level, y in lantern_positions:
        if level != 0:
            continue
        center = 70 if night == 2 and x > 45 else 0
        distance = ((x-center)**2+y*y)**.5
        for step in range(2,int(distance/1.65)):
            fraction = step * 1.65 / distance
            detail = stone.copyTo(parent)
            detail.setPos(center+(x-center)*fraction+rng.uniform(-.35,.35),
                          y*fraction+rng.uniform(-.35,.35),0)
            detail.setH(rng.uniform(0,360))
    for template in (tree, rock, stone):
        template.removeNode()
