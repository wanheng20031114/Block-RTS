"""Author three editable northern residences using native Godot mesh resources.

Run with Python's standard library; no runtime geometry or external DCC required.
Every material/primitive pair is one MultiMesh batch, shared by scene instances.
Geometry stays inside a 6 x 5.5 m footprint (roof eaves: 6.4 x 5.9 m).

Godot class references consulted before choosing the native resources:
https://docs.godotengine.org/en/stable/classes/class_boxmesh.html
https://docs.godotengine.org/en/stable/classes/class_prismmesh.html
https://docs.godotengine.org/en/stable/classes/class_multimeshinstance3d.html
Official XML sources used when the documentation host returned HTTP 403:
https://github.com/godotengine/godot/tree/master/doc/classes
"""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/defense"
PALETTE = {
    "stone": (0.31, 0.37, 0.40),
    "mortar": (0.46, 0.51, 0.51),
    "plaster": (0.69, 0.68, 0.58),
    "timber": (0.27, 0.17, 0.115),
    "roof": (0.39, 0.19, 0.155),
    "snow": (0.88, 0.95, 0.98),
    "iron": (0.14, 0.19, 0.21),
    "glass": (1.0, 0.66, 0.25),
}


def write(path: Path, value: str) -> None:
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def fmt(values) -> str:
    return ", ".join(f"{value:.5f}" for value in values)


def mul(a, b):
    return [[sum(a[row][i] * b[i][col] for i in range(3)) for col in range(3)] for row in range(3)]


def basis(size, rotation):
    x, y, z = rotation
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    rotated = mul(ry, mul(rx, rz))
    return [[rotated[row][col] * size[col] for col in range(3)] for row in range(3)]


