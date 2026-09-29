extends SceneTree
## Enemy residences are destructible scenery, independent from economy and waves.

var game: Node3D
var navigation: ConstructionNavigation
var residences: Array[BattleBuilding] = []
var checks: int = 0
var failures: Array[String] = []

func _initialize() -> void:
	Engine.max_fps = 60
	_run.call_deferred()

func check(value: bool, label: String) -> void:
	checks += 1
	print("PASS " if value else "FAIL ", label)
	if not value:
		failures.append(label)

func _freeze_unit(unit: BattleUnit) -> void:
	unit.stop()
	unit.set_physics_process(false)
	unit.navigation_agent.avoidance_enabled = false
	unit.attack_windup.stop()

func _sync_navigation() -> void:
	for tick: int in 300:
		await physics_frame
		if navigation.paths_ready():
			await physics_frame
			await physics_frame
			return
	check(false, "residence footprint changes publish to native navigation")

func _load_battle() -> void:
	change_scene_to_file("res://scenes/defense/battle.tscn")
	await scene_changed
	game = current_scene
	game.camera_rig.edge_scroll = false
	while not game._match_ready:
		await process_frame
	for tick: int in 5:
		await physics_frame
		await process_frame
	game.set_physics_process(false)
	game.get_node("IncomeTimer").stop()
	game.get_node("EnemyTimer").stop()
	for unit: BattleUnit in get_nodes_in_group("units"):
		_freeze_unit(unit)
	for building: BattleBuilding in get_nodes_in_group("buildings"):
		building.set_physics_process(false)
		building.production.set_physics_process(false)
		if building.owner_id == 1 and building.building_type == "residence":
			residences.append(building)
	navigation = game.get_node("ConstructionNavigation")
	await _sync_navigation()

func _query_path(unit: BattleUnit, from: Vector3, to: Vector3) -> PackedVector3Array:
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

func _route_fits(unit: BattleUnit, path: PackedVector3Array) -> bool:
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
		if not space.intersect_shape(query, 1).is_empty():
			return false
		query.motion = path[index + 1] - path[index]
		if space.cast_motion(query)[0] < 0.999:
			return false
	return true

func _military_routes() -> void:
	var at: Vector3 = game.find_recruit_position("war_elephant", game.defended_headquarters)
	check(at.is_finite(), "route fixture has a native large-unit spawn point")
	if not at.is_finite():
		return
	var probe: BattleUnit = game.spawn_unit("war_elephant", 0, at)
	_freeze_unit(probe)
	var crossings: Array[Node] = game.map_instance.get_node("Environment/River/Crossings").get_children()
	for producer: BattleBuilding in game._living_producers():
		var kind: String = "war_elephant" if producer.building_type == "barracks" else "heavy_cannon"
		var start: Vector3 = game.find_recruit_position(kind, producer)
		var destination: Vector3 = crossings[0].get_node("East").global_position
		for crossing: Marker3D in crossings:
			var candidate: Vector3 = crossing.get_node("East").global_position
			if absf(candidate.z - producer.position.z) < absf(destination.z - producer.position.z):
				destination = candidate
		var path := _query_path(probe, start, destination) if start.is_finite() else PackedVector3Array()
		check(start.is_finite() and path.size() >= 2 and path[-1].distance_to(destination) < 0.3 and _route_fits(probe, path), "%s %d keeps a large-body route through the settlement to its eastern river approach" % [producer.building_type, producer.entity_id])

