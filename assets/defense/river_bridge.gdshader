shader_type spatial;
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
}
