"""Author an editable winter river, its crossing markers and matching collision.

This is offline authoring: play loads saved OBJ meshes, ShaderMaterials and
native StaticBody3D/ConvexPolygonShape3D nodes. Navigation and water collision
use exactly the same one-metre convex strips, including crossing boundaries.

Godot references consulted before authoring:
https://docs.godotengine.org/en/stable/classes/class_arraymesh.html
https://docs.godotengine.org/en/stable/classes/class_convexpolygonshape3d.html
https://docs.godotengine.org/en/stable/classes/class_shadermaterial.html
"""
from __future__ import annotations

import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/defense"
BANK_MARGIN = 1.5
SAMPLE_STEP = 1.0
Z_SAMPLES = tuple(float(z) for z in range(-72, 73))
CROSSING_HALF_DEPTH = 8.0
CROSSINGS = (
    {"name": "North", "z": -40.0, "kind": "ice", "width": 16.0},
    {"name": "Center", "z": 0.0, "kind": "bridge", "width": 16.0},
    {"name": "South", "z": 40.0, "kind": "ice", "width": 16.0},
)


def river_x(z: float) -> float:
    return 8.0 + 9.0 * math.sin(z * .045) + 3.0 * math.sin(z * .11)


def river_half_width(z: float) -> float:
    return 7.5 + math.sin(z * .06 + .8)


def river_outer_bank_x(z: float, side: int) -> float:
    return river_x(z) + side * (river_half_width(z) + BANK_MARGIN)


def crossing_at(z: float):
    return next((crossing for crossing in CROSSINGS
                 if abs(z - crossing["z"]) <= CROSSING_HALF_DEPTH), None)


def water_collision_polygons():
    """Return the authored strips in the same order as the scene's water walls."""
    result = []
    for low, high in zip(Z_SAMPLES, Z_SAMPLES[1:]):
        if crossing_at((low + high) * .5):
            continue
        result.append(((river_x(low) - river_half_width(low), low),
                       (river_x(low) + river_half_width(low), low),
                       (river_x(high) + river_half_width(high), high),
                       (river_x(high) - river_half_width(high), high)))
    return tuple(result)


WATER_POLYGONS = water_collision_polygons()


def _distance_squared_to_segment(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((x-a[0])*dx + (z-a[1])*dz) / (dx*dx + dz*dz)))
    return (x-a[0]-t*dx)**2 + (z-a[1]-t*dz)**2


def is_water_blocked(x: float, z: float, padding: float = 1.15) -> bool:
    """Test the scene's convex water walls expanded by navigation clearance."""
    if abs(x-river_x(z)) > river_half_width(z) + padding + 2.0:
        return False
    for polygon in WATER_POLYGONS:
        if z < polygon[0][1]-padding or z > polygon[2][1]+padding:
            continue
        inside = True
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            if (b[0]-a[0])*(z-a[1]) - (b[1]-a[1])*(x-a[0]) < 0.0:
                inside = False
            if padding > 0.0 and _distance_squared_to_segment(x, z, a, b) < padding*padding:
                return True
        if inside:
            return True
    return False


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _vector(values):
    return "Vector3(" + ", ".join(f"{value:.5f}" for value in values) + ")"


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


class Mesh:
    """Small flat-shaded OBJ writer; the importer supplies native ArrayMeshes."""
    def __init__(self, name):
        self.name = name
        self.faces = []

    def triangle(self, a, b, c, facing=(0.0, 1.0, 0.0)):
        ab = tuple(b[i]-a[i] for i in range(3))
        ac = tuple(c[i]-a[i] for i in range(3))
        normal = _cross(ab, ac)
        if sum(normal[i]*facing[i] for i in range(3)) < 0.0:
            b, c = c, b
            normal = tuple(-v for v in normal)
        length = math.sqrt(sum(v*v for v in normal))
        if length > 1e-8:
            self.faces.append((a, b, c, tuple(v/length for v in normal)))

    def quad(self, a, b, c, d, facing=(0.0, 1.0, 0.0)):
        self.triangle(a, b, c, facing)
        self.triangle(a, c, d, facing)

    def box(self, x0, x1, y0, y1, z0, z1):
        points = [(x, y, z) for y in (y0, y1) for z in (z0, z1) for x in (x0, x1)]
        for ids, facing in [((4, 5, 7, 6), (0, 1, 0)),
                            ((0, 2, 3, 1), (0, -1, 0)),
                            ((0, 1, 5, 4), (0, 0, -1)),
                            ((2, 6, 7, 3), (0, 0, 1)),
                            ((0, 4, 6, 2), (-1, 0, 0)),
                            ((1, 3, 7, 5), (1, 0, 0))]:
            self.quad(*(points[i] for i in ids), facing=facing)

    def save(self):
        lines = ["# Authored winter river; Wavefront CCW faces are converted by Godot's OBJ importer.", f"o {self.name}"]
        for a, b, c, _normal in self.faces:
            for point in (a, b, c):
                lines.append("v " + " ".join(f"{v:.6f}" for v in point))
        for _a, _b, _c, normal in self.faces:
            lines.append("vn " + " ".join(f"{v:.6f}" for v in normal))
        for index in range(len(self.faces)):
            start = index*3 + 1
            lines.append("f " + " ".join(f"{vertex}//{index+1}" for vertex in range(start, start+3)))
        _write(ART / f"{self.name}.obj", "\n".join(lines))


