// A single unwarped field defines the large shapes. Fine noise only breaks
// their outlines: the interiors are solid paint, never a sum of colour noise.
float meadow_edge_noise(vec2 p) {
	return texture(meadow_noise, p / 6.5 + vec2(0.41, 0.76)).r - 0.5;
}

vec3 painted_meadow(vec2 p, vec3 base, vec3 shade, vec3 sunlight) {
	// A 190 m repeat exceeds the playable map width. The texture's restrained
	// second octave bends contours without adding another layer of colour.
	vec2 uv = p / 190.0 + vec2(0.23, 0.17);
	float shape = texture(meadow_noise, uv).r;
	// Scale the fine noise by the field's world-space slope. A fixed colour
	// amplitude makes shallow parts of the field dissolve into speckled islands;
	// this instead limits the edge displacement to about a quarter metre.
	vec2 gradient = vec2(texture(meadow_noise, uv + vec2(0.25 / 190.0, 0.0)).r,
		texture(meadow_noise, uv + vec2(0.0, 0.25 / 190.0)).r) - vec2(shape);
	float contour = shape + meadow_edge_noise(p) * length(gradient) / 0.25 * 0.45;
	// One-pixel coverage rather than a metre-wide blur. Mipmaps and derivatives
	// keep the small edge notches stable at both tactical and close-up zooms.
	float aa = max(fwidth(contour) * 0.65, 0.001);
	vec3 color = mix(shade, base, smoothstep(0.38 - aa, 0.38 + aa, contour));
	return mix(color, sunlight, smoothstep(0.66 - aa, 0.66 + aa, contour));
}

float meadow_blade(vec2 p, vec2 a, vec2 b) {
	vec2 d = b - a;
	float along = clamp(dot(p - a, d) / dot(d, d), 0.0, 1.0);
	return length(p - a - d * along) - mix(0.035, 0.003, along);
}

// Sparse three-blade tufts. Each cell varies scale and orientation; no evenly
// repeated V stamps. Fade subpixel marks out before they shimmer when zooming.
float meadow_blades(vec2 p) {
	vec2 cell = floor(p / 1.65);
	vec2 seed = fract(sin(vec2(dot(cell, vec2(127.1, 311.7)),
		dot(cell, vec2(269.5, 183.3)))) * 43758.5453);
	vec2 q = (fract(p / 1.65) - 0.5) * 1.65 - (seed - 0.5) * 0.85;
	float angle = (seed.y - 0.5) * 1.4;
	q = mat2(vec2(cos(angle), -sin(angle)), vec2(sin(angle), cos(angle))) * q;
	q /= 0.8 + seed.y * 0.45;
	float blade = min(meadow_blade(q, vec2(0.0, 0.13), vec2(-0.12, -0.07)),
		meadow_blade(q, vec2(0.0, 0.13), vec2(0.14, -0.09)));
	blade = min(blade, meadow_blade(q, vec2(0.0, 0.13), vec2(0.015, -0.16)));
	float pixel = max(length(fwidth(p)), 0.005);
	return (1.0 - smoothstep(-pixel * 0.4, pixel * 0.4, blade))
		* step(0.80, seed.x) * (1.0 - smoothstep(0.09, 0.20, pixel));
}
