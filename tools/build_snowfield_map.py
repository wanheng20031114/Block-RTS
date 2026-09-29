"""Author the editable snowfield defense map. No geometry is generated in play.

Uses only the Python standard library. Godot imports the tiny faceted OBJ meshes
as native ArrayMesh resources; every prop, collider, particle and marker is saved
in the scene. Navigation and physical scenery share the same convex footprints.

Godot references consulted before authoring:
https://docs.godotengine.org/en/stable/classes/class_primitivemesh.html
https://docs.godotengine.org/en/stable/classes/class_particleprocessmaterial.html
https://docs.godotengine.org/en/stable/classes/class_navigationregion3d.html
https://docs.godotengine.org/en/stable/classes/class_multimesh.html
https://docs.godotengine.org/en/stable/classes/class_multimeshinstance3d.html
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
WIDTH, DEPTH = 256, 144
HQ = (-106, 0)
MINES = [(-108, -24), (-106, 24), (-77, -41), (-73, 42), (-23, -20), (-23, 23), (37, -44), (35, 43)]
STARTING = [("Barracks", "barracks", -92, -10), ("Watchtower", "defense_tower", -84, 10)]
ENEMY = [
    ("NorthCastle", "castle", 108, -23, -1),
    ("SouthCastle", "castle", 108, 23, 1),
    ("NorthBarracks", "barracks", 96, -42, -1),
    ("InnerNorthBarracks", "barracks", 96, -14, 0),
    ("InnerSouthBarracks", "barracks", 96, 14, 0),
    ("SouthBarracks", "barracks", 96, 42, 1),
    ("NorthFactory", "factory", 110, -54, -1),
    ("SouthFactory", "factory", 110, 54, 1),
    ("NorthWatchtower", "defense_tower", 84, -53, -1),
    ("NorthGunTower", "cannon_tower", 84, -27, -1),
    ("CenterGunTower", "cannon_tower", 84, 0, 0),
    ("SouthGunTower", "cannon_tower", 84, 27, 1),
    ("SouthWatchtower", "defense_tower", 84, 53, 1),
]
# Streets remain broad; small rotations are deliberately avoided so the saved
# collision footprint and the visual roof eaves stay easy to inspect in-editor.
# Each tuple is (district, x, z, model suffix, yaw in degrees).
RESIDENCES = [
    ("Foregate",44,-7.7,"cottage",0), ("Foregate",55,-7.7,"townhouse",0),
    ("Foregate",65,-7.7,"cottage",0), ("Foregate",75,-7.7,"longhouse",0),
    ("Foregate",44,7.7,"cottage",180), ("Foregate",55,7.7,"longhouse",180),
    ("Foregate",65,7.7,"townhouse",180), ("Foregate",75,7.7,"cottage",180),
    ("WatchSquare",85,-15,"townhouse",0), ("WatchSquare",85,15,"townhouse",180),
    ("CastleWard",94,-28,"longhouse",90), ("CastleWard",94,28,"cottage",90),
    ("CastleWard",104,-32.5,"cottage",0), ("CastleWard",104,32.5,"townhouse",180),
    ("Market",105,-8.5,"townhouse",0), ("Market",116,-9.6,"cottage",0),
    ("Market",105,8.5,"longhouse",180), ("Market",116,9.6,"townhouse",180),
    ("EastWard",123,-21,"cottage",90), ("EastWard",123,-29.9,"townhouse",90),
    ("EastWard",123,21,"townhouse",90), ("EastWard",123,29.9,"longhouse",90),
    ("NorthWorkshop",87,-64,"cottage",0), ("NorthWorkshop",98,-66,"longhouse",0),
    ("NorthWorkshop",109,-66,"cottage",0), ("NorthWorkshop",120,-65,"townhouse",0),
    ("NorthWorkshop",120,-55,"cottage",90), ("NorthWorkshop",94,-54,"townhouse",90),
    ("SouthWorkshop",87,64,"longhouse",180), ("SouthWorkshop",98,66,"townhouse",180),
    ("SouthWorkshop",109,66,"cottage",180), ("SouthWorkshop",120,65,"longhouse",180),
    ("SouthWorkshop",120,55,"townhouse",90), ("SouthWorkshop",94,54,"cottage",90),
]
INTERIOR = [
    ("WestNorthBluff", -55, -22, (16, 7.4, 9.5), .10),
    ("WestSouthBluff", -50, 22, (18, 6.5, 9), -.08),
    ("EastNorthBluff", 57, -21, (17, 8.2, 8.5), -.09),
    ("EastSouthBluff", 52, 23, (15, 6.4, 10), .06),
    ("NorthWestFoothill", -92, -61, (20, 12, 14), .12),
    ("NorthRiverFoothill", -23, -64, (15, 14, 12), -.14),
    ("NorthEastFoothill", 58, -63, (21, 13, 14), .03),
    ("SouthWestFoothill", -93, 61, (19, 10, 13), -.09),
    ("SouthRiverFoothill", -27, 64, (17, 12, 12), .08),
    ("SouthEastFoothill", 58, 62, (19, 11, 13), -.12),
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


def segment_crosses_cell(a, b, x, z):
    """Clip the actual obstacle edge against the complete unit-cell square."""
    low,high=0.0,1.0
    for start,delta,minimum in [(a[0],b[0]-a[0],x),(a[1],b[1]-a[1],z)]:
        if delta == 0.0:
            if start < minimum or start > minimum+1:
                return False
            continue
        first,last=(minimum-start)/delta,(minimum+1-start)/delta
        low=max(low,min(first,last))
        high=min(high,max(first,last))
        if low > high:
            return False
    return True


def cell_touches_inflated_polygon(x, z, polygon, padding=1.15):
    """Reject every cell whose area is too close to the physical footprint.

    Native paths can use any point of a cell, including its edges and corners.
    For disjoint polygon/square edges their closest pair includes a vertex of
    at least one edge; checking both directions gives the exact 2D distance.
    Clipping plus containment also covers footprints intersecting the square.
    """
    if inside_inflated((x,z),polygon,padding=0.0):
        return True
    corners=((x,z),(x+1,z),(x+1,z+1),(x,z+1))
    clearance_squared=padding*padding
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if segment_crosses_cell(a,b,x,z):
            return True
        # Polygon vertex to the square (including its interior).
        dx=max(x-a[0],0.0,a[0]-(x+1))
        dz=max(z-a[1],0.0,a[1]-(z+1))
        if dx*dx+dz*dz < clearance_squared:
            return True
        # Square vertices to this polygon edge.
        ex,ez=b[0]-a[0],b[1]-a[1]
        denominator=ex*ex+ez*ez
        for cx,cz in corners:
            px,pz=cx-a[0],cz-a[1]
            t=max(0.0,min(1.0,(px*ex+pz*ez)/denominator))
            dx,dz=px-t*ex,pz-t*ez
            if dx*dx+dz*dz < clearance_squared:
                return True
    return False


def rectangle(x,z,width,depth,yaw=0.0):
    corners=[]
    for px,pz in [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]:
        corners.append((x+px*math.cos(yaw)+pz*math.sin(yaw),z-px*math.sin(yaw)+pz*math.cos(yaw)))
    return hull(corners)


def polygon_distance(a,b):
    """Shortest separation of two convex, static placement footprints."""
    if inside_inflated(a[0],b,0.0) or inside_inflated(b[0],a,0.0):
        return 0.0
    minimum=math.inf
    def signed(p,q,r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    for p,q in zip(a,a[1:]+a[:1]):
        for r,s in zip(b,b[1:]+b[:1]):
            if max(min(p[0],q[0]),min(r[0],s[0])) <= min(max(p[0],q[0]),max(r[0],s[0])) and max(min(p[1],q[1]),min(r[1],s[1])) <= min(max(p[1],q[1]),max(r[1],s[1])):
                if signed(p,q,r)*signed(p,q,s)<=0 and signed(r,s,p)*signed(r,s,q)<=0:
                    return 0.0
            for point,start,end in [(p,r,s),(q,r,s),(r,p,q),(s,p,q)]:
                dx,dz=end[0]-start[0],end[1]-start[1]
                px,pz=point[0]-start[0],point[1]-start[1]
                t=max(0,min(1,(px*dx+pz*dz)/(dx*dx+dz*dz)))
                minimum=min(minimum,(px-t*dx)**2+(pz-t*dz)**2)
    return math.sqrt(minimum)


def military_footprints():
    result=[]
    for name,kind,x,z,lane in ENEMY:
        source=(ROOT/f'data/buildings/{kind}.tres').read_text(encoding='utf-8')
        size=re.search(r'^size = Vector3\(([^)]+)\)',source,re.M)
        dimensions=[float(value) for value in size.group(1).split(',')] if size else [6,4,5]
        result.append((name,kind,x,z,dimensions[0],dimensions[2]))
    return result


def validate_town(polygons,river):
    houses=[]
    for i,(district,x,z,model,angle) in enumerate(RESIDENCES):
        roof=rectangle(x,z,6.4,5.9,math.radians(angle))
        assert max(abs(px) for px,pz in roof)<128 and max(abs(pz) for px,pz in roof)<71, f'House {i} outside town bounds'
        for j,solid in enumerate(polygons):
            assert polygon_distance(roof,solid)>.50, f'House {i} {district} ({x},{z}) overlaps scenery {j}'
        for name,kind,mx,mz,width,depth in military_footprints():
            clearance=polygon_distance(roof,rectangle(mx,mz,width,depth))
            assert clearance>1.4, f'House {i} too close to {name}: {clearance:.2f}m'
        for j,other in enumerate(houses):
            assert polygon_distance(roof,other)>2.4, f'Houses {i}/{j} need a wider lane'
        for entrance in (-40,0,40):
            assert not inside_inflated((119,entrance),roof,5), f'House {i} blocks an entrance'
        for name,kind,mx,mz,width,depth in military_footprints():
            if kind in ('barracks','factory'):
                assert not inside_inflated((mx-6,mz),roof,1.65), f'House {i} crowds producer exit {name}'
        assert not any(river.is_water_blocked(px,pz,1.15) for px,pz in roof), f'House {i} overlaps water'
        houses.append(roof)
    print(f'Town placement: {len(houses)} residential roof footprints clear terrain, military buildings, each other and wave entrances.')


def construction_cells(x,z,width,depth):
    """The existing ConstructionNavigation building-cell contract."""
    half_x,half_z=width*.5+1.15,depth*.5+1.15
    return {(cx,cz) for cx in range(math.floor(x-half_x),math.ceil(x+half_x))
            for cz in range(math.floor(z-half_z),math.ceil(z+half_z))
            if abs(cx+.5-x)<half_x and abs(cz+.5-z)<half_z}


def validate_occupied_town(source_cells):
    """Verify actual live-building carving without saving it into source nav."""
    footprints=[]
    for name,kind,x,z,width,depth in military_footprints():
        footprints.append(construction_cells(x,z,width,depth))
    for _,x,z,_,degrees in RESIDENCES:
        angle=math.radians(degrees)
        width=abs(math.cos(angle))*6+abs(math.sin(angle))*5.5
        depth=abs(math.sin(angle))*6+abs(math.cos(angle))*5.5
        footprints.append(construction_cells(x,z,width,depth))
    footprints.extend([construction_cells(-106,0,9,8),construction_cells(-92,-10,6,5),construction_cells(-84,10,4,4)])
    occupied=set().union(*footprints)
    open_cells=source_cells-occupied
    start=(-106,6)
    assert start in open_cells, 'Player base exit blocked by city changes'
    reached={start}
    pending=deque([start])
    while pending:
        x,z=pending.popleft()
        for cell in [(x-1,z),(x+1,z),(x,z-1),(x,z+1)]:
            if cell in open_cells and cell not in reached:
                reached.add(cell)
                pending.append(cell)
    for lane in (-40,0,40):
        for dz in range(-5,6):
            for dx in range(-5,6):
                if dx*dx+dz*dz<=25:
                    assert (119+dx,lane+dz) in reached, f'Active homes obstruct entrance cell {(119+dx,lane+dz)}'
        assert (42,lane) in reached, 'Active homes disconnect a main town approach'
    for name,kind,x,z,_,_ in military_footprints():
        if kind in ('barracks','factory'):
            assert (x-6,z) in reached, f'Active homes disconnect {name} deployment'
    for index,(_,x,z,_,_) in enumerate(RESIDENCES):
        local_cells={(cx,cz) for cx in range(math.floor(x)-7,math.ceil(x)+8) for cz in range(math.floor(z)-7,math.ceil(z)+8)}
        assert reached & local_cells, f'Residence {index} cannot be approached'
        freed=footprints[len(ENEMY)+index]&source_cells
        for j,other in enumerate(footprints):
            if j!=len(ENEMY)+index:
                freed-=other
        assert freed, f'Demolition of residence {index} would not reopen terrain'
    print('Town occupancy: all three approaches, all six production exits, 34 housing approaches and demolition footprints verified.')


def faceted_mesh(name, seed, rock=False, mesa=False):
    """Small flat-shaded, asymmetric solids with a shared collision hull."""
    rng = random.Random(seed)
    count = 10 if mesa else 9 if rock else 8
    levels = [(0,1),(.13,1.02),(.66,.69),(.92,.61)] if mesa else [(0, 1), (.34, .92), (.73, .60)] if rock else [(0, 1), (.30, .77), (.66, .38)]
    points = []
    for level, (height, radius) in enumerate(levels):
        for i in range(count):
            a = i*math.tau/count + .035*level
            r = radius*rng.uniform(.87, 1.12)
            points.append((math.cos(a)*r + .06*level, height + (rng.uniform(-.04,.04) if level else 0), math.sin(a)*r-.04*level))
    points.append((.13, .94 if mesa else 1, -.08))
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
float street(vec2 p, vec2 center, vec2 half_size) {
    vec2 beyond = abs(p-center)-half_size;
    return 1.0-smoothstep(-.15,.45,max(beyond.x,beyond.y));
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
    float spread = smoothstep(-108.0, -67.0, p.x);
    float flank = (40.0 + sin(p.x*.04)*2.4)*spread;
    float distance_to_road = min(abs(p.y), min(abs(p.y-flank), abs(p.y+flank)));
    float wear = 1.0-smoothstep(2.3, 5.2, distance_to_road+(detail-.5)*2.0);
    wear *= smoothstep(-119.0, -103.0, p.x);
    vec3 packed_snow = mix(vec3(.29,.43,.53), vec3(.48,.59,.66), detail);
    vec3 surface = mix(snow, packed_snow, wear*.59);
    // Exposed paving joins the residential fronts to the military courtyards.
    // It is part of the existing ground material, with no overlapping planes.
    float town = street(p,vec2(84.5,0),vec2(44.5,3.9));
    town = max(town,street(p,vec2(103,0),vec2(16,4.7)));
    town = max(town,street(p,vec2(103,-40),vec2(24,4.4)));
    town = max(town,street(p,vec2(103,40),vec2(24,4.4)));
    town = max(town,street(p,vec2(100,-54),vec2(4.5,6.0)));
    town = max(town,street(p,vec2(100,54),vec2(4.5,6.0)));
    town = max(town,street(p,vec2(119,-23),vec2(2.0,10.5)));
    town = max(town,street(p,vec2(119,23),vec2(2.0,10.5)));
    vec2 paving = vec2(p.x*.95 + mod(floor(p.y*.82),2.0)*.5,p.y*.82);
    vec2 joint = abs(fract(paving)-.5);
    float mortar = smoothstep(.43,.49,max(joint.x,joint.y));
    vec3 flagstones = mix(vec3(.39,.49,.54),vec3(.56,.64,.67),detail);
    flagstones = mix(flagstones,vec3(.64,.73,.77),mortar*.48);
    surface = mix(surface,flagstones,town*.70);
    ALBEDO = surface;
    ROUGHNESS = .94;
    SPECULAR = .15;
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
        '[sub_resource type="StandardMaterial3D" id="Snow"]\nalbedo_color = Color(0.77, 0.86, 0.90, 1)\nroughness = 0.95',
        '[sub_resource type="StandardMaterial3D" id="Needles"]\nalbedo_color = Color(0.075, 0.22, 0.23, 1)\nroughness = 0.95',
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
            resources.append(f'[sub_resource type="CylinderMesh" id="{name}"]\nmaterial = SubResource("{"Snow" if snowy else "Needles"}")\ntop_radius = 0.0\nbottom_radius = {radius*(.81 if snowy else 1):.4f}\nheight = {height*(.90 if snowy else 1):.4f}\nradial_segments = 7\nrings = 1')
            nodes.append(f'[node name="{name}" type="MeshInstance3D" parent="."]\nposition = Vector3({.025 if snowy else 0}, {y+(.21 if snowy else 0):.4f}, 0)\nrotation = Vector3(0, {index*.43:.4f}, 0)\nmesh = SubResource("{name}")')
    write(ART / "snow_pine.tscn", "\n\n".join([f'[gd_scene load_steps={len(resources)+1} format=3]', *resources, *nodes]))


def pine_meshes():
    """Share actual native mesh resources between the editor and static batches."""
    pieces = [("Trunk", .14, .23, 3.0, 1.5, 0.0, 0.0, (.26,.24,.22))]
    for index,(radius,height,y) in enumerate([(1.75,2.25,2.15),(1.38,2.18,3.30),(.98,1.95,4.38),(.58,1.7,5.35)]):
        pieces.append((f"Needles{index}",0,radius,height,y,index*.43,0,(.075,.22,.23)))
        pieces.append((f"Snow{index}",0,radius*.81,height*.90,y+.21,index*.43,.025,(.77,.86,.90)))
    for name,top,bottom,height,y,yaw,offset,color in pieces:
        write(ART/f"pine_{name.lower()}.tres", f'''[gd_resource type="CylinderMesh" load_steps=2 format=3]

[sub_resource type="StandardMaterial3D" id="Material"]
albedo_color = Color({color[0]}, {color[1]}, {color[2]}, 1)
roughness = 0.95

[resource]
material = SubResource("Material")
top_radius = {top}
bottom_radius = {bottom}
height = {height}
radial_segments = 7
rings = 1''')
    return pieces


def land_mesh(river):
    """Two river-bank strips share the river author's exact one-metre samples."""
    points, faces = [], []
    for z0,z1 in zip(river.Z_SAMPLES,river.Z_SAMPLES[1:]):
        for side in (-1,1):
            edge0,edge1=river.river_outer_bank_x(z0,side),river.river_outer_bank_x(z1,side)
            left0,right0=(-WIDTH/2,edge0) if side < 0 else (edge0,WIDTH/2)
            left1,right1=(-WIDTH/2,edge1) if side < 0 else (edge1,WIDTH/2)
            first=len(points)+1
            points.extend([(left0,-.005,z0),(right0,-.005,z0),(left1,-.005,z1),(right1,-.005,z1)])
            faces.extend([(first,first+2,first+1),(first+1,first+2,first+3)])
    text=['# River banks: shared samples, no opaque ground below the river.','o SnowfieldBanks']
    text.extend('v '+' '.join(f'{n:.6f}' for n in p) for p in points)
    text.append('vn 0 1 0')
    text.extend('f '+' '.join(f'{i}//1' for i in f) for f in faces)
    write(ART/'snowfield_banks.obj','\n'.join(text))