class Residence:
    def __init__(self, kind: str):
        self.kind = kind
        self.parts = defaultdict(list)
        self.bounds = []

    def add(self, material, center, size, rotation=(0, 0, 0), primitive="box", eave=False):
        b = basis(size, rotation)
        transform = [number for row in range(3) for number in (*b[row], center[row])]
        self.parts[(primitive, material)].append(transform)
        # Bounds use each primitive's conservative unit cube, including sloped roofs.
        half = [sum(abs(value) for value in row) * 0.5 for row in b]
        low = [center[i] - half[i] for i in range(3)]
        high = [center[i] + half[i] for i in range(3)]
        limit_x, limit_z = (3.2, 2.95) if eave else (3.0, 2.75)
        assert low[0] >= -limit_x - 0.001 and high[0] <= limit_x + 0.001, (self.kind, material, low, high)
        assert low[2] >= -limit_z - 0.001 and high[2] <= limit_z + 0.001, (self.kind, material, low, high)
        assert low[1] >= -0.001 and high[1] <= 6.5, (self.kind, material, low, high)
        self.bounds.append((low, high))

    def beam(self, start, end, thickness=0.15, material="timber"):
        delta = [end[i] - start[i] for i in range(3)]
        length = math.sqrt(sum(value * value for value in delta))
        yaw = math.atan2(delta[0], delta[2])
        pitch = -math.asin(delta[1] / length)
        self.add(material, [(start[i] + end[i]) * 0.5 for i in range(3)], (thickness, thickness, length), (pitch, yaw, 0), eave=True)

    def roof(self, cx, cz, width, depth, eave_y, rise, sideways=False):
        angle = math.atan2(rise, width * 0.5)
        slope_length = math.hypot(rise, width * 0.5)
        yaw = math.pi * 0.5 if sideways else 0
        for side in (-1, 1):
            sx, sz = side * width * 0.25, 0
            px, pz = cx + math.cos(yaw) * sx, cz - math.sin(yaw) * sx
            rot = (0, yaw, -side * angle)
            self.add("roof", (px, eave_y + rise * 0.5, pz), (slope_length, 0.15, depth), rot, eave=True)
            # Thick snow blankets sit above red eaves with a deliberate exposed hem.
            self.add("snow", (px, eave_y + rise * 0.5 + 0.13, pz), (slope_length - 0.14, 0.14, depth - 0.11), rot, eave=True)
        ridge_size = (0.23, 0.19, depth + 0.02)
        self.add("snow", (cx, eave_y + rise + 0.16, cz), ridge_size, (0, yaw, 0), eave=True)
        # Exposed gable rafters and central truss are visible against pale plaster.
        for end in (-1, 1):
            def point(x, y, z):
                return (cx + math.cos(yaw) * x + math.sin(yaw) * z, y, cz - math.sin(yaw) * x + math.cos(yaw) * z)
            for side in (-1, 1):
                self.beam(point(side * width * 0.48, eave_y - 0.09, end * (depth * 0.5 - 0.07)), point(0, eave_y + rise - 0.07, end * (depth * 0.5 - 0.07)), 0.14)

    def shell(self, width, depth, wall_height, roof_rise, sideways=False):
        self.add("stone", (0, 0.24, 0), (width + 0.22, 0.48, depth + 0.18))
        self.add("plaster", (0, 0.43 + wall_height * 0.5, 0), (width, wall_height, depth))
        # Distinct dressed-stone blocks make the foundation read as masonry.
        for side in (-1, 1):
            for i in range(6):
                self.add("mortar", (-width * 0.5 + (i + 0.5) * width / 6, 0.27, side * (depth * 0.5 + 0.102)), (width / 6 - 0.035, 0.31, 0.055))
        top = wall_height + 0.43
        gable_width, gable_depth = (depth, width) if sideways else (width, depth)
        yaw = math.pi * 0.5 if sideways else 0
        self.add("plaster", (0, top + roof_rise * 0.5, 0), (gable_width, roof_rise, gable_depth), (0, yaw, 0), "prism")
        self.roof(0, 0, gable_width + 0.48, gable_depth + 0.42, top + 0.01, roof_rise, sideways)
        for x in (-width * 0.5, 0, width * 0.5):
            for z in (-depth * 0.5 - 0.025, depth * 0.5 + 0.025):
                self.add("timber", (x, 0.43 + wall_height * 0.5, z), (0.18, wall_height + 0.05, 0.13))
        for y in (0.58, top - 0.07):
            for z in (-depth * 0.5 - 0.035, depth * 0.5 + 0.035):
                self.add("timber", (0, y, z), (width + 0.11, 0.15, 0.16))
            for x in (-width * 0.5 - 0.025, width * 0.5 + 0.025):
                self.add("timber", (x, y, 0), (0.15, 0.15, depth + 0.1))
        return top

    def window(self, x, y, z, width=0.63, height=0.77, side=0):
        yaw = side * math.pi * 0.5
        def point(dx, dy, dz):
            return (x + math.cos(yaw) * dx + math.sin(yaw) * dz, y + dy, z - math.sin(yaw) * dx + math.cos(yaw) * dz)
        def box(material, offset, size):
            self.add(material, point(*offset), size, (0, yaw, 0))
        box("timber", (0, 0, 0), (width + 0.17, height + 0.17, 0.11))
        box("glass", (0, 0, 0.063), (width, height, 0.034))
        for offset, size in [((0, 0, 0.092), (0.065, height, 0.055)), ((0, 0, 0.092), (width, 0.065, 0.055))]:
            box("timber", offset, size)
        box("snow", (0, -height * 0.5 - 0.085, 0.04), (width + 0.3, 0.10, 0.24))
        for sign in (-1, 1):
            box("roof", (sign * (width * 0.5 + 0.19), 0, 0.022), (0.23, height + 0.03, 0.075))

    def door(self, x, z, porch=True):
        self.add("timber", (x, 1.28, z + 0.035), (0.97, 1.76, 0.13))
        for i in range(4):
            self.add("roof", (x - 0.33 + i * 0.22, 1.23, z + 0.109), (0.19, 1.58, 0.035))
        for y in (0.8, 1.7):
            self.add("iron", (x, y, z + 0.138), (0.77, 0.075, 0.032))
        self.add("iron", (x + 0.28, 1.28, z + 0.165), (0.065, 0.14, 0.045))
        self.add("stone", (x, 0.17, z + 0.44), (1.23, 0.34, 0.65))
        if porch:
            for sign in (-1, 1):
                self.add("timber", (x + sign * 0.7, 1.36, z + 0.69), (0.14, 2.48, 0.14))
            self.roof(x, z + 0.38, 1.70, 0.96, 2.59, 0.47)

    def chimney(self, x, z, bottom, height):
        self.add("stone", (x, bottom + height * 0.5, z), (0.57, height, 0.60))
        for i in range(3):
            y = bottom + height - 0.15 - i * 0.24
            self.add("mortar", (x, y, z + 0.308), (0.52, 0.14, 0.025))
        self.add("iron", (x, bottom + height + 0.06, z), (0.72, 0.12, 0.73))
        self.add("snow", (x, bottom + height + 0.145, z - 0.13), (0.66, 0.08, 0.32))

    def firewood(self, x, z):
        for row in range(3):
            for col in range(3 - row):
                self.add("timber", (x + (col + row * 0.5 - 1) * 0.23, 0.15 + row * 0.19, z), (0.21, 0.95, 0.21), (math.pi * 0.5, 0, 0), "log")
        self.add("snow", (x, 0.64, z), (0.52, 0.10, 0.94))

    def crate(self, x, z):
        self.add("roof", (x, 0.37, z), (0.65, 0.64, 0.65))
        for dx in (-0.28, 0.28):
            self.add("timber", (x + dx, 0.37, z + 0.34), (0.075, 0.67, 0.07))
        for y in (0.095, 0.655):
            self.add("timber", (x, y, z + 0.34), (0.65, 0.075, 0.07))
        self.add("snow", (x, 0.73, z), (0.66, 0.09, 0.66))

    def save(self):
        refs, resources, nodes = [], [], []
        all_low = [min(a[i] for a, _ in self.bounds) for i in range(3)]
        all_high = [max(b[i] for _, b in self.bounds) for i in range(3)]
        dimensions = [all_high[i] - all_low[i] for i in range(3)]
        for (primitive, material), instances in self.parts.items():
            key = f"{primitive}_{material}"
            refs.append(f'[ext_resource type="Mesh" path="res://assets/defense/residence_{key}.tres" id="{key}"]')
            resources.append(f'[sub_resource type="MultiMesh" id="{key}"]\ntransform_format = 1\ninstance_count = {len(instances)}\nmesh = ExtResource("{key}")\ncustom_aabb = AABB({fmt(all_low + dimensions)})\nbuffer = PackedFloat32Array({fmt([v for item in instances for v in item])})')
            nodes.append(f'[node name="{primitive.title()}{material.title()}" type="MultiMeshInstance3D" parent="."]\nmultimesh = SubResource("{key}")')
        header = f'[gd_scene load_steps={1 + len(refs) + len(resources)} format=3]'
        root = f'[node name="Residence{self.kind.title()}" type="Node3D"]\nmetadata/building_kind = "residence"\nmetadata/front = "+Z"\nmetadata/authoring_tool = "tools/build_snowfield_residences.py"\nmetadata/primitive_count = {sum(len(items) for items in self.parts.values())}'
        write(ART / f"residence_{self.kind}.tscn", "\n\n".join([header, *refs, *resources, root, *nodes]))
        print(f'{self.kind}: {len(self.parts)} draw batches, {sum(len(items) for items in self.parts.values())} pieces; AABB [{fmt(all_low)}] [{fmt(all_high)}]')


