shader_type canvas_item;
render_mode unshaded;

uniform vec3 unknown_color = vec3(0.141176, 0.145098, 0.113725);
uniform vec3 explored_color = vec3(0.294118, 0.274510, 0.188235);
uniform vec3 visible_color = vec3(0.564706, 0.466667, 0.274510);

// Share the battlefield's R8 visibility texture. Terrain needs one quad,
// rather than thousands of CPU cell queries and CanvasItem draw commands.
void fragment() {
	float state = texture(TEXTURE, UV).r * 255.0;
	COLOR = vec4(state > 1.5 ? visible_color : (state > 0.5 ? explored_color : unknown_color), 1.0);
}
