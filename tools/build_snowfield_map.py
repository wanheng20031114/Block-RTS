"""Author the editable snowfield defense map. No geometry is generated in play.

Uses only the Python standard library. Godot imports the tiny faceted OBJ meshes
as native ArrayMesh resources; every prop, collider, particle and marker is saved
in the scene. Navigation and physical scenery share the same convex footprints.

Godot references consulted before authoring:
https://docs.godotengine.org/en/stable/classes/class_primitivemesh.html
https://docs.godotengine.org/en/stable/classes/class_particleprocessmaterial.html
https://docs.godotengine.org/en/stable/classes/class_navigationregion3d.html
"""
from __future__ import annotations

import math
import random
import re
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/defense"
SCENES = ROOT / "scenes/defense"
RNG = random.Random(9202610)
MINES = [(-60, -17), (-58, 19), (-28, -22), (-22, 24), (12, -26), (22, 24)]
STARTING = [("Barracks", "barracks", -53, -7), ("Watchtower", "defense_tower", -49, 7)]
ENEMY = [
    ("NorthCastle", "castle", 63, -12, -1),
    ("SouthCastle", "castle", 63, 12, 1),
    ("NorthBarracks", "barracks", 53, -23, -1),
    ("InnerNorthBarracks", "barracks", 53, -8, 0),
    ("InnerSouthBarracks", "barracks", 53, 8, 0),
    ("SouthBarracks", "barracks", 53, 23, 1),
    ("NorthFactory", "factory", 64, -30, -1),
    ("SouthFactory", "factory", 64, 30, 1),
    ("NorthWatchtower", "defense_tower", 43, -30, -1),
    ("NorthGunTower", "cannon_tower", 43, -14, -1),
    ("CenterGunTower", "cannon_tower", 43, 0, 0),
    ("SouthGunTower", "cannon_tower", 43, 14, 1),
    ("SouthWatchtower", "defense_tower", 43, 30, 1),
]


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def vec(values):
    return "Vector3(" + ", ".join(f"{v:.5f}" for v in values) + ")"


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def hull(points):
    points = sorted(set(points))
    def turn(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    low, high = [], []
    for p in points:
        while len(low) >= 2 and turn(low[-2], low[-1], p) <= 0:
            low.pop()
        low.append(p)
    for p in reversed(points):
        while len(high) >= 2 and turn(high[-2], high[-1], p) <= 0:
            high.pop()
        high.append(p)
    return low[:-1] + high[:-1]


def inside_inflated(point, polygon, padding=1.15):
    inside = True
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dz = b[0] - a[0], b[1] - a[1]
        px, pz = point[0] - a[0], point[1] - a[1]
        if dx * pz - dz * px < 0:
            inside = False
        t = max(0.0, min(1.0, (px*dx+pz*dz)/(dx*dx+dz*dz)))
        if (px-t*dx)**2 + (pz-t*dz)**2 < padding**2:
            return True
    return inside


def faceted_mesh(name, seed, rock=False):
    """Small flat-shaded, asymmetric solids with a shared collision hull."""
    rng = random.Random(seed)
    count = 9 if rock else 8
    levels = [(0, 1), (.34, .92), (.73, .60)] if rock else [(0, 1), (.30, .77), (.66, .38)]
    points = []
    for level, (height, radius) in enumerate(levels):
        for i in range(count):
            a = i*math.tau/count + .035*level
            r = radius*rng.uniform(.87, 1.12)
            points.append((math.cos(a)*r + .06*level, height + (rng.uniform(-.04,.04) if level else 0), math.sin(a)*r-.04*level))
    points.append((.13, 1, -.08))
    faces = []
    for ring in range(len(levels)-1):
        for i in range(count):
            a, b = ring*count+i, ring*count+(i+1)%count
            c, d = a+count, b+count
            faces.extend([(a,c,b), (b,c,d)])
    for i in range(count):
        faces.append(((len(levels)-1)*count+i, len(points)-1, (len(levels)-1)*count+(i+1)%count))
    # Explicit per-face normals preserve the crisp hand-cut low-poly silhouette.
    text = [f"# Snowfield {name}: deterministic authored geometry", f"o {name}"]
    text.extend("v " + " ".join(f"{v:.6f}" for v in p) for p in points)
    for a, b, c in faces:
        u = tuple(points[b][j]-points[a][j] for j in range(3))
        v = tuple(points[c][j]-points[a][j] for j in range(3))
        normal = cross(u, v)
        length = math.sqrt(sum(n*n for n in normal))
        text.append("vn " + " ".join(f"{n/length:.6f}" for n in normal))
    for i, (a,b,c) in enumerate(faces, 1):
        text.append(f"f {a+1}//{i} {b+1}//{i} {c+1}//{i}")
    write(ART / f"{name}.obj", "\n".join(text))
    return points


def shaders():
    write(ART / "snow_ground.gdshader", '''shader_type spatial;
render_mode cull_back;
varying vec2 world_xz;
// Continuous crossing wind frequencies avoid any visible square noise lattice.
float wind(vec2 p) {
    return .5 + .20*sin(p.x*.91+p.y*.43) + .17*sin(-p.x*.53+p.y*.79+1.7) + .10*cos(p.x*1.37-p.y*1.13);
}
void vertex() { world_xz = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz; }
void fragment() {
    vec2 p = world_xz;
    float broad = wind(p * 0.085);
    float detail = wind(p * 0.83);
    float drift = sin(p.y * 2.7 + sin(p.x * .11) * 3.5 + broad * 4.0) * .5 + .5;
    vec3 snow = mix(vec3(.49,.62,.70), vec3(.77,.84,.88), broad * .75 + .10);
    snow += (detail-.5) * .022 + (drift-.5) * .012;
    // Three broad approach routes converge naturally at the western base.
    float spread = smoothstep(-62.0, -28.0, p.x);
    float flank = (18.0 + sin(p.x*.055)*2.4)*spread;
    float distance_to_road = min(abs(p.y), min(abs(p.y-flank), abs(p.y+flank)));
    float wear = 1.0-smoothstep(2.3, 5.2, distance_to_road+(detail-.5)*2.0);
    wear *= smoothstep(-72.0, -58.0, p.x);
    vec3 packed_snow = mix(vec3(.29,.43,.53), vec3(.48,.59,.66), detail);
    vec3 surface = mix(snow, packed_snow, wear*.59);
    // Flat frozen ponds remain traversable; the pale cracked edges read as ice.
    vec2 ice_a = (p-vec2(-5.0,29.0))/vec2(8.2,3.8);
    vec2 ice_b = (p-vec2(30.0,-30.0))/vec2(5.6,3.0);
    float pond = min(length(ice_a), length(ice_b)) + (wind(p*.56)-.5)*.12;
    float ice = 1.0-smoothstep(.85, 1.05, pond);
    float rim = (1.0-smoothstep(.92,1.11,pond))*smoothstep(.80,.94,pond);
    float crack = pow(1.0-abs(sin(p.x*.53+p.y*1.9+wind(p*.3)*1.8)), 31.0)*.09;
    vec3 frozen = mix(vec3(.31,.58,.70), vec3(.64,.79,.86), detail*.65) + crack;
    surface = mix(surface, frozen, ice*.87);
    ALBEDO = mix(surface, vec3(.9,.96,.98), rim*.6);
    ROUGHNESS = mix(.94,.36,ice);
    SPECULAR = mix(.15,.5,ice);
}''')
    write(ART / "snow_stone.gdshader", '''shader_type spatial;
varying vec3 local_position;
varying vec3 world_normal;
uniform float snow_height = .42;
void vertex() {
    local_position = VERTEX;
    world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}
void fragment() {
    vec3 face = normalize(world_normal);
    // Exposed steep faces stay dark. Snow descends the gentler, leeward
    // planes and narrow gullies instead of drawing a horizontal cap.
    float gully = sin(local_position.x*10.0+local_position.z*7.0+local_position.y*2.0)*.5+.5;
    float deposit = face.y*.80 + face.z*.13 - face.x*.065;
    deposit += local_position.y*.12 + gully*.045;
    float snow = smoothstep(snow_height+.08, snow_height+.16, deposit);
    float strata = sin(local_position.y*36.0+local_position.x*9.0)*.009;
    vec3 stone = mix(vec3(.19,.27,.34), vec3(.29,.39,.47), face.y*.5+.5) + strata;
    ALBEDO = mix(stone, vec3(.79,.87,.91), snow);
    ROUGHNESS = .94;
    SPECULAR = .14;
}''')


def pine_scene():
    resources = [
        '[sub_resource type="StandardMaterial3D" id="Snow"]\nalbedo_color = Color(0.83, 0.91, 0.95, 1)\nroughness = 0.95',
        '[sub_resource type="StandardMaterial3D" id="Needles"]\nalbedo_color = Color(0.09, 0.23, 0.24, 1)\nroughness = 0.93',
        '[sub_resource type="StandardMaterial3D" id="Bark"]\nalbedo_color = Color(0.26, 0.24, 0.22, 1)\nroughness = 1.0',
        '[sub_resource type="CylinderMesh" id="Trunk"]\nmaterial = SubResource("Bark")\ntop_radius = 0.14\nbottom_radius = 0.23\nheight = 3.0\nradial_segments = 6\nrings = 1',
        '[sub_resource type="CylinderShape3D" id="TrunkShape"]\nradius = 0.23\nheight = 3.6\nmargin = 0.01',
    ]
    nodes = ['[node name="SnowPine" type="StaticBody3D"]\ncollision_layer = 1\ncollision_mask = 0',
             '[node name="Trunk" type="MeshInstance3D" parent="."]\nposition = Vector3(0, 1.5, 0)\nmesh = SubResource("Trunk")',
             '[node name="CollisionShape3D" type="CollisionShape3D" parent="."]\nposition = Vector3(0, 1.8, 0)\nshape = SubResource("TrunkShape")']
    for index, (radius, height, y) in enumerate([(1.75,2.25,2.15), (1.38,2.18,3.30), (.98,1.95,4.38), (.58,1.7,5.35)]):
        for snowy in [False, True]:
            name = ("Snow" if snowy else "Needles") + str(index)
            resources.append(f'[sub_resource type="CylinderMesh" id="{name}"]\nmaterial = SubResource("{"Snow" if snowy else "Needles"}")\ntop_radius = 0.0\nbottom_radius = {radius*(.95 if snowy else 1):.4f}\nheight = {height:.4f}\nradial_segments = 7\nrings = 1')
            nodes.append(f'[node name="{name}" type="MeshInstance3D" parent="."]\nposition = Vector3({.025 if snowy else 0}, {y+(.14 if snowy else 0):.4f}, 0)\nrotation = Vector3(0, {index*.43:.4f}, 0)\nmesh = SubResource("{name}")')
    write(ART / "snow_pine.tscn", "\n\n".join([f'[gd_scene load_steps={len(resources)+1} format=3]', *resources, *nodes]))


def author():
    ART.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    mountain_vertices = faceted_mesh("fractured_peak", 74)
    rock_vertices = faceted_mesh("glacial_boulder", 126, rock=True)
    shaders()
    pine_scene()
    ext = [
        '[ext_resource type="NavigationMesh" path="res://scenes/defense/snowfield_navigation.tres" id="Nav"]',
        '[ext_resource type="PackedScene" path="res://scenes/resource_vein.tscn" id="Mine"]',
        '[ext_resource type="PackedScene" path="res://assets/defense/snow_pine.tscn" id="Pine"]',
        '[ext_resource type="ArrayMesh" path="res://assets/defense/fractured_peak.obj" id="Mountain"]',
        '[ext_resource type="ArrayMesh" path="res://assets/defense/glacial_boulder.obj" id="Boulder"]',
        '[ext_resource type="Shader" path="res://assets/defense/snow_ground.gdshader" id="GroundShader"]',
        '[ext_resource type="Shader" path="res://assets/defense/snow_stone.gdshader" id="StoneShader"]',
    ]
    resources = [
        '[sub_resource type="ShaderMaterial" id="SnowfieldMaterial"]\nshader = ExtResource("GroundShader")',
        '[sub_resource type="ShaderMaterial" id="MountainMaterial"]\nshader = ExtResource("StoneShader")\nshader_parameter/snow_height = 0.43',
        '[sub_resource type="ShaderMaterial" id="BoulderMaterial"]\nshader = ExtResource("StoneShader")\nshader_parameter/snow_height = 0.63',
        '[sub_resource type="StandardMaterial3D" id="SnowMaterial"]\nalbedo_color = Color(0.83, 0.90, 0.94, 1)\nroughness = 0.98',
        '[sub_resource type="PlaneMesh" id="GroundMesh"]\nmaterial = SubResource("SnowfieldMaterial")\nsize = Vector2(160, 96)\nsubdivide_width = 1\nsubdivide_depth = 1',
        '[sub_resource type="PlaneMesh" id="OuterNorthSouthMesh"]\nmaterial = SubResource("SnowfieldMaterial")\nsize = Vector2(260, 52)',
        '[sub_resource type="PlaneMesh" id="OuterEastWestMesh"]\nmaterial = SubResource("SnowfieldMaterial")\nsize = Vector2(50, 96)',
        '[sub_resource type="BoxShape3D" id="Floor"]\nsize = Vector3(160, 1, 96)',
        '[sub_resource type="SphereMesh" id="Snowdrift"]\nmaterial = SubResource("SnowMaterial")\nradius = 1.0\nheight = 2.0\nradial_segments = 12\nrings = 4',
        '[sub_resource type="StandardMaterial3D" id="FlakeMaterial"]\nshading_mode = 0\nalbedo_color = Color(0.84, 0.93, 1, 1)\nbillboard_mode = 1\ndisable_receive_shadows = true',
        '[sub_resource type="QuadMesh" id="FlakeMesh"]\nmaterial = SubResource("FlakeMaterial")\nsize = Vector2(0.065, 0.065)',
        '[sub_resource type="ParticleProcessMaterial" id="SnowProcess"]\nemission_shape = 3\nemission_box_extents = Vector3(79, 0, 47)\ndirection = Vector3(0.16, -1, 0.07)\nspread = 12.0\ninitial_velocity_min = 0.65\ninitial_velocity_max = 1.2\ngravity = Vector3(0.04, -0.07, 0.015)\nscale_min = 0.65\nscale_max = 1.5',
    ]
    nodes = [
        '[node name="SnowfieldMap" type="Node3D"]\nmetadata/map_id = "snowfield"\nmetadata/map_size = Vector2(160, 96)\nmetadata/map_title = "霜原守望"',
        '[node name="NavigationRegion3D" type="NavigationRegion3D" parent="."]\nnavigation_mesh = ExtResource("Nav")\nuse_edge_connections = false',
        '[node name="Environment" type="Node3D" parent="."]',
        '[node name="Ground" type="StaticBody3D" parent="Environment"]\ncollision_layer = 1\ncollision_mask = 0',
        '[node name="CollisionShape3D" type="CollisionShape3D" parent="Environment/Ground"]\nposition = Vector3(0, -0.5, 0)\nshape = SubResource("Floor")',
        '[node name="Snowfield" type="MeshInstance3D" parent="Environment/Ground"]\nposition = Vector3(0, -0.005, 0)\ncast_shadow = 0\nmesh = SubResource("GroundMesh")',
        # Four adjoining strips leave a literal hole for the gameplay floor.
        # No close parallel ground planes remain for SSAO/SSIL to self-occlude.
        '[node name="NorthSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(0, -0.005, -74)\ncast_shadow = 0\nmesh = SubResource("OuterNorthSouthMesh")',
        '[node name="SouthSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(0, -0.005, 74)\ncast_shadow = 0\nmesh = SubResource("OuterNorthSouthMesh")',
        '[node name="WestSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(-105, -0.005, 0)\ncast_shadow = 0\nmesh = SubResource("OuterEastWestMesh")',
        '[node name="EastSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(105, -0.005, 0)\ncast_shadow = 0\nmesh = SubResource("OuterEastWestMesh")',
        '[node name="MountainRing" type="Node3D" parent="Environment"]',
        '[node name="GlacialRocks" type="Node3D" parent="Environment"]',
        '[node name="PineGroves" type="Node3D" parent="Environment"]',
        '[node name="SnowBanks" type="Node3D" parent="Environment"]',
    ]
    polygons = []
    prop_count = 0

    def solid(name, at, scale, angle, vertices, mesh, material, parent):
        nonlocal prop_count
        transformed = []
        for x, y, z in vertices:
            xx, zz = x*scale[0], z*scale[2]
            transformed.append((xx*math.cos(angle)+zz*math.sin(angle), y*scale[1], -xx*math.sin(angle)+zz*math.cos(angle)))
        polygon = hull([(at[0]+p[0], at[2]+p[2]) for p in transformed])
        polygons.append(polygon)
        shape = f"Solid{prop_count}"
        resources.append(f'[sub_resource type="ConvexPolygonShape3D" id="{shape}"]\npoints = PackedVector3Array(' + ', '.join(f"{v:.5f}" for p in transformed for v in p) + ')\nmargin = 0.01')
        nodes.extend([
            f'[node name="{name}" type="StaticBody3D" parent="Environment/{parent}"]\nposition = {vec(at)}\ncollision_layer = 1\ncollision_mask = 0',
            f'[node name="Shape" type="CollisionShape3D" parent="Environment/{parent}/{name}"]\nshape = SubResource("{shape}")',
            f'[node name="Mesh" type="MeshInstance3D" parent="Environment/{parent}/{name}"]\nrotation = Vector3(0, {angle:.5f}, 0)\nscale = {vec(scale)}\nmesh = ExtResource("{mesh}")\nmaterial_override = SubResource("{material}")',
        ])
        prop_count += 1

    # Overlapping middle ridges, low inner spurs and a staggered high rear
    # skyline form a connected range rather than a row of isolated cones.
    mountains = []
    for side in (-1, 1):
        for i, x in enumerate(range(-84, 90, 15)):
            mountains.append((x+RNG.uniform(-2.5,2.5), side*RNG.uniform(51,55), RNG.uniform(8.5,12.0), RNG.uniform(10,18) if side < 0 else RNG.uniform(7,12)))
        for i, z in enumerate(range(-34, 39, 17)):
            mountains.append((side*RNG.uniform(90,93), z+RNG.uniform(-2,2), RNG.uniform(8.0,10.5), RNG.uniform(10,17)))
    def ridge(name, x, z, scale, angle):
        # Keep every new mountain face beyond the original navigable bounds;
        # the most inward base vertex, not its centre, determines placement.
        footprint = [(p[0]*scale[0]*math.cos(angle)+p[2]*scale[2]*math.sin(angle), -p[0]*scale[0]*math.sin(angle)+p[2]*scale[2]*math.cos(angle)) for p in mountain_vertices]
        if abs(z) > 47:
            if z < 0:
                z = min(z, -48.2-max(p[1] for p in footprint))
            else:
                z = max(z, 48.2-min(p[1] for p in footprint))
        elif x < 0:
            x = min(x, -80.2-max(p[0] for p in footprint))
        else:
            x = max(x, 80.2-min(p[0] for p in footprint))
        solid(name, (x,-.05,z), scale, angle, mountain_vertices, "Mountain", "MountainMaterial", "MountainRing")

    for i, (x,z,r,h) in enumerate(mountains):
        a = RNG.uniform(0,math.tau)
        if abs(z) > 47:
            ridge(f"MiddleRidge{i:02d}", x, z+math.copysign(9,z), (r*1.52,h*1.12,r*.98), a*.035)
        else:
            ridge(f"MiddleRidge{i:02d}", x+math.copysign(4,x), z, (r,h*1.1,r*1.65), a*.035)
    range_rng = random.Random(73029)
    extra_ridges = 0
    for side in (-1,1):
        for i,x in enumerate(range(-91, 99, 21)):
            rear_height = range_rng.uniform(21,34) if side < 0 else range_rng.uniform(11,17)
            ridge(f"Rear{side}_{i}", x+range_rng.uniform(-5,5), side*range_rng.uniform(72,77), (range_rng.uniform(18,24),rear_height,range_rng.uniform(12,16)), range_rng.uniform(-.16,.16))
            extra_ridges += 1
        for i,x in enumerate(range(-79, 83, 14)):
            ridge(f"InnerSpur{side}_{i}", x+range_rng.uniform(-2,2), side*range_rng.uniform(53,56), (range_rng.uniform(9,13),range_rng.uniform(4,7.5),range_rng.uniform(4,6)), range_rng.uniform(-.15,.15))
            extra_ridges += 1
        for i,z in enumerate(range(-37, 42, 18)):
            ridge(f"SideRear{side}_{i}", side*range_rng.uniform(107,111), z+range_rng.uniform(-3,3), (range_rng.uniform(13,17),range_rng.uniform(17,24),range_rng.uniform(14,19)), range_rng.uniform(-.15,.15))
            extra_ridges += 1

    # A few clusters at the edge supply terrain, while all three lanes stay wide.
    rock_sites = [(-70,-35),(-45,-38),(-15,-36),(9,-37),(31,-37),(-69,35),(-42,38),(-13,39),(13,36),(34,39)]
    for i, (x,z) in enumerate(rock_sites):
        for j in range(2 if i % 3 else 3):
            sx = RNG.uniform(1.1,2.3) if j else RNG.uniform(2.0,3.1)
            sz = sx*RNG.uniform(.70,1.05)
            solid(f"Boulder{i:02d}_{j}", (x+RNG.uniform(-2,2),0,z+RNG.uniform(-1,1)), (sx,RNG.uniform(1.4,3.0),sz), RNG.uniform(0,math.tau), rock_vertices, "Boulder", "BoulderMaterial", "GlacialRocks")

    reserved = [(x,z,6.5) for x,z in MINES] + [(x,z,6.0) for _,_,x,z,_ in ENEMY]
    reserved += [(-64,0,12), (-53,-7,8), (-49,7,8)]
    tree_sites = []
    for side in (-1,1):
        for x in range(-73, 74, 6):
            for row in range(2):
                xx, zz = x+RNG.uniform(-2,2), side*(37+row*5+RNG.uniform(-1,1))
                if any(math.hypot(xx-cx,zz-cz)<radius+1.9 for cx,cz,radius in reserved):
                    continue
                if any(inside_inflated((xx,zz),p,1.7) for p in polygons):
                    continue
                tree_sites.append((xx,zz,RNG.uniform(.66,1.17),RNG.uniform(0,math.tau)))
    for i,(x,z,s,a) in enumerate(tree_sites):
        nodes.append(f'[node name="SnowPine{i:03d}" parent="Environment/PineGroves" instance=ExtResource("Pine")]\nposition = Vector3({x:.5f}, 0, {z:.5f})\nrotation = Vector3(0, {a:.5f}, 0)\nscale = Vector3({s:.5f}, {s:.5f}, {s:.5f})')
        polygons.append([(x+.23*s*math.cos(a),z+.23*s*math.sin(a)) for a in [i*math.tau/16 for i in range(16)]])

    # Shallow drifts under the framing groves are scenery, not invisible walls.
    for i,(x,z,_,_) in enumerate(tree_sites[::3]):
        nodes.append(f'[node name="Drift{i:02d}" type="MeshInstance3D" parent="Environment/SnowBanks"]\nposition = Vector3({x:.5f}, -0.24, {z:.5f})\nscale = Vector3({RNG.uniform(1.8,3.1):.4f}, 0.35, {RNG.uniform(1.0,1.8):.4f})\ncast_shadow = 0\nmesh = SubResource("Snowdrift")')

    nodes.extend([
        '[node name="Snowfall" type="GPUParticles3D" parent="Environment"]\nposition = Vector3(0, 16, 0)\ncast_shadow = 0\namount = 1800\nlifetime = 17.0\npreprocess = 17.0\nvisibility_aabb = AABB(-86, -20, -52, 174, 24, 108)\nprocess_material = SubResource("SnowProcess")\ndraw_pass_1 = SubResource("FlakeMesh")',
        '[node name="SpawnPoints" type="Node3D" parent="."]',
        '[node name="Player0" type="Marker3D" parent="SpawnPoints"]\nposition = Vector3(-64, 0, 0)\nrotation = Vector3(0, 1.570796, 0)\nmetadata/player_id = 0\nmetadata/alliance_id = 0\nmetadata/starting_tower_position = Vector3(-49, 0, 7)',
        '[node name="Player1" type="Marker3D" parent="SpawnPoints"]\nposition = Vector3(70, 0, 0)\nrotation = Vector3(0, -1.570796, 0)\nmetadata/player_id = 1\nmetadata/alliance_id = 1',
        '[node name="StartingBuildings" type="Node3D" parent="."]',
    ])
    for name,kind,x,z in STARTING:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="StartingBuildings"]\nposition = Vector3({x}, 0, {z})\nmetadata/kind = "{kind}"')
    nodes.append('[node name="EnemyBuildings" type="Node3D" parent="."]')
    for name,kind,x,z,lane in ENEMY:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="EnemyBuildings"]\nposition = Vector3({x}, 0, {z})\nrotation = Vector3(0, -1.570796, 0)\nmetadata/kind = "{kind}"\nmetadata/lane = {lane}')
    nodes.append('[node name="Entrances" type="Node3D" parent="."]')
    for name,lane in [("North",-1),("Center",0),("South",1)]:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="Entrances"]\nposition = Vector3(72, 0, {lane*22})\nmetadata/lane = {lane}')
    nodes.append('[node name="Resources" type="Node3D" parent="."]')
    ore_source = (ROOT / "assets/models/environment/gold_vein_collision.tres").read_text(encoding="utf-8")
    ore_flat = [float(v) for v in re.search(r"PackedVector3Array\((.*?)\)", ore_source).group(1).split(",")]
    ore_hull = hull([(ore_flat[i],ore_flat[i+2]) for i in range(0,len(ore_flat),3)])
    for i,(x,z) in enumerate(MINES):
        nodes.append(f'[node name="GoldVein{i}" parent="Resources" instance=ExtResource("Mine")]\nposition = Vector3({x}, 0, {z})')
        polygons.append([(x+px,z+pz) for px,pz in ore_hull])

    navigation(polygons)
    write(SCENES / "snowfield_map.tscn", "\n\n".join([f'[gd_scene load_steps={len(ext)+len(resources)+1} format=3]', *ext, *resources, *nodes]))
    write(ROOT / "data/defense/snowfield.tres", '''[gd_resource type="Resource" script_class="MapDefinition" load_steps=3 format=3]

[ext_resource type="Script" path="res://scripts/data/map_definition.gd" id="script"]
[ext_resource type="PackedScene" path="res://scenes/defense/snowfield_map.tscn" id="scene"]

[resource]
script = ExtResource("script")
id = &"snowfield"
display_name = "霜原守望"
size = Vector2(160, 96)
slots = 2
scene = ExtResource("scene")''')
    print(f"Authored snowfield: {len(mountains)+extra_ridges} layered ridge sections, {len(rock_sites)} boulder groups, {len(tree_sites)} pines, 6 mines, 13 enemy buildings.")


