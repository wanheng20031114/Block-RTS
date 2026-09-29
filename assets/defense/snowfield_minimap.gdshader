shader_type canvas_item;
render_mode unshaded;

#include "res://assets/defense/river_layout.gdshaderinc"

uniform vec3 unknown_color = vec3(0.11, 0.16, 0.22);
uniform vec3 explored_color = vec3(0.31, 0.42, 0.52);
uniform vec3 visible_color = vec3(0.66, 0.78, 0.85);

void fragment() {
	float state = texture(TEXTURE, UV).r * 255.0;
	vec2 point = (UV - vec2(0.5)) * vec2(256.0, 144.0);
	float river_distance = abs(point.x - snow_river_x(point.y));
	float river = 1.0 - smoothstep(snow_river_half_width(point.y) - 0.5, snow_river_half_width(point.y) + 0.5, river_distance);
	vec3 water = vec3(0.15, 0.36, 0.48);
	if (snow_river_crossing(point.y)) {
		water = abs(point.y) < 8.1 ? vec3(0.65, 0.62, 0.51) : vec3(0.50, 0.81, 0.87);
	}
	vec3 terrain = mix(visible_color, water, river);
	vec3 remembered = mix(explored_color, water * 0.65, river);
	COLOR = vec4(state > 1.5 ? terrain : (state > 0.5 ? remembered : unknown_color), 1.0);
}