def _strip(mesh, za, zb, side, outer_offset, inner_offset, outer_y, inner_y):
    def point(z, offset, y):
        return (river_x(z) + side*(river_half_width(z)+offset), y, z)
    mesh.quad(point(za, outer_offset, outer_y), point(zb, outer_offset, outer_y),
              point(zb, inner_offset, inner_y), point(za, inner_offset, inner_y))


def _sheet(mesh, za, zb, extra, y):
    mesh.quad((river_x(za)-river_half_width(za)-extra, y, za),
              (river_x(zb)-river_half_width(zb)-extra, y, zb),
              (river_x(zb)+river_half_width(zb)+extra, y, zb),
              (river_x(za)+river_half_width(za)+extra, y, za))


def _floe(mesh, rng, x, z, radius, top):
    count = rng.randrange(5, 8)
    angle = rng.uniform(0.0, math.tau)
    perimeter = []
    for index in range(count):
        theta = angle + index*math.tau/count
        r = radius*rng.uniform(.82, 1.10)
        perimeter.append((x+math.cos(theta)*r, top+rng.uniform(-.025, .025), z+math.sin(theta)*r*.78))
    for index, a in enumerate(perimeter):
        b = perimeter[(index+1) % count]
        mesh.triangle((x, top+.03, z), a, b)
        facing = ((a[0]+b[0])*.5-x, 0.0, (a[2]+b[2])*.5-z)
        mesh.quad(a, b, (b[0], -.39, b[2]), (a[0], -.39, a[2]), facing)


def _broken_frozen_edge(mesh, z, direction, rng):
    """Thin, sinking shelves outside the flat crossing; water stays impassable.

    Every ice crossing still has its entire surveyed 16-metre deck at y=0.
    Only these visual fringes extend over water. Unequal shards cover the old
    straight seam without changing any collision or navigable boundary.
    """
    inner, outer = [], []
    count = 17
    for index in range(count):
        u = -1.0 + 2.0*index/(count-1)
        extension = rng.uniform(.38, 1.65)
        extension += .25*math.sin(index*.7+z)
        if index % 4 == 1:
            extension *= .40
        edge_z = z+direction*extension
        inner.append((river_x(z)+u*(river_half_width(z)-.04), 0.0, z))
        outer.append((river_x(edge_z)+u*(river_half_width(edge_z)-.04),
                      rng.uniform(-.24,-.10), edge_z))
    for index in range(count-1):
        mesh.quad(inner[index],inner[index+1],outer[index+1],outer[index])
        a,b = outer[index],outer[index+1]
        mesh.quad(a,b,(b[0],-.39,b[2]),(a[0],-.39,a[2]),(0,0,direction))
    for index in range(5):
        chip_z=z+direction*rng.uniform(1.9,3.2)
        u=-.82+index*.41+rng.uniform(-.10,.10)
        chip_x=river_x(chip_z)+u*(river_half_width(chip_z)-.8)
        _floe(mesh,rng,chip_x,chip_z,rng.uniform(.32,.67),rng.uniform(-.28,-.19))