func _economy_and_menu() -> void:
	var enemy: PlayerState = game.get_player(1)
	var before_gold: int = enemy.gold
	var before_units: int = game.owned_entities(1, "units").size()
	var before_shots: int = game.get_node("ProjectilePool").launch_count
	for residence: BattleBuilding in residences:
		residence.production._physics_process(120.0)
		residence._physics_process(120.0)
	check(game.owned_entities(1, "units").size() == before_units and enemy.gold == before_gold and game.get_node("ProjectilePool").launch_count == before_shots, "idle residences neither recruit, generate gold nor fire weapons")
	check(not residences[0].production.recruit("swordsman").ok and enemy.gold == before_gold, "residence rejects military production without charging")
	check(enemy.military_supply == 0 and enemy.reserved_military_supply == 0 and enemy.get_supply_limit() == PlayerState.SUPPLY_LIMIT, "enemy residences grant no units, reservations or extra population capacity")
	var worker: BattleUnit = game.owned_entities(0, "units").filter(func(unit: BattleUnit): return unit.unit_type == "farmer")[0]
	game.select_entities([worker])
	game.hud.refresh()
	check(not game.hud._actions.any(func(action: Dictionary): return action.kind == "build" and action.id == "residence"), "residence never appears in the player's construction actions")
	var player_gold: int = game.get_player(0).gold
	var denied: Dictionary = game.command_bus.execute({"kind": "build", "building_type": "residence", "units": [worker.entity_id], "at": [0, 0, 0]}, 0)
	check(not denied.ok and denied.error == "无效建筑" and game.get_player(0).gold == player_gold, "normal player build command cannot purchase an enemy scenery residence")
	game._on_income()
	check(enemy.gold == before_gold + BalanceCatalog.ECONOMY.passive_gold_per_second, "residences do not multiply the existing match income tick")

func _damage_and_collapse(residence: BattleBuilding) -> void:
	var center: Vector3 = residence.global_position
	var sphere := SphereShape3D.new()
	sphere.radius = 0.35
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = sphere
	query.collision_mask = 2
	query.transform.origin = center + Vector3.UP
	var space: PhysicsDirectSpaceState3D = game.get_world_3d().direct_space_state
	check(space.intersect_shape(query, 8).any(func(hit: Dictionary): return hit.collider == residence) and not navigation.contains_walkable_point(center), "living residence occupies both native physics and walking space")
	var at: Vector3 = game.find_recruit_position("swordsman", residence)
	check(at.is_finite(), "residence has an accessible melee attack approach")
	if not at.is_finite():
		return
	var attacker: BattleUnit = game.spawn_unit("swordsman", 0, at)
	game.get_node("FogOfWar").tick(FogOfWar.UPDATE_SECONDS)
	game.select_entities([residence])
	game.hud.refresh()
	check(game.hud._selected_preview == "residence" and game.hud.selected_name.text == "住宅", "selecting a visible residence shows its name and dedicated native portrait")
	var attack: Dictionary = game.command_bus.execute({"kind": "attack", "units": [attacker.entity_id], "target": residence.entity_id}, 0)
	check(attack.ok, "visible residence accepts the normal player attack command")
	var before_hp: float = residence.hp
	for tick: int in 150:
		if residence.hp < before_hp:
			break
		await physics_frame
		await process_frame
	_freeze_unit(attacker)
	check(residence.alive and residence.hp > 0.0 and residence.hp < before_hp, "real sword attack removes residence HP through the normal combat pipeline")
	var deaths: Array[int] = [0]
	residence.died.connect(func(_entity: Node3D): deaths[0] += 1)
	residence.receive_damage(residence.hp, attacker)
	residence.receive_damage(residence.max_hp, attacker)
	await _sync_navigation()
	check(not residence.alive and residence.hp == 0.0 and deaths[0] == 1 and not residence.is_in_group("buildings"), "lethal damage destroys a residence exactly once and retires its building registration")
	check(residence.collision_layer == 0 and residence.get_node("CollisionShape3D").disabled and space.intersect_shape(query, 1).is_empty(), "destroyed residence releases its physical collision")
	var closest: Vector3 = NavigationServer3D.map_get_closest_point(game.get_world_3d().navigation_map, center)
	check(navigation.contains_walkable_point(center) and closest.distance_to(center) < 0.3, "demolition restores the residence footprint to published native walking space")
	await create_timer(1.4).timeout
	check(residence.get_node("Rubble").visible and not residence.model_pivot.visible and residence.model_pivot.scale.y < 0.1, "residence uses the native collapse animation and leaves visible rubble")

