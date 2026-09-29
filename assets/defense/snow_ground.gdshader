shader_type spatial;
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
}
