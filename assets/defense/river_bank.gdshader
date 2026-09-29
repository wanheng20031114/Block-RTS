shader_type spatial;
varying vec3 bank_position;
void vertex() { bank_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz; }
void fragment() {
    vec2 p=bank_position.xz;
    float wind=.5+.22*sin(p.x*.6+p.y*.82)+.18*sin(p.y*2.7-p.x*.47);
    float wet=1.0-smoothstep(-.31,-.08,bank_position.y);
    vec3 snow=mix(vec3(.63,.76,.85),vec3(.88,.93,.97),wind);
    ALBEDO=mix(snow,vec3(.27,.48,.59),wet*.63);
    ROUGHNESS=mix(.96,.47,wet);
    SPECULAR=.25;
}