def add_forest_batches(tree_sites, pieces, ext, resources, nodes):
    cells={}
    for tree in tree_sites:
        x,z,_,_=tree
        key=(math.floor((x+WIDTH/2)/64),math.floor((z+DEPTH/2)/48))
        cells.setdefault(key,[]).append(tree)
    for name,*_ in pieces:
        ext.append(f'[ext_resource type="Mesh" path="res://assets/defense/pine_{name.lower()}.tres" id="Pine{name}"]')
    for (cx,cz),trees in sorted(cells.items()):
        group=f'Cell_{cx}_{cz}'
        nodes.append(f'[node name="{group}" type="Node3D" parent="Environment/PineGroves"]\nmetadata/tree_count = {len(trees)}')
        for name,top,bottom,height,y,yaw,offset,color in pieces:
            values=[]
            for x,z,s,a in trees:
                angle=a+yaw
                c,t=math.cos(angle)*s,math.sin(angle)*s
                ox=x+math.cos(a)*offset*s
                oz=z-math.sin(a)*offset*s
                # Native 3D MultiMesh buffer: three row-major vec4 rows.
                values.extend([c,0,t,ox,0,s,0,y*s,-t,0,c,oz])
            identifier=f'Forest_{cx}_{cz}_{name}'
            low_x=min(p[0]-p[2]*2 for p in trees)
            low_z=min(p[1]-p[2]*2 for p in trees)
            high_x=max(p[0]+p[2]*2 for p in trees)
            high_z=max(p[1]+p[2]*2 for p in trees)
            high_y=max(p[2]*7 for p in trees)
            resources.append(f'[sub_resource type="MultiMesh" id="{identifier}"]\ntransform_format = 1\ninstance_count = {len(trees)}\nmesh = ExtResource("Pine{name}")\ncustom_aabb = AABB({low_x:.4f}, 0, {low_z:.4f}, {high_x-low_x:.4f}, {high_y:.4f}, {high_z-low_z:.4f})\nbuffer = PackedFloat32Array('+', '.join(f'{n:.5f}' for n in values)+')')
            nodes.append(f'[node name="{name}" type="MultiMeshInstance3D" parent="Environment/PineGroves/{group}"]\nmultimesh = SubResource("{identifier}")')
    return len(cells)*len(pieces)


