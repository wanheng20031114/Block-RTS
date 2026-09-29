shader_type spatial;
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
}