def shared_resources():
    for material, color in PALETTE.items():
        properties = f'roughness = 0.92\nalbedo_color = Color({fmt((*color, 1))})'
        if material == "glass":
            properties += '\nemission_enabled = true\nemission = Color(1, 0.40, 0.08, 1)\nemission_energy_multiplier = 0.75'
        if material == "iron":
            properties += '\nmetallic = 0.45'
        meshes = [("box", "BoxMesh", "size = Vector3(1, 1, 1)")]
        if material == "plaster":
            meshes.append(("prism", "PrismMesh", "size = Vector3(1, 1, 1)"))
        if material == "timber":
            meshes.append(("log", "CylinderMesh", "top_radius = 0.5\nbottom_radius = 0.5\nheight = 1.0\nradial_segments = 6\nrings = 1"))
        for primitive, godot_class, settings in meshes:
            write(ART / f"residence_{primitive}_{material}.tres", f'[gd_resource type="{godot_class}" load_steps=2 format=3]\n\n[sub_resource type="StandardMaterial3D" id="Finish"]\n{properties}\n\n[resource]\nmaterial = SubResource("Finish")\n{settings}')


def cottage():
    r = Residence("cottage")
    top = r.shell(4.35, 3.40, 2.38, 1.50)
    r.door(-0.50, 1.73)
    r.window(1.20, 1.52, 1.765)
    r.window(-1.23, 1.56, -1.765, side=2)
    r.window(2.22, 1.52, -0.45, side=1)
    r.window(-2.22, 1.52, 0.05, side=-1)
    r.window(0, top + 0.49, 1.755, 0.38, 0.46)
    r.chimney(1.33, -0.78, top + 0.20, 1.39)
    r.firewood(-2.60, -0.70)
    r.crate(2.38, 2.06)
    r.save()