def _write_shaders():
    _write(ART / "river_layout.gdshaderinc", '''// Shared snowfield river layout, authored by tools/snowfield_river.py.
float snow_river_x(float z) {
    return 8.0 + 9.0 * sin(z * 0.045) + 3.0 * sin(z * 0.11);
}
float snow_river_half_width(float z) {
    return 7.5 + sin(z * 0.06 + 0.8);
}
bool snow_river_crossing(float z) {
    return abs(z + 40.0) <= 8.0 || abs(z) <= 8.0 || abs(z - 40.0) <= 8.0;
}''')
    _write(ART / "river_water.gdshader", '''shader_type spatial;
render_mode cull_back;
#include "res://assets/defense/river_layout.gdshaderinc"
varying vec2 river_position;
void vertex() { river_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz; }
void fragment() {
    vec2 p = river_position;
    float offset = p.x - snow_river_x(p.y);
    float across = abs(offset) / snow_river_half_width(p.y);
    float current = sin(p.y * 1.35 - TIME * 1.05 + sin(offset * 1.45) * 1.1);
    float ripple = sin(offset * 3.6 + p.y * .35 - TIME * .85) * .5 + .5;
    float ribbons = pow(.5 + .5*sin(offset*2.1 + sin(p.y*.22-TIME*.28)*1.7), 18.0);
    float edge = smoothstep(.66, 1.0, across);
    vec3 deep = mix(vec3(.022,.082,.12), vec3(.045,.16,.21), current*.5+.5);
    vec3 shallow = vec3(.14,.29,.36);
    ALBEDO = mix(deep, shallow, edge*.61) + ripple*.006 + ribbons*vec3(.013,.028,.031);
    ROUGHNESS = .30 + ripple*.10;
    METALLIC = 0.0;
    SPECULAR = .30;
}''')
    _write(ART / "river_ice.gdshader", '''shader_type spatial;
render_mode cull_back;
#include "res://assets/defense/river_layout.gdshaderinc"
varying vec3 ice_position;
varying vec3 ice_normal;
void vertex() {
    ice_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    ice_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}
void fragment() {
    vec2 p = ice_position.xz;
    float cloud = .5+.22*sin(p.x*.41+p.y*.21)+.19*sin(p.y*.7-p.x*.23);
    float u = p.x-snow_river_x(p.y);
    float v = p.y-(p.y<0.0 ? -40.0 : 40.0);
    // A few branching stress fractures replace the uniform cellular web.
    float main_seam = abs(v-u*.27-.35*sin(u*1.70)-.10*sin(u*4.8));
    float branch_a = abs(u-v*1.75-1.6+.23*sin(v*3.1)+.09*sin(v*7.1));
    branch_a += (1.0-smoothstep(.4,1.1,v))*20.0;
    float branch_b = abs(v+u*.83+2.1+.22*sin(u*2.9));
    branch_b += smoothstep(-1.1,-.3,u)*20.0;
    float branch_c = abs(v-u*.41-4.7+.16*sin(u*3.3));
    branch_c += smoothstep(2.3,3.1,u)*20.0;
    float crack_distance = min(main_seam,min(branch_a,min(branch_b,branch_c)));
    float thickness = .014+.030*(.5+.5*sin(p.x*.77+p.y*.43));
    float fissure = 1.0-smoothstep(thickness,thickness+.028,crack_distance);
    float fracture_rim = (1.0-smoothstep(thickness+.035,thickness+.13,crack_distance))*(1.0-fissure);
    float fine = pow(1.0-abs(sin(p.x*.73+p.y*1.3+sin(p.y*.23)*2.5)),55.0)*.05;
    float bank = abs(u)-snow_river_half_width(p.y);
    float end_frost = smoothstep(6.5,8.8,abs(v)+sin(u*1.2)*.48)*.64;
    float snowy_edge = max(smoothstep(-.65,1.30,bank),end_frost);
    vec3 ice = mix(vec3(.16,.42,.57),vec3(.47,.73,.82),cloud);
    ice = mix(ice,vec3(.06,.21,.34),fissure*.83);
    ice = mix(ice,vec3(.76,.92,.97),fracture_rim*.62+fine);
    ice = mix(ice,vec3(.80,.88,.93),snowy_edge*.96);
    ALBEDO = mix(ice*vec3(.48,.70,.80),ice,smoothstep(.12,.7,ice_normal.y));
    ROUGHNESS = mix(.23,.83,snowy_edge);
    SPECULAR = .63;
}''')
    _write(ART / "river_bank.gdshader", '''shader_type spatial;
varying vec3 bank_position;
void vertex() { bank_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz; }
void fragment() {
    vec2 p=bank_position.xz;
    float wind=.5+.22*sin(p.x*.6+p.y*.82)+.18*sin(p.y*2.7-p.x*.47);
    float wet=1.0-smoothstep(-.31,-.08,bank_position.y);
    vec3 snow=mix(vec3(.63,.76,.85),vec3(.88,.93,.97),wind);
    ALBEDO=mix(snow,vec3(.27,.48,.59),wet*.63);
    ROUGHNESS=mix(.96,.47,wet);
    SPECULAR=.25;
}''')
    _write(ART / "river_bridge.gdshader", '''shader_type spatial;
varying vec3 plank_position;
varying vec3 plank_normal;
void vertex() {
    plank_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
    plank_normal=normalize(MODEL_NORMAL_MATRIX*NORMAL);
}
void fragment() {
    vec2 p=plank_position.xz;
    float grain=sin(p.x*1.8+sin(p.y*32.0)*1.1)*.5+.5;
    float board=fract(sin(floor(p.y/.56)*32.783)*417.28);
    vec3 wood=mix(vec3(.20,.17,.14),vec3(.38,.30,.21),board*.7+grain*.17);
    float edge_frost=smoothstep(4.8,7.9,abs(p.y));
    float streak=pow(.5+.5*sin(p.x*.47+p.y*7.9),9.0)*.3;
    float snow=clamp(edge_frost*.80+streak,0.0,.94)*smoothstep(.2,.85,plank_normal.y);
    ALBEDO=mix(wood,vec3(.80,.88,.93),snow);
    ROUGHNESS=.87;
    SPECULAR=.19;
}''')
    _write(ART / "river_stone.gdshader", '''shader_type spatial;
varying vec3 masonry_position;
varying vec3 masonry_normal;
void vertex() {
    masonry_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
    masonry_normal=normalize(MODEL_NORMAL_MATRIX*NORMAL);
}
void fragment() {
    float patch=.5+.25*sin(masonry_position.x*2.0+masonry_position.z*1.3);
    vec3 stone=mix(vec3(.22,.29,.33),vec3(.39,.47,.51),patch);
    float snow=smoothstep(.42,.81,masonry_normal.y);
    ALBEDO=mix(stone,vec3(.82,.89,.93),snow*.88);
    ROUGHNESS=.92;
    SPECULAR=.18;
}''')


