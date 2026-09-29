extends SceneTree
## Authored terrain is checked through native paths, shape casts and real units.

var game: Node3D
var navigation: ConstructionNavigation
var river: Node3D
var checks: int = 0
var failures: Array[String] = []
var crossing_units: Array[BattleUnit] = []
var crossing_destinations: Array[Vector3] = []

func _initialize() -> void:
	Engine.max_fps = 60
	_run.call_deferred()

func check(value: bool, label: String) -> void:
	checks += 1
	print("PASS " if value else "FAIL ", label)
	if not value:
		failures.append(label)

func _load_battle() -> void:
	change_scene_to_file("res://scenes/defense/battle.tscn")
	await scene_changed
	game = current_scene
	game.camera_rig.edge_scroll = false
	while not game._match_ready:
		await process_frame
	# Base _ready still awaits two physics frames after setting _match_ready.
	# Let its initial navigation publication finish before freezing the fixture.
	for tick: int in 5:
		await physics_frame
		await process_frame
	game.set_physics_process(false)
	game.get_node("IncomeTimer").stop()
	game.get_node("EnemyTimer").stop()
	for unit: BattleUnit in get_nodes_in_group("units"):
		unit.stop()
		unit.set_physics_process(false)
		unit.navigation_agent.avoidance_enabled = false
		unit.attack_windup.stop()
	for building: BattleBuilding in get_nodes_in_group("buildings"):
		building.set_physics_process(false)
		building.production.set_physics_process(false)
	navigation = game.get_node("ConstructionNavigation")
	river = game.map_instance.get_node("Environment/River")
	for attempt: int in 300:
		await physics_frame
		if navigation.paths_ready():
			await physics_frame
			await physics_frame
			var headquarters: Vector3 = game.defended_headquarters.global_position
			var native_closest: Vector3 = NavigationServer3D.map_get_closest_point(game.get_world_3d().navigation_map, headquarters)
			var footprint: Vector3 = game.defended_headquarters.get_footprint_size()
			var carved: bool = not navigation.contains_walkable_point(headquarters) and native_closest.distance_to(headquarters) > minf(footprint.x, footprint.z) * 0.5
			check(carved, "published native navigation excludes the physical headquarters footprint")
			if not carved:
				print("DEFENSE_NAV_STARTUP_DIAG " + JSON.stringify({"iteration": NavigationServer3D.map_get_iteration_id(game.get_world_3d().navigation_map), "published_iteration": navigation._published_map_iteration, "compact_polygons": navigation.compact_polygon_count, "headquarters": str(headquarters), "native_closest": str(native_closest), "cache_walkable": navigation.contains_walkable_point(headquarters)}))
			return
	check(false, "expanded defense publishes native navigation")

func _path(from: Vector3, to: Vector3) -> PackedVector3Array:
	# Match the parameters used by the live PathBudget; the short map_get_path
	# helper's default search budget is insufficient for the expanded battlefield.
	var unit: BattleUnit = game.get_node("Units").get_child(0)
	var query := NavigationPathQueryParameters3D.new()
	var result := NavigationPathQueryResult3D.new()
	query.map = unit.navigation_agent.get_navigation_map()
	query.start_position = from
	query.target_position = to
	query.navigation_layers = unit.navigation_agent.navigation_layers
	query.path_search_max_polygons = unit.navigation_agent.path_search_max_polygons
	query.metadata_flags = unit.navigation_agent.path_metadata_flags
	NavigationServer3D.query_path(query, result)
	return result.path

func _path_summary(path: PackedVector3Array, destination: Vector3) -> Dictionary:
	return {"size": path.size(), "end": str(path[-1]) if not path.is_empty() else "empty", "end_distance": path[-1].distance_to(destination) if not path.is_empty() else -1.0}

func _hit_names(hits: Array[Dictionary]) -> Array[String]:
	var names: Array[String] = []
	for hit: Dictionary in hits:
		names.append(str(hit.collider.get_path()))
	return names

