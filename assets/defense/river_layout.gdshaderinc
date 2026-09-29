// Shared snowfield river layout, authored by tools/snowfield_river.py.
float snow_river_x(float z) {
    return 8.0 + 9.0 * sin(z * 0.045) + 3.0 * sin(z * 0.11);
}
float snow_river_half_width(float z) {
    return 7.5 + sin(z * 0.06 + 0.8);
}
bool snow_river_crossing(float z) {
    return abs(z + 40.0) <= 8.0 || abs(z) <= 8.0 || abs(z - 40.0) <= 8.0;
}