def navigation(polygons):
    bounds = [(min(x for x,z in p)-1.15, min(z for x,z in p)-1.15, max(x for x,z in p)+1.15, max(z for x,z in p)+1.15) for p in polygons]
    walkable = set()
    for z in range(-46,46):
        for x in range(-78,78):
            px,pz=x+.5,z+.5
            if any(b[0]<=px<=b[2] and b[1]<=pz<=b[3] and inside_inflated((px,pz),p) for p,b in zip(polygons,bounds)):
                continue
            walkable.add((x,z))
    visited = {(-64,0)}
    queue = deque(visited)
    assert (-64,0) in walkable
    while queue:
        x,z = queue.popleft()
        for n in [(x-1,z),(x+1,z),(x,z-1),(x,z+1)]:
            if n in walkable and n not in visited:
                visited.add(n)
                queue.append(n)
    for z in [-22,0,22]:
        for dz in range(-5,6):
            for dx in range(-5,6):
                if dx*dx+dz*dz <= 25:
                    assert (72+dx,z+dz) in visited, "Reinforcement approach obstructed"
    for _,_,x,z,_ in ENEMY:
        assert (x-6,z) in visited, "Enemy deployment exit disconnected"
    vertices, ids, polygons_out = [], {}, []
    for x,z in sorted(visited,key=lambda p:(p[1],p[0])):
        indices=[]
        for p in [(x,z),(x,z+1),(x+1,z+1),(x+1,z)]:
            if p not in ids:
                ids[p]=len(vertices)
                vertices.append((p[0],0,p[1]))
            indices.append(ids[p])
        polygons_out.append(indices)
    flat = ", ".join(str(v) for p in vertices for v in p)
    faces = ", ".join("PackedInt32Array("+", ".join(str(v) for v in p)+")" for p in polygons_out)
    write(SCENES / "snowfield_navigation.tres", '[gd_resource type="NavigationMesh" format=3]\n\n[resource]\nvertices = PackedVector3Array('+flat+')\npolygons = Array[PackedInt32Array](['+faces+'])\nagent_radius = 1.15\nagent_height = 2.4\ncell_size = 1.0\ncell_height = 0.2')
    print(f"Navigation: {len(visited)} connected one-metre cells; all entrances and building exits connected.")


if __name__ == "__main__":
    author()
