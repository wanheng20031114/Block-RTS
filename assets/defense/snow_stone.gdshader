shader_type spatial;
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
}