func _reaches(path: PackedVector3Array, destination: Vector3, tolerance: float = 0.3) -> bool:
	return path.size() >= 2 and path[-1].distance_to(destination) < tolerance

func _clear_for_unit(path: PackedVector3Array, unit: BattleUnit) -> bool:
	# Sweep the unit's real native body, excluding other movable units. A nav
	# route that cuts a river wall, tree trunk or cliff cannot pass this check.
	if path.size() < 2:
		return false
	var collision: CollisionShape3D = unit.get_node("CollisionShape3D")
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = collision.shape
	query.collision_mask = 1 | 2 | 128
	var offset: Vector3 = collision.position + Vector3.UP * 0.05
	var space: PhysicsDirectSpaceState3D = game.get_world_3d().direct_space_state
	for index: int in range(path.size() - 1):
		query.transform.origin = path[index] + offset
		query.motion = Vector3.ZERO
		var initial_hits: Array[Dictionary] = space.intersect_shape(query, 8)
		if not initial_hits.is_empty():
			print("DEFENSE_TERRAIN_COLLISION_DIAG " + JSON.stringify({"kind": "initial_overlap", "unit": unit.unit_type, "segment": index, "from": str(path[index]), "to": str(path[index + 1]), "path_size": path.size(), "path_end": str(path[-1]), "colliders": _hit_names(initial_hits)}))
			return false
		query.motion = path[index + 1] - path[index]
		var sweep: PackedFloat32Array = space.cast_motion(query)
		if sweep[0] < 0.999:
			var motion: Vector3 = query.motion
			var contact_sample: Vector3 = query.transform.origin + motion * minf(1.0, sweep[1] + 0.005 / maxf(0.001, motion.length()))
			query.transform.origin = contact_sample
			query.motion = Vector3.ZERO
			query.margin = 0.02
			var contact_hits: Array[Dictionary] = space.intersect_shape(query, 8)
			print("DEFENSE_TERRAIN_COLLISION_DIAG " + JSON.stringify({"kind": "sweep", "unit": unit.unit_type, "segment": index, "from": str(path[index]), "to": str(path[index + 1]), "path_size": path.size(), "path_end": str(path[-1]), "safe_fraction": sweep[0], "unsafe_fraction": sweep[1], "contact_sample": str(contact_sample), "colliders": _hit_names(contact_hits)}))
			return false
	return true

func _water_is_blocked() -> void:
	var water_checks: Array[Node] = river.get_node("WaterChecks").get_children()
	check(water_checks.size() >= 4, "river authors water samples between and beyond the three crossings")
	var scout: BattleUnit = game.owned_entities(0, "units").filter(func(unit: BattleUnit): return unit.unit_type == "archer")[0]
	var scout_origin: Vector3 = scout.global_position
	var fog: FogOfWar = game.get_node("FogOfWar")
	var query := PhysicsShapeQueryParameters3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = 0.3
	query.shape = sphere
	query.collision_mask = 1
	for marker: Marker3D in water_checks:
		var at: Vector3 = marker.global_position
		var nearest: Vector3 = NavigationServer3D.map_get_closest_point(game.get_world_3d().navigation_map, at)
		var separated: float = Vector2(nearest.x - at.x, nearest.z - at.z).length()
		check(not navigation.contains_walkable_point(at) and separated > 1.5, String(marker.name) + " open water is absent from native navigation")
		query.transform.origin = at + Vector3.UP * 0.8
		var hits: Array[Dictionary] = game.get_world_3d().direct_space_state.intersect_shape(query, 8)
		check(hits.any(func(hit: Dictionary): return river.is_ancestor_of(hit.collider)), String(marker.name) + " water has a real river collision barrier")
		# Use a real allied source on the bank to reveal the point, so fog cannot
		# accidentally satisfy the rejection. The source is outside the building
		# footprint; the expected refusal is specifically the physical obstruction.
		scout.global_position = nearest
		fog.tick(FogOfWar.UPDATE_SECONDS)
		var refusal: String = game.placement_error(at, 0, "barracks")
		check(game.can_see_position(0, at) and refusal == "这里有单位或障碍物", String(marker.name) + " visible open water rejects a paid barracks due to its physical barrier")
	scout.global_position = scout_origin
	fog.tick(FogOfWar.UPDATE_SECONDS)

