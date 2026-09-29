shader_type spatial;
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
}