def build():
    ART.mkdir(parents=True, exist_ok=True)
    _write_shaders()
    water = Mesh("river_water")
    banks = Mesh("river_banks")
    ice = Mesh("river_ice")
    timber = Mesh("river_bridge_wood")
    stone = Mesh("river_bridge_stone")
    for low, high in zip(Z_SAMPLES, Z_SAMPLES[1:]):
        crossing = crossing_at((low+high)*.5)
        if crossing:
            if crossing["kind"] == "ice":
                _sheet(ice, low, high, BANK_MARGIN, 0.0)
            continue
        _sheet(water, low, high, .04, -.35)
        for side in (-1, 1):
            _strip(banks, low, high, side, BANK_MARGIN, .5, 0.0, -.09)
            _strip(banks, low, high, side, .5, -.04, -.09, -.37)
            # A thin jagged ice shelf follows the bank and remains inside water collision.
            width = .45 + .22*math.sin((low+high)*1.7 + side*2.8)
            _strip(ice, low, high, side, -.03, -width, -.16, -.20)
    edge_rng = random.Random(583129)
    for crossing in CROSSINGS:
        if crossing["kind"] != "ice":
            continue
        for z, direction in ((crossing["z"]-8.0, -1.0), (crossing["z"]+8.0, 1.0)):
            _broken_frozen_edge(ice,z,direction,edge_rng)
    rng = random.Random(20930)
    for low, high in ((-71.0,-49.0),(-31.0,-9.0),(9.0,31.0),(49.0,71.0)):
        for _index in range(11):
            z = rng.uniform(low+1.0,high-1.0)
            radius = rng.uniform(.30,1.32)
            x = river_x(z)+rng.uniform(-1.0,1.0)*(river_half_width(z)-radius-.6)
            _floe(ice,rng,x,z,radius,rng.uniform(-.27,-.12))
    # Timber planks follow the two surveyed banks; their walkable tops are y=0.
    # The hidden underdeck seals plank seams without occupying any open water.
    for low, high in zip(Z_SAMPLES, Z_SAMPLES[1:]):
        if -8.0 <= low and high <= 8.0:
            _sheet(timber,low,high,.72,-.045)
    plank_count = 29
    for index in range(plank_count):
        low = -8.0+16.0*index/plank_count
        high = -8.0+16.0*(index+1)/plank_count
        _sheet(timber,low+.010,high-.010,.72,0.0)
    # Bridge rails sit beyond the clear 16-metre crossing, above blocked water.
    for side in (-1,1):
        z = side*8.22
        left = river_outer_bank_x(z,-1)
        right = river_outer_bank_x(z,1)
        timber.box(left,right,.68,.88,z-.10,z+.10)
        for index in range(8):
            x=left+(right-left)*index/7.0
            stone.box(x-.23,x+.23,-.24,.87,z-.24,z+.24)
            stone.box(x-.29,x+.29,.87,.98,z-.29,z+.29)
    for side in (-1,1):
        for low,high in zip(Z_SAMPLES,Z_SAMPLES[1:]):
            if -8.0 <= low and high <= 8.0:
                _strip(stone,low,high,side,BANK_MARGIN,.72,0.0,0.0)
    for mesh in (water,banks,ice,timber,stone):
        mesh.save()
    ext = []
    nodes = ['[node name="River" type="Node3D"]\nmetadata/crossing_depth = 16.0\nmetadata/water_surface_y = -0.35',
             '[node name="Surface" type="Node3D" parent="."]']
    resources = []
    for name,mesh_name,shader_name in (("OpenWater","river_water","river_water"),
                                      ("SnowBanks","river_banks","river_bank"),
                                      ("FrozenCrossingsAndFloes","river_ice","river_ice"),
                                      ("BridgeTimber","river_bridge_wood","river_bridge"),
                                      ("BridgeMasonry","river_bridge_stone","river_stone")):
        _write(ART/f"{mesh_name}.tres",f'''[gd_resource type="ShaderMaterial" load_steps=2 format=3]

[ext_resource type="Shader" path="res://assets/defense/{shader_name}.gdshader" id="shader"]

[resource]
shader = ExtResource("shader")''')
        ext.extend([f'[ext_resource type="ArrayMesh" path="res://assets/defense/{mesh_name}.obj" id="{name}Mesh"]',
                    f'[ext_resource type="Material" path="res://assets/defense/{mesh_name}.tres" id="{name}Material"]'])
        nodes.append(f'[node name="{name}" type="MeshInstance3D" parent="Surface"]\nmesh = ExtResource("{name}Mesh")\nmaterial_override = ExtResource("{name}Material")')
    nodes.append('[node name="WaterBarrier" type="StaticBody3D" parent="."]\ncollision_layer = 1\ncollision_mask = 0')
    for index,polygon in enumerate(WATER_POLYGONS):
        coords=[component for y in (-1.0,2.4) for x,z in polygon for component in (x,y,z)]
        resources.append(f'[sub_resource type="ConvexPolygonShape3D" id="Water{index:03d}"]\nmargin = 0.001\npoints = PackedVector3Array('+", ".join(f"{v:.6f}" for v in coords)+')')
        nodes.append(f'[node name="Reach{index:03d}" type="CollisionShape3D" parent="WaterBarrier"]\nshape = SubResource("Water{index:03d}")')
    nodes.append('[node name="Crossings" type="Node3D" parent="."]')
    for crossing in CROSSINGS:
        z=crossing["z"]
        x=river_x(z)
        name=crossing["name"]
        nodes.append(f'[node name="{name}" type="Marker3D" parent="Crossings"]\nposition = {_vector((x,0,z))}\nmetadata/width = 16.0\nmetadata/clear_width = 13.7\nmetadata/kind = "{crossing["kind"]}"')
        for side,label in ((-1,"West"),(1,"East")):
            endpoint=side*(river_half_width(z)+BANK_MARGIN+4.0)
            nodes.append(f'[node name="{label}" type="Marker3D" parent="Crossings/{name}"]\nposition = {_vector((endpoint,0,0))}')
    nodes.append('[node name="WaterChecks" type="Node3D" parent="."]')
    for name,z in (("FarNorth",-62.0),("NorthReach",-20.0),("SouthReach",20.0),("FarSouth",62.0)):
        nodes.append(f'[node name="{name}" type="Marker3D" parent="WaterChecks"]\nposition = {_vector((river_x(z),0,z))}')
    _write(ART/"river.tscn","\n\n".join([f'[gd_scene load_steps={1+len(ext)+len(resources)} format=3]',*ext,*resources,*nodes]))
    return {"scene":"res://assets/defense/river.tscn", "water_polygons":len(WATER_POLYGONS),
            "crossings":CROSSINGS,"triangles":sum(len(mesh.faces) for mesh in (water,banks,ice,timber,stone)),"draw_calls":5}


if __name__ == "__main__":
    print(build())
