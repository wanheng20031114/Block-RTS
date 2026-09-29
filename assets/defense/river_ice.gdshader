shader_type spatial;
render_mode cull_back;
#include "res://assets/defense/river_layout.gdshaderinc"
varying vec3 ice_position;
varying vec3 ice_normal;
void vertex() {
    ice_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    ice_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}
void fragment() {
    vec2 p = ice_position.xz;
    float cloud = .5+.22*sin(p.x*.41+p.y*.21)+.19*sin(p.y*.7-p.x*.23);
    float u = p.x-snow_river_x(p.y);
    float v = p.y-(p.y<0.0 ? -40.0 : 40.0);
    // A few branching stress fractures replace the uniform cellular web.
    float main_seam = abs(v-u*.27-.35*sin(u*1.70)-.10*sin(u*4.8));
    float branch_a = abs(u-v*1.75-1.6+.23*sin(v*3.1)+.09*sin(v*7.1));
    branch_a += (1.0-smoothstep(.4,1.1,v))*20.0;
    float branch_b = abs(v+u*.83+2.1+.22*sin(u*2.9));
    branch_b += smoothstep(-1.1,-.3,u)*20.0;
    float branch_c = abs(v-u*.41-4.7+.16*sin(u*3.3));
    branch_c += smoothstep(2.3,3.1,u)*20.0;
    float crack_distance = min(main_seam,min(branch_a,min(branch_b,branch_c)));
    float thickness = .014+.030*(.5+.5*sin(p.x*.77+p.y*.43));
    float fissure = 1.0-smoothstep(thickness,thickness+.028,crack_distance);
    float fracture_rim = (1.0-smoothstep(thickness+.035,thickness+.13,crack_distance))*(1.0-fissure);
    float fine = pow(1.0-abs(sin(p.x*.73+p.y*1.3+sin(p.y*.23)*2.5)),55.0)*.05;
    float bank = abs(u)-snow_river_half_width(p.y);
    float end_frost = smoothstep(6.5,8.8,abs(v)+sin(u*1.2)*.48)*.64;
    float snowy_edge = max(smoothstep(-.65,1.30,bank),end_frost);
    vec3 ice = mix(vec3(.16,.42,.57),vec3(.47,.73,.82),cloud);
    ice = mix(ice,vec3(.06,.21,.34),fissure*.83);
    ice = mix(ice,vec3(.76,.92,.97),fracture_rim*.62+fine);
    ice = mix(ice,vec3(.80,.88,.93),snowy_edge*.96);
    ALBEDO = mix(ice*vec3(.48,.70,.80),ice,smoothstep(.12,.7,ice_normal.y));
    ROUGHNESS = mix(.23,.83,snowy_edge);
    SPECULAR = .63;
}