def author():
    import snowfield_river as river

    ART.mkdir(parents=True, exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    river.build()
    land_mesh(river)
    mountain_vertices = faceted_mesh("fractured_peak", 74)
    rock_vertices = faceted_mesh("glacial_boulder", 126, rock=True)
    mesa_vertices = faceted_mesh("terraced_bluff", 232, mesa=True)
    shaders()
    pine_scene()
    pieces=pine_meshes()
    ext = [
        '[ext_resource type="NavigationMesh" path="res://scenes/defense/snowfield_navigation.tres" id="Nav"]',
        '[ext_resource type="PackedScene" path="res://scenes/resource_vein.tscn" id="Mine"]',
        '[ext_resource type="PackedScene" path="res://assets/defense/river.tscn" id="River"]',
        '[ext_resource type="ArrayMesh" path="res://assets/defense/snowfield_banks.obj" id="Banks"]',
        '[ext_resource type="ArrayMesh" path="res://assets/defense/terraced_bluff.obj" id="Bluff"]',
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
        '[sub_resource type="PlaneMesh" id="OuterNorthSouthMesh"]\nmaterial = SubResource("SnowfieldMaterial")\nsize = Vector2(360, 52)',
        '[sub_resource type="PlaneMesh" id="OuterEastWestMesh"]\nmaterial = SubResource("SnowfieldMaterial")\nsize = Vector2(52, 144)',
        '[sub_resource type="BoxShape3D" id="Floor"]\nsize = Vector3(256, 1, 144)',
        '[sub_resource type="CylinderShape3D" id="PineTrunkShape"]\nradius = 0.23\nheight = 3.6\nmargin = 0.01',
        '[sub_resource type="SphereMesh" id="Snowdrift"]\nmaterial = SubResource("SnowMaterial")\nradius = 1.0\nheight = 2.0\nradial_segments = 12\nrings = 4',
        '[sub_resource type="StandardMaterial3D" id="FlakeMaterial"]\nshading_mode = 0\nalbedo_color = Color(0.84, 0.93, 1, 1)\nbillboard_mode = 1\ndisable_receive_shadows = true',
        '[sub_resource type="QuadMesh" id="FlakeMesh"]\nmaterial = SubResource("FlakeMaterial")\nsize = Vector2(0.065, 0.065)',
        '[sub_resource type="ParticleProcessMaterial" id="SnowProcess"]\nemission_shape = 3\nemission_box_extents = Vector3(127, 0, 71)\ndirection = Vector3(0.16, -1, 0.07)\nspread = 12.0\ninitial_velocity_min = 0.65\ninitial_velocity_max = 1.2\ngravity = Vector3(0.04, -0.07, 0.015)\nscale_min = 0.65\nscale_max = 1.5',
    ]
    nodes = [
        '[node name="SnowfieldMap" type="Node3D"]\nmetadata/map_id = "snowfield"\nmetadata/map_size = Vector2(256, 144)\nmetadata/map_title = "霜原守望"',
        '[node name="NavigationRegion3D" type="NavigationRegion3D" parent="."]\nnavigation_mesh = ExtResource("Nav")\nuse_edge_connections = false',
        '[node name="Environment" type="Node3D" parent="."]',
        '[node name="Ground" type="StaticBody3D" parent="Environment"]\ncollision_layer = 1\ncollision_mask = 0',
        '[node name="CollisionShape3D" type="CollisionShape3D" parent="Environment/Ground"]\nposition = Vector3(0, -0.5, 0)\nshape = SubResource("Floor")',
        '[node name="Snowfield" type="MeshInstance3D" parent="Environment/Ground"]\ncast_shadow = 0\nmesh = ExtResource("Banks")\nmaterial_override = SubResource("SnowfieldMaterial")',
        # Four adjoining strips leave a literal hole for the gameplay floor.
        # No close parallel ground planes remain for SSAO/SSIL to self-occlude.
        '[node name="NorthSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(0, -0.005, -98)\ncast_shadow = 0\nmesh = SubResource("OuterNorthSouthMesh")',
        '[node name="SouthSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(0, -0.005, 98)\ncast_shadow = 0\nmesh = SubResource("OuterNorthSouthMesh")',
        '[node name="WestSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(-154, -0.005, 0)\ncast_shadow = 0\nmesh = SubResource("OuterEastWestMesh")',
        '[node name="EastSnow" type="MeshInstance3D" parent="Environment"]\nposition = Vector3(154, -0.005, 0)\ncast_shadow = 0\nmesh = SubResource("OuterEastWestMesh")',
        '[node name="River" parent="Environment" instance=ExtResource("River")]',
        '[node name="MountainRing" type="Node3D" parent="Environment"]',
        '[node name="GlacialRocks" type="Node3D" parent="Environment"]',
        '[node name="PineGroves" type="Node3D" parent="Environment"]',
        '[node name="PineCollisions" type="Node3D" parent="Environment"]',
        '[node name="InteriorTerrain" type="Node3D" parent="Environment"]',
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
        for i, x in enumerate(range(-133, 139, 15)):
            mountains.append((x+RNG.uniform(-2.5,2.5), side*RNG.uniform(77,81), RNG.uniform(11,16), RNG.uniform(18,28) if side < 0 else RNG.uniform(11,19)))
        for i, z in enumerate(range(-54, 59, 17)):
            mountains.append((side*RNG.uniform(140,145), z+RNG.uniform(-2,2), RNG.uniform(11,15), RNG.uniform(17,27)))
    def ridge(name, x, z, scale, angle):
        # Keep every new mountain face beyond the original navigable bounds;
        # the most inward base vertex, not its centre, determines placement.
        footprint = [(p[0]*scale[0]*math.cos(angle)+p[2]*scale[2]*math.sin(angle), -p[0]*scale[0]*math.sin(angle)+p[2]*scale[2]*math.cos(angle)) for p in mountain_vertices]
        if abs(z) > 72:
            if z < 0:
                z = min(z, -72.2-max(p[1] for p in footprint))
            else:
                z = max(z, 72.2-min(p[1] for p in footprint))
        elif x < 0:
            x = min(x, -128.2-max(p[0] for p in footprint))
        else:
            x = max(x, 128.2-min(p[0] for p in footprint))
        solid(name, (x,-.05,z), scale, angle, mountain_vertices, "Mountain", "MountainMaterial", "MountainRing")

    for i, (x,z,r,h) in enumerate(mountains):
        a = RNG.uniform(0,math.tau)
        if abs(z) > 72:
            ridge(f"MiddleRidge{i:02d}", x, z+math.copysign(9,z), (r*1.52,h*1.12,r*.98), a*.035)
        else:
            ridge(f"MiddleRidge{i:02d}", x+math.copysign(4,x), z, (r,h*1.1,r*1.65), a*.035)
    range_rng = random.Random(73029)
    extra_ridges = 0
    for side in (-1,1):
        for i,x in enumerate(range(-141, 150, 21)):
            rear_height = range_rng.uniform(30,43) if side < 0 else range_rng.uniform(17,25)
            ridge(f"Rear{side}_{i}", x+range_rng.uniform(-5,5), side*range_rng.uniform(100,107), (range_rng.uniform(20,29),rear_height,range_rng.uniform(15,21)), range_rng.uniform(-.16,.16))
            extra_ridges += 1
        for i,x in enumerate(range(-125, 130, 14)):
            ridge(f"InnerSpur{side}_{i}", x+range_rng.uniform(-2,2), side*range_rng.uniform(76,80), (range_rng.uniform(11,16),range_rng.uniform(6,11),range_rng.uniform(5,8)), range_rng.uniform(-.15,.15))
            extra_ridges += 1
        for i,z in enumerate(range(-61, 66, 18)):
            ridge(f"SideRear{side}_{i}", side*range_rng.uniform(156,161), z+range_rng.uniform(-3,3), (range_rng.uniform(16,22),range_rng.uniform(24,34),range_rng.uniform(19,25)), range_rng.uniform(-.15,.15))
            extra_ridges += 1

    for name,x,z,scale,angle in INTERIOR:
        solid(name,(x,0,z),scale,angle,mesa_vertices,"Bluff","MountainMaterial","InteriorTerrain")

    # A few clusters at the edge supply terrain, while all three lanes stay wide.
    rock_sites = [(-122,-42),(-117,43),(-72,-23),(-69,25),(-38,-29),(-34,31),(41,-26),(36,24),(70,-28),(70,28),(-49,-63),(-49,62),(79,-68),(79,68)]
    for i, (x,z) in enumerate(rock_sites):
        for j in range(2 if i % 3 else 3):
            sx = RNG.uniform(1.1,2.3) if j else RNG.uniform(2.0,3.1)
            sz = sx*RNG.uniform(.70,1.05)
            solid(f"Boulder{i:02d}_{j}", (x+RNG.uniform(-2,2),0,z+RNG.uniform(-1,1)), (sx,RNG.uniform(1.4,3.0),sz), RNG.uniform(0,math.tau), rock_vertices, "Boulder", "BoulderMaterial", "GlacialRocks")

    validate_town(polygons,river)
    reserved = [(x,z,7.2) for x,z in MINES] + [(x,z,7.5) for _,_,x,z,_ in ENEMY]
    reserved += [(x,z,4.3) for _,x,z,_,_ in RESIDENCES]
    reserved += [(-106,0,21), (-92,-10,11), (-84,10,11)]
    tree_sites = []
    # Snow forests grow in irregular belts, with fully reserved broad valleys.
    # Dense tree clusters use native MultiMesh resources, not individual visuals.
    for z in range(-68,69,3):
        for x in range(-123,124,3):
            xx,zz=x+RNG.uniform(-.8,.8),z+RNG.uniform(-.8,.8)
            spread=max(0,min(1,(xx+108)/41))
            spread=spread*spread*(3-2*spread)
            flank=40*spread
            if min(abs(zz),abs(zz-flank),abs(zz+flank)) < 10:
                continue
            if abs(xx-river.river_x(zz)) < river.river_half_width(zz)+6:
                continue
            if any(math.hypot(xx-cx,zz-cz)<radius+2.0 for cx,cz,radius in reserved):
                continue
            forest=.53+.20*math.sin(xx*.073+zz*.10)+.17*math.cos(xx*.17-zz*.09)
            if RNG.random()>forest or any(inside_inflated((xx,zz),p,1.8) for p in polygons):
                continue
            tree_sites.append((xx,zz,RNG.uniform(.72,1.25),RNG.uniform(0,math.tau)))
    for i,(x,z,s,a) in enumerate(tree_sites):
        nodes.extend([f'[node name="Tree{i:03d}" type="StaticBody3D" parent="Environment/PineCollisions"]\nposition = Vector3({x:.5f}, 0, {z:.5f})\ncollision_layer = 1\ncollision_mask = 0',
                      f'[node name="Trunk" type="CollisionShape3D" parent="Environment/PineCollisions/Tree{i:03d}"]\nposition = Vector3(0, {1.8*s:.5f}, 0)\nscale = Vector3({s:.5f}, {s:.5f}, {s:.5f})\nshape = SubResource("PineTrunkShape")'])
        polygons.append([(x+.23*s*math.cos(a),z+.23*s*math.sin(a)) for a in [i*math.tau/16 for i in range(16)]])
    batch_count=add_forest_batches(tree_sites,pieces,ext,resources,nodes)

    # Shallow drifts under the framing groves are scenery, not invisible walls.
    for i,(x,z,_,_) in enumerate(tree_sites[::18]):
        nodes.append(f'[node name="Drift{i:02d}" type="MeshInstance3D" parent="Environment/SnowBanks"]\nposition = Vector3({x:.5f}, -0.24, {z:.5f})\nscale = Vector3({RNG.uniform(1.8,3.1):.4f}, 0.35, {RNG.uniform(1.0,1.8):.4f})\ncast_shadow = 0\nmesh = SubResource("Snowdrift")')

    nodes.extend([
        '[node name="Snowfall" type="GPUParticles3D" parent="Environment"]\nposition = Vector3(0, 16, 0)\ncast_shadow = 0\namount = 4000\nlifetime = 17.0\npreprocess = 17.0\nvisibility_aabb = AABB(-134, -20, -77, 270, 24, 158)\nprocess_material = SubResource("SnowProcess")\ndraw_pass_1 = SubResource("FlakeMesh")',
        '[node name="SpawnPoints" type="Node3D" parent="."]',
        '[node name="Player0" type="Marker3D" parent="SpawnPoints"]\nposition = Vector3(-106, 0, 0)\nrotation = Vector3(0, 1.570796, 0)\nmetadata/player_id = 0\nmetadata/alliance_id = 0\nmetadata/starting_tower_position = Vector3(-84, 0, 10)',
        '[node name="Player1" type="Marker3D" parent="SpawnPoints"]\nposition = Vector3(118, 0, 0)\nrotation = Vector3(0, -1.570796, 0)\nmetadata/player_id = 1\nmetadata/alliance_id = 1',
        '[node name="StartingBuildings" type="Node3D" parent="."]',
    ])
    for name,kind,x,z in STARTING:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="StartingBuildings"]\nposition = Vector3({x}, 0, {z})\nmetadata/kind = "{kind}"')
    nodes.append('[node name="StartingUnits" type="Node3D" parent="."]')
    for i in range(6):
        nodes.append(f'[node name="Farmer{i}" type="Marker3D" parent="StartingUnits"]\nposition = Vector3({-112+(i%3)*2}, 0, {-11-(i//3)*3})\nmetadata/kind = "farmer"')
    for i in range(6):
        kind="swordsman" if i < 4 else "archer"
        nodes.append(f'[node name="Guard{i}" type="Marker3D" parent="StartingUnits"]\nposition = Vector3({-85+(i%2)*2}, 0, {-4+(i//2)*2})\nmetadata/kind = "{kind}"')
    nodes.append('[node name="EnemyBuildings" type="Node3D" parent="."]')
    for name,kind,x,z,lane in ENEMY:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="EnemyBuildings"]\nposition = Vector3({x}, 0, {z})\nrotation = Vector3(0, -1.570796, 0)\nmetadata/kind = "{kind}"\nmetadata/lane = {lane}')
    for i,(district,x,z,model,angle) in enumerate(RESIDENCES):
        nodes.append(f'[node name="{district}Residence{i:02d}" type="Marker3D" parent="EnemyBuildings"]\nposition = Vector3({x}, 0, {z})\nrotation = Vector3(0, {math.radians(angle):.6f}, 0)\nmetadata/kind = "residence"\nmetadata/model = "residence_{model}"\nmetadata/district = "{district}"\nmetadata/lane = {0 if abs(z)<20 else -1 if z<0 else 1}')
    nodes.append('[node name="Entrances" type="Node3D" parent="."]')
    for name,lane in [("North",-1),("Center",0),("South",1)]:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="Entrances"]\nposition = Vector3(119, 0, {lane*40})\nmetadata/lane = {lane}')
    nodes.append('[node name="Resources" type="Node3D" parent="."]')
    ore_source = (ROOT / "assets/models/environment/gold_vein_collision.tres").read_text(encoding="utf-8")
    ore_flat = [float(v) for v in re.search(r"PackedVector3Array\((.*?)\)", ore_source).group(1).split(",")]
    ore_hull = hull([(ore_flat[i],ore_flat[i+2]) for i in range(0,len(ore_flat),3)])
    for i,(x,z) in enumerate(MINES):
        nodes.append(f'[node name="GoldVein{i}" parent="Resources" instance=ExtResource("Mine")]\nposition = Vector3({x}, 0, {z})')
        polygons.append([(x+px,z+pz) for px,pz in ore_hull])

    navigation(polygons,river)
    write(SCENES / "snowfield_map.tscn", "\n\n".join([f'[gd_scene load_steps={len(ext)+len(resources)+1} format=3]', *ext, *resources, *nodes]))
    write(ROOT / "data/defense/snowfield.tres", '''[gd_resource type="Resource" script_class="MapDefinition" load_steps=3 format=3]

[ext_resource type="Script" path="res://scripts/data/map_definition.gd" id="script"]
[ext_resource type="PackedScene" path="res://scenes/defense/snowfield_map.tscn" id="scene"]

[resource]
script = ExtResource("script")
id = &"snowfield"
display_name = "霜原守望"
size = Vector2(256, 144)
slots = 2
scene = ExtResource("scene")''')
    print(f"Authored snowfield: {len(mountains)+extra_ridges} layered ridge sections, {len(INTERIOR)} solid interior bluffs, {len(rock_sites)} boulder groups, {len(tree_sites)} pines in {batch_count} batches, 8 mines, 13 military buildings and {len(RESIDENCES)} homes.")