def townhouse():
    r = Residence("townhouse")
    top = r.shell(3.80, 3.30, 3.96, 1.59)
    r.door(0, 1.68)
    for x in (-1.05, 1.05):
        r.window(x, 1.46, 1.705, 0.52, 0.78)
        r.window(x, 3.29, 1.705, 0.67, 0.95)
        r.window(x, 3.29, -1.705, 0.67, 0.95, side=2)
    for side in (-1, 1):
        for y in (1.55, 3.32):
            r.window(side * 1.945, y, -0.52, 0.62, 0.81, side=side)
        r.add("timber", (0, 2.42, side * 1.69), (3.93, 0.19, 0.18))
        r.beam((-1.81, 2.52, side * 1.72), (-0.25, 3.99, side * 1.72), 0.12)
    r.window(0, top + 0.47, 1.70, 0.36, 0.41)
    r.chimney(-1.09, -0.63, top + 0.23, 1.37)
    # Lower annex changes the silhouette without exceeding the common plot.
    r.add("plaster", (2.32, 1.08, -0.42), (0.77, 1.70, 2.06))
    r.add("stone", (2.32, 0.18, -0.42), (0.89, 0.36, 2.16))
    r.add("roof", (2.36, 2.16, -0.42), (1.14, 0.15, 2.29), (0, 0, -0.35), eave=True)
    r.add("snow", (2.36, 2.27, -0.42), (1.12, 0.12, 2.25), (0, 0, -0.35), eave=True)
    r.firewood(-2.43, -0.48)
    r.crate(2.36, 1.49)
    r.save()


def longhouse():
    r = Residence("longhouse")
    top = r.shell(5.46, 3.25, 2.22, 1.58, sideways=True)
    r.door(1.55, 1.66)
    for x in (-1.84, -0.20):
        r.window(x, 1.43, 1.685, 0.75, 0.73)
    for x in (-1.75, 0, 1.75):
        r.window(x, 1.43, -1.685, 0.68, 0.72, side=2)
    r.window(-2.775, 1.5, 0, 0.62, 0.79, side=-1)
    # Front dormer gives the broad roof a broken silhouette and a warm attic.
    r.add("plaster", (-0.58, 3.20, 1.05), (1.30, 0.76, 0.70))
    r.add("plaster", (-0.58, 3.79, 1.05), (1.30, 0.43, 0.70), primitive="prism")
    r.roof(-0.58, 1.05, 1.56, 0.96, 3.59, 0.48)
    r.window(-0.58, 3.22, 1.427, 0.58, 0.48)
    r.chimney(1.87, -0.71, top + 0.42, 1.31)
    r.firewood(-2.27, 2.22)
    r.crate(2.17, -2.21)
    r.save()


def main():
    ART.mkdir(parents=True, exist_ok=True)
    shared_resources()
    cottage()
    townhouse()
    longhouse()


if __name__ == "__main__":
    main()