func _clear_wave() -> void:
	for step: int in 200:
		if not game.wave_active or game.finished:
			return
		game._advance_waves(1.0)
		for unit: BattleUnit in game.get_node("Units").get_children():
			if unit.alive and unit.owner_id == 1 and unit.has_meta("defense_wave"):
				unit.receive_damage(unit.hp)
		game.check_victory()
		await process_frame
	check(false, "residence wave fixture drains its real reinforcement queue")

func _wave_independence() -> void:
	var survivor: BattleBuilding = residences[-1]
	var player: PlayerState = game.get_player(0)
	var enemy: PlayerState = game.get_player(1)
	var player_gold: int = player.gold
	var enemy_gold: int = enemy.gold
	var supply_limit: int = enemy.get_supply_limit()
	for residence: BattleBuilding in residences:
		if residence.alive and residence != survivor:
			residence.receive_damage(residence.hp)
	await _sync_navigation()
	game.check_victory()
	await process_frame
	check(not game.finished and survivor.alive and game.wave_index == 0, "destroying the settlement does not bypass the ten-wave objective")
	check(player.gold == player_gold and enemy.gold == enemy_gold and enemy.get_supply_limit() == supply_limit, "residence losses grant no gold and remove no military population capacity")
	game._on_income()
	check(enemy.gold == enemy_gold + BalanceCatalog.ECONOMY.passive_gold_per_second, "income tick is unchanged after settlement demolition")
	check(game._living_producers().size() == 6 and game._initial_producers == 6, "only the four military barracks and two factories count as wave producers")
	game._start_wave()
	check(game.wave_index == 1 and game.wave_remaining == game.waves[0].roster().size(), "destroyed residences leave the full authored first-wave strength intact")
	await _clear_wave()
	for producer: BattleBuilding in game._living_producers():
		producer.receive_damage(producer.hp)
	await _sync_navigation()
	game.check_victory()
	await process_frame
	check(not game.finished, "removing military production and most homes still cannot win before wave ten")
	game.wave_index = 9
	game._start_wave()
	check(game.wave_index == 10 and game.wave_remaining == ceili(game.waves[9].roster().size() * 0.5), "six destroyed military producers still halve the final wave independently of residences")
	await _clear_wave()
	check(game.finished and game.battle_won and survivor.alive, "clearing the tenth wave wins while an enemy residence remains standing")

func _run() -> void:
	create_timer(60.0, true, false, true).timeout.connect(func(): push_error("DEFENSE_RESIDENCE deadline"); quit(3))
	await _load_battle()
	check(residences.size() >= 30 and residences.size() <= 40, "enemy settlement authors thirty to forty destructible residences")
	if residences.is_empty():
		await game.prepare_shutdown()
		quit(1)
		return
	var variants: Dictionary = {}
	var valid_models: bool = true
	var scenery_only: bool = true
	for residence: BattleBuilding in residences:
		var definition: BuildingDefinition = residence.get_combat_definition()
		variants[definition.model] = true
		valid_models = valid_models and residence._model.scene_file_path == BattleBuilding.MODELS[definition.model].resource_path
		scenery_only = scenery_only and residence.alive and residence.max_hp > 0.0 and definition.damage == 0.0 and definition.produces.is_empty()
	check(variants.size() == 3 and valid_models, "all three residence appearances instantiate their authored native model scenes")
	check(scenery_only, "each residence has real hit points and no weapons or recruitable units")
	_economy_and_menu()
	_military_routes()
	await _damage_and_collapse(residences[0])
	await _wave_independence()
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	print("DEFENSE_RESIDENCE_RESULTS " + JSON.stringify({"checks": checks, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