func _crossing_routes() -> void:
	var crossings: Array[Node] = river.get_node("Crossings").get_children()
	check(crossings.size() == 3, "river has three authored crossing locations")
	for crossing: Marker3D in crossings:
		var west: Vector3 = crossing.get_node("West").global_position
		var east: Vector3 = crossing.get_node("East").global_position
		var path: PackedVector3Array = _path(west, east)
		var label: String = String(crossing.name)
		check(_reaches(path, east), label + " connects both banks with a complete native path")
		var center_distance: float = INF
		for index: int in range(path.size() - 1):
			center_distance = minf(center_distance, crossing.global_position.distance_to(Geometry3D.get_closest_point_to_segment(crossing.global_position, path[index], path[index + 1])))
		check(center_distance < 3.0, label + " native route uses its own crossing instead of a distant detour")
		var unit: BattleUnit = game.spawn_unit("war_elephant", 0, west)
		unit.set_physics_process(false)
		crossing_units.append(unit)
		crossing_destinations.append(east)
		check(_clear_for_unit(path, unit), label + " full crossing clears the real war-elephant collision body")
		var return_path: PackedVector3Array = _path(east, west)
		check(_reaches(return_path, west) and _clear_for_unit(return_path, unit), label + " also permits a large body to cross in reverse")
	# A diagonal route between separate lanes must still go around solid water.
	var north: Marker3D = river.get_node("Crossings/North")
	var south: Marker3D = river.get_node("Crossings/South")
	var destination: Vector3 = south.get_node("East").global_position
	var diagonal: PackedVector3Array = _path(north.get_node("West").global_position, destination)
	check(_reaches(diagonal, destination) and _clear_for_unit(diagonal, crossing_units[0]), "cross-lane native route reaches the opposite bank without cutting across blocked water")

func _interior_landforms() -> void:
	var interior: Node3D = game.map_instance.get_node("Environment/InteriorTerrain")
	var elevated: int = 0
	for body: StaticBody3D in interior.get_children():
		var at: Vector3 = body.global_position
		var ray := PhysicsRayQueryParameters3D.create(at + Vector3.UP * 60.0, at - Vector3.UP * 2.0, 1)
		var hit: Dictionary = game.get_world_3d().direct_space_state.intersect_ray(ray)
		if not hit.is_empty() and hit.collider == body and hit.position.y > 1.0:
			if absf(at.x) < game.map_size.x * 0.5 - 20.0 and absf(at.z) < game.map_size.y * 0.5 - 14.0:
				elevated += 1
	check(elevated >= 4, "at least four interior landforms have real raised terrain collisions above the snow plain")
	var groves: Node3D = game.map_instance.get_node("Environment/PineGroves")
	var trees: Node3D = game.map_instance.get_node("Environment/PineCollisions")
	var batches: Array[Node] = groves.find_children("*", "MultiMeshInstance3D", true, false)
	check(groves.get_child_count() >= 4 and batches.size() >= 12 and trees.get_child_count() >= 60, "snowfield contains several sizeable groves with authored tree batches and physical trunks")
	var interior_trees: int = 0
	var sampled_collisions: int = 0
	for body: StaticBody3D in trees.get_children():
		var at: Vector3 = body.global_position
		if absf(at.x) >= game.map_size.x * 0.5 - 20.0 or absf(at.z) >= game.map_size.y * 0.5 - 14.0:
			continue
		interior_trees += 1
		if sampled_collisions >= 3:
			continue
		var ray := PhysicsRayQueryParameters3D.create(at + Vector3.UP * 8.0, at - Vector3.UP, 1)
		var hit: Dictionary = game.get_world_3d().direct_space_state.intersect_ray(ray)
		check(not hit.is_empty() and hit.collider == body and not navigation.contains_walkable_point(at), "interior tree sample %d has a physical trunk excluded from walking paths" % sampled_collisions)
		sampled_collisions += 1
	check(interior_trees >= 24, "forest patches extend into the playable interior instead of only lining the map edge")