def navigation(polygons,river):
    # Water and scenery use one geometric rule. A cell-centre point test can
    # preserve unsafe corners even when the reported radius is large enough.
    solids=polygons+list(river.water_collision_polygons())
    bounds = [(min(x for x,z in p)-1.15, min(z for x,z in p)-1.15, max(x for x,z in p)+1.15, max(z for x,z in p)+1.15) for p in solids]
    walkable = set()
    for z in range(-DEPTH//2+2,DEPTH//2-2):
        for x in range(-WIDTH//2+2,WIDTH//2-2):
            if any(b[0]<=x+1 and x<=b[2] and b[1]<=z+1 and z<=b[3] and cell_touches_inflated_polygon(x,z,p) for p,b in zip(solids,bounds)):
                continue
            walkable.add((x,z))
    visited = {HQ}
    queue = deque(visited)
    assert HQ in walkable
    while queue:
        x,z = queue.popleft()
        for n in [(x-1,z),(x+1,z),(x,z-1),(x,z+1)]:
            if n in walkable and n not in visited:
                visited.add(n)
                queue.append(n)
    for z in [-40,0,40]:
        for dz in range(-5,6):
            for dx in range(-5,6):
                if dx*dx+dz*dz <= 25:
                    assert (119+dx,z+dz) in visited, "Reinforcement approach obstructed"
        crossing=int(river.river_x(z))
        assert (crossing,z) in visited, "Wide river crossing disconnected"
    for x,z in MINES:
        assert (x-5,z) in visited, "Expansion mine disconnected"
    for _,_,x,z,_ in ENEMY:
        assert (x-6,z) in visited, "Enemy deployment exit disconnected"
    validate_occupied_town(visited)
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
