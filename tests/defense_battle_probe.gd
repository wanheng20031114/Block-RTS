extends SceneTree
## Let enemies cross the whole battlefield, then defend with normal player orders.
var game: Node3D
var previous_positions: Dictionary = {}
var initial_guard_ids: Array[int] = []
var player_orders_sent: int = 0

func _unit_state(unit: BattleUnit) -> Dictionary:
	var budget: PathBudget = game.get_node("PathBudget")
	var path: PackedVector3Array = budget.current_path(unit)
	var target: Node3D = unit.target
	var movement: float = unit.global_position.distance_to(previous_positions[unit.entity_id]) if previous_positions.has(unit.entity_id) else -1.0
	previous_positions[unit.entity_id] = unit.global_position
	return {"id": unit.entity_id, "kind": unit.unit_type, "owner": unit.owner_id, "hp": unit.hp, "at": str(unit.global_position), "order": BattleUnit.Order.keys()[unit.order], "order_name": unit.order_name, "destination": str(unit.destination), "movement_since_sample": movement, "velocity": str(unit.velocity), "target_id": target.entity_id if is_instance_valid(target) else 0, "target_at": str(target.global_position) if is_instance_valid(target) else "none", "target_hp": target.hp if is_instance_valid(target) else 0.0, "in_range": unit._within_attack_range(target) if is_instance_valid(target) and target.alive else false, "path_size": path.size(), "path_end": str(path[-1]) if not path.is_empty() else "empty", "path_next": str(unit._navigation_route.next), "path_goal": str(budget.target_position(unit)), "path_pending": budget.has_pending(unit), "path_blocked": budget.is_blocked(unit), "path_finished": budget.is_finished(unit)}

func _sample(emit_log: bool = true) -> void:
	var enemies: Array[Dictionary] = []
	var guards: Array[Dictionary] = []
	for unit: BattleUnit in get_nodes_in_group("units"):
		if not unit.alive:
			continue
		if unit.owner_id == 1:
			enemies.append(_unit_state(unit))
		elif unit.unit_type != "farmer":
			guards.append(_unit_state(unit))
	if emit_log:
		print("DEFENSE_BATTLE_SAMPLE " + JSON.stringify({"elapsed": game.elapsed, "pending": game.pending_wave_units.size(), "remaining": game.wave_remaining, "enemies": enemies, "guards": guards}))

func _order_defenders() -> void:
	var guards: Array = game.owned_entities(0, "units").filter(func(unit: BattleUnit): return unit.entity_id in initial_guard_ids)
	var invaders: Array = game.owned_entities(1, "units").filter(func(unit: BattleUnit): return int(unit.get_meta("defense_wave", 0)) == 1 and unit.global_position.x < game.defended_headquarters.position.x + 30.0)
	if guards.is_empty() or invaders.is_empty():
		return
	# The mode is an RTS: a flanking attacker can sit outside idle guards' scan
	# ranges. Reposition the original army through the same validated player
	# command used by the UI, after enemies have already crossed the river.
	if player_orders_sent > 0 and guards.any(func(unit: BattleUnit): return is_instance_valid(unit.target) and unit.target.alive):
		return
	var at: Vector3 = invaders[0].global_position
	var command: Dictionary = {"kind": "move", "units": guards.map(func(unit: BattleUnit): return unit.entity_id), "at": [at.x, at.y, at.z], "attack_move": true}
	var response: Dictionary = game.command_bus.execute(command, 0)
	if response.ok:
		player_orders_sent += 1
	print("DEFENSE_BATTLE_PLAYER_ORDER " + JSON.stringify({"elapsed": game.elapsed, "guards": guards.size(), "at": str(at), "result": response}))

func _initialize() -> void:
	Engine.time_scale = 6.0
	Engine.physics_ticks_per_second = 180
	Engine.max_physics_steps_per_frame = 48
	_run.call_deferred()

func _run() -> void:
	create_timer(100.0, true, false, true).timeout.connect(func(): quit(3))
	change_scene_to_file("res://scenes/defense/battle.tscn")
	await scene_changed
	game = current_scene
	game.camera_rig.edge_scroll = false
	while not game._match_ready:
		await process_frame
	# Let base _ready and the initial building-carved map publish before removing
	# preparation time. No units are frozen or moved by the probe.
	for tick: int in 5:
		await physics_frame
		await process_frame
	var navigation: ConstructionNavigation = game.get_node("ConstructionNavigation")
	for tick: int in 300:
		if navigation.paths_ready():
			break
		await physics_frame
	await physics_frame
	await physics_frame
	var center: Vector3 = game.defended_headquarters.global_position
	var native_point: Vector3 = NavigationServer3D.map_get_closest_point(game.get_world_3d().navigation_map, center)
	print("DEFENSE_BATTLE_READY " + JSON.stringify({"elapsed": game.elapsed, "navigation_ready": navigation.paths_ready(), "compact_polygons": navigation.compact_polygon_count, "headquarters": str(center), "native_closest": str(native_point)}))
	for unit: BattleUnit in game.owned_entities(0, "units"):
		if unit.unit_type != "farmer":
			initial_guard_ids.append(unit.entity_id)
	game.preparation_remaining = 0.0
	var reached_west := false
	var attacks_observed := false
	var first_wave_finished := false
	var limit: float = game.elapsed + 150.0
	var sample_at: float = game.elapsed + 10.0
	var order_at: float = game.elapsed
	while game.elapsed < limit and not game.finished:
		for unit: BattleUnit in get_nodes_in_group("units"):
			if unit.owner_id == 1 and unit.position.x < game.defended_headquarters.position.x + 30.0:
				reached_west = true
			if unit.hp < unit.max_hp:
				attacks_observed = true
		if game.wave_index == 1 and not game.wave_active:
			first_wave_finished = true
			break
		if game.elapsed >= order_at:
			_order_defenders()
			order_at = game.elapsed + 5.0
		if game.elapsed >= sample_at:
			_sample(false)
			sample_at += 10.0
		await physics_frame
	if not first_wave_finished:
		_sample()
	var result := {"reached_west": reached_west, "combat_observed": attacks_observed,
		"first_wave_cleared": first_wave_finished, "elapsed": game.elapsed,
		"pending": game.pending_wave_units.size(), "remaining": game.wave_remaining,
		"base_hp": game.defended_headquarters.hp, "player_orders": player_orders_sent}
	print("DEFENSE_BATTLE_PROBE ", JSON.stringify(result))
	Engine.time_scale = 1.0
	Engine.physics_ticks_per_second = 30
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if reached_west and attacks_observed and first_wave_finished and result.base_hp > 0 else 1)