func _mine_access() -> void:
	var worker: BattleUnit = game.owned_entities(0, "units").filter(func(unit: BattleUnit): return unit.unit_type == "farmer")[0]
	var exit: Vector3 = game.find_recruit_position("farmer", game.defended_headquarters)
	check(exit.is_finite(), "expanded headquarters has a usable worker exit")
	if not exit.is_finite():
		return
	var mines: Array[Node] = get_nodes_in_group("resource_veins")
	check(mines.size() >= 6, "expanded field retains multiple protected and expansion mines")
	for mine: ResourceVein in mines:
		var reachable: int = 0
		var slots: Array[Node] = mine.get_node("GatherSlots").get_children()
		for slot: Marker3D in slots:
			var path: PackedVector3Array = _path(exit, slot.global_position)
			if not _reaches(path, slot.global_position, ResourceVein.MAX_CONTACT_APPROACH):
				print("DEFENSE_MINE_DIAG " + JSON.stringify({"mine": str(mine.name), "slot": str(slot.name), "target": str(slot.global_position), "reason": "native_path_stops_short", "path": _path_summary(path, slot.global_position)}))
				continue
			# Workers may take the existing short collision-safe final approach
			# outside the shared military navigation clearance around the mine.
			path.append(slot.global_position)
			if _clear_for_unit(path, worker):
				reachable += 1
			else:
				print("DEFENSE_MINE_DIAG " + JSON.stringify({"mine": str(mine.name), "slot": str(slot.name), "target": str(slot.global_position), "reason": "static_collision", "path": _path_summary(path, slot.global_position)}))
		check(reachable == slots.size(), String(mine.name) + " all gathering slots have collision-safe paths from the player base")

func _move_large_units() -> void:
	for index: int in crossing_units.size():
		crossing_units[index].set_physics_process(true)
		crossing_units[index].issue_move(crossing_destinations[index])
	for tick: int in 600:
		var arrived: bool = true
		for index: int in crossing_units.size():
			arrived = arrived and crossing_units[index].global_position.distance_to(crossing_destinations[index]) < 1.7
		if arrived:
			break
		await physics_frame
		await process_frame
	for index: int in crossing_units.size():
		check(crossing_units[index].global_position.distance_to(crossing_destinations[index]) < 1.7, "real war elephant traverses crossing %d using normal path following" % index)
		crossing_units[index].stop()
		crossing_units[index].set_physics_process(false)
		crossing_units[index].navigation_agent.avoidance_enabled = false

func _run() -> void:
	create_timer(75.0, true, false, true).timeout.connect(func(): push_error("DEFENSE_TERRAIN deadline"); quit(3))
	await _load_battle()
	check(game.map_size.x * game.map_size.y > 2.0 * 160.0 * 96.0, "new snowfield area exceeds twice the original defense field")
	check(game.defended_headquarters.global_position.distance_to(game.get_spawn_marker(0).global_position) < 0.1 and game.defended_headquarters.position.x < -90.0, "expanded player headquarters uses the authored far-west deployment")
	_water_is_blocked()
	_crossing_routes()
	_interior_landforms()
	_mine_access()
	await _move_large_units()
	check(game.wave_index == 0 and not game.finished, "terrain probes leave defense preparation and objectives intact")
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	print("DEFENSE_TERRAIN_RESULTS " + JSON.stringify({"checks": checks, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
