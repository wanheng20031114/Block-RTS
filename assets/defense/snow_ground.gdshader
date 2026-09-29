shader_type spatial;
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
}
