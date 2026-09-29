extends SceneTree
## Real snowfield, paid economy, native pause and ten-wave victory contract.

var game: Node3D
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

func _load_battle() -> void:
	if is_instance_valid(game):
		await game.prepare_shutdown()
	paused = false
	change_scene_to_file("res://scenes/defense/battle.tscn")
	await scene_changed
	game = current_scene
	game.camera_rig.edge_scroll = false
	while not game._match_ready:
		await process_frame
	# Allow the derived scene's ready method and native navigation to finish.
	for tick: int in 5:
		await physics_frame
		await process_frame

func _freeze_simulation() -> void:
	game.set_physics_process(false)
	game.get_node("IncomeTimer").stop()
	game.get_node("EnemyTimer").stop()
	for unit: BattleUnit in get_nodes_in_group("units"):
		unit.set_physics_process(false)
		unit.navigation_agent.avoidance_enabled = false
		unit.attack_windup.stop()
	for building: BattleBuilding in get_nodes_in_group("buildings"):
		building.set_physics_process(false)
		building.production.set_physics_process(false)

func _sync_navigation() -> void:
	var navigation: ConstructionNavigation = game.get_node("ConstructionNavigation")
	for attempt: int in 240:
		await physics_frame
		if not navigation.is_rebuilding() and NavigationServer3D.map_get_iteration_id(game.get_world_3d().navigation_map) > 0:
			await physics_frame
			await physics_frame
			return
	check(false, "snowfield native navigation rebuild completes")

func _path_reaches_headquarters(from: Vector3) -> bool:
	# The economy test constructs buildings near HQ. Select an actual reachable
	# contact approach instead of expecting an arbitrary east-side tile to remain
	# empty after the academy is built and carved into native navigation.
	var unit: BattleUnit = game.get_node("Units").get_child(0)
	var query := NavigationPathQueryParameters3D.new()
	var result := NavigationPathQueryResult3D.new()
	query.map = unit.navigation_agent.get_navigation_map()
	query.start_position = from
	query.target_position = NavigationServer3D.map_get_closest_point(query.map, game.defended_headquarters.get_attack_position(from))
	query.navigation_layers = unit.navigation_agent.navigation_layers
	query.path_search_max_polygons = unit.navigation_agent.path_search_max_polygons
	query.metadata_flags = unit.navigation_agent.path_metadata_flags
	NavigationServer3D.query_path(query, result)
	var attacker: UnitDefinition = BalanceCatalog.unit("war_elephant")
	var contact: Vector3 = game.defended_headquarters.get_attack_position(query.target_position)
	var in_attack_reach: bool = query.target_position.distance_to(contact) <= attacker.range + attacker.radius
	return in_attack_reach and result.path.size() >= 2 and result.path[-1].distance_to(query.target_position) < 0.3

func _enemy_production_routes() -> void:
	await _sync_navigation()
	var count: int = 0
	for building: BattleBuilding in game.owned_entities(1, "buildings"):
		if building.building_type not in ["barracks", "factory"]:
			continue
		count += 1
		# Verify the largest late-wave body from each production family as well
		# as the real building exit, rather than querying an arbitrary map point.
		var kind: String = "war_elephant" if building.building_type == "barracks" else "heavy_cannon"
		var at: Vector3 = game.find_recruit_position(kind, building)
		var label: String = "%s %d" % [building.building_type, building.entity_id]
		check(at.is_finite(), label + " has a collision-safe native " + kind + " production exit")
		if at.is_finite():
			check(_path_reaches_headquarters(at), label + " production exit connects to the player headquarters approach")
	check(count == 6, "all four eastern barracks and both factories are covered by exit and route checks")

func _destroy_enemy_producers() -> void:
	for building: BattleBuilding in game.owned_entities(1, "buildings"):
		if building.building_type in ["barracks", "factory"]:
			building.receive_damage(building.hp)
	await _sync_navigation()
	game.check_victory()
	await process_frame
	var surviving: Array = game.owned_entities(1, "buildings")
	check(not surviving.is_empty() and surviving.all(func(building: BattleBuilding): return building.building_type not in ["barracks", "factory"]), "raiding every enemy producer leaves the permanent fortifications standing")
	check(not game.finished and not game.wave_active and game.wave_index == 1, "destroying all production buildings cannot win before the remaining defense waves")

func _current_wave_units() -> Array:
	return game.get_node("Units").get_children().filter(func(unit: BattleUnit):
		return unit.alive and int(unit.get_meta("defense_wave", 0)) == game.wave_index)

func _kill_current_wave() -> void:
	for unit: BattleUnit in _current_wave_units():
		unit.receive_damage(unit.hp)

func _clear_current_wave() -> void:
	# Each step lets the real spawn queue publish a batch. Deaths follow the same
	# signals as combat; no direct assignment to the controller's alive count.
	for batch: int in 200:
		if not game.wave_active or game.finished:
			return
		game._advance_waves(1.0)
		_kill_current_wave()
		game.check_victory()
		await process_frame
	check(false, "wave finishes after bounded pending-queue drain")

func _paid_economy() -> void:
	var player: PlayerState = game.get_player(0)
	var original_gold: int = player.gold
	var worker: BattleUnit = game.owned_entities(0, "units").filter(func(unit: BattleUnit): return unit.unit_type == "farmer")[0]
	var mine: ResourceVein = game.nearest_mine(worker.position)
	worker.stop()
	worker.issue_gather(mine)
	worker.global_position = worker.destination
	worker._work_velocity(BalanceCatalog.ECONOMY.mining_seconds)
	check(player.gold == original_gold + BalanceCatalog.ECONOMY.mining_gold, "snowfield mine pays through the real worker economy")
	player.gold = 5000
	var at: Vector3 = game.find_build_location(0, "barracks", game.defended_headquarters.position)
	check(at.is_finite(), "snowfield has a legal player barracks site")
	if not at.is_finite():
		return
	var price: int = player.get_building_cost("barracks")
	var result: Dictionary = game.create_site(0, "barracks", at, [worker], false)
	check(result.ok and player.gold == 5000 - price, "player can pay and place a real barracks construction site")
	if not result.ok:
		return
	var barracks: BattleBuilding = game.owned_entities(0, "buildings").filter(func(building: BattleBuilding): return building.entity_id == result.entity_id)[0]
	check(not barracks.is_constructed, "paid barracks begins as a construction site")
	worker.global_position = barracks.get_attack_position(barracks.position + Vector3(10, 0, 0)) + Vector3(0.5, 0, 0)
	worker._work_velocity(barracks.get_combat_definition().build_seconds)
	check(barracks.is_constructed, "assigned farmer completes the barracks through native construction")
	barracks.set_physics_process(false)
	barracks.production.set_physics_process(false)
	for attempt: int in 240:
		if game.find_recruit_position("swordsman", barracks).is_finite():
			break
		await physics_frame
	check(game.find_recruit_position("swordsman", barracks).is_finite(), "constructed snowfield barracks has a navigable production exit")
	var supply_before: int = player.military_supply
	var gold_before: int = player.gold
	var swordsman: UnitDefinition = BalanceCatalog.unit("swordsman")
	check(barracks.production.recruit("swordsman").ok and player.gold == gold_before - swordsman.cost, "defense barracks accepts paid military training")
	barracks.production._physics_process(swordsman.training_seconds)
	check(player.military_supply == supply_before + swordsman.supply and player.reserved_military_supply == 0, "completed training creates a real unit and transfers population reservation")
	at = game.find_build_location(0, "academy", game.defended_headquarters.position)
	check(at.is_finite(), "snowfield has a legal academy site")
	if not at.is_finite():
		return
	var academy: BattleBuilding = game.spawn_building("academy", 0, at)
	academy.production.set_physics_process(false)
	academy.set_physics_process(false)
	gold_before = player.gold
	var upgrade: UpgradeDefinition = BalanceCatalog.upgrade("attack_1")
	check(academy.production.research("attack_1").ok and player.gold == gold_before - upgrade.cost, "defense academy accepts paid standard upgrades")
	academy.production._physics_process(upgrade.research_seconds)
	check(player.attack_level == 1, "normal research completion applies the player's technology")
	_freeze_simulation()

func _run() -> void:
	create_timer(60.0, true, false, true).timeout.connect(func(): push_error("DEFENSE_MODE deadline"); quit(3))
	await _load_battle()
	check(game.waves.size() == 10 and game.wave_index == 0 and not game.wave_active, "defense opens with ten authored waves and no active attack")
	check(game.preparation_remaining > 118.0 and game.preparation_remaining <= 120.0, "opening preparation gives the player two minutes")
	check(game.defended_headquarters == game.headquarters and game.defended_headquarters.owner_id == 0, "original player headquarters is the protected objective")
	check(game.defended_headquarters.position.x < 0.0, "player headquarters starts on the western side")
	check(game.owned_entities(1, "buildings").size() >= 6, "eastern enemy base contains multiple permanent fortifications")
	check(get_nodes_in_group("resource_veins").size() >= 4, "defense snowfield contains multiple expansion mines")
	check(game.bots.is_empty(), "standard skirmish economy AI cannot create unscheduled enemy attacks")
	var bell: AudioStreamPlayer = game.get_node("WaveBell")
	check(bell.stream.resource_path == "res://assets/audio/defense_wave_bell.wav" and bell.bus == &"Combat" and bell.process_mode == Node.PROCESS_MODE_PAUSABLE, "each wave uses the authored global pausable defense bell")
	game.handle_pause_action()
	var paused_preparation: float = game.preparation_remaining
	var paused_elapsed: float = game.elapsed
	game._advance_waves(1000.0)
	game._start_wave()
	await create_timer(0.12, true).timeout
	check(paused and game.preparation_remaining == paused_preparation and game.elapsed == paused_elapsed and game.wave_index == 0, "native pause freezes preparation, simulation and wave scheduling")
	game.handle_pause_action()
	_freeze_simulation()
	await _enemy_production_routes()
	await _paid_economy()
	game.check_victory()
	await process_frame
	check(not game.finished, "living enemy fortifications and no active wave do not resolve the preparation phase")
	game._advance_waves(game.preparation_remaining - 0.1)
	check(game.wave_index == 0 and not game.wave_active, "first wave waits for the complete preparation interval")
	game._advance_waves(0.11)
	check(game.wave_index == 1 and game.wave_active and bell.playing, "first attack begins once and rings the warning bell")
	var pending_before: int = game.pending_wave_units.size()
	var living_before: int = _current_wave_units().size()
	game._start_wave()
	check(game.wave_index == 1 and game.pending_wave_units.size() == pending_before and _current_wave_units().size() == living_before, "repeated start cannot overlap or duplicate an active wave")
	game._advance_waves(1.0)
	var attackers: Array = _current_wave_units()
	check(not attackers.is_empty(), "wave queue spawns real tagged enemies")
	check(attackers.all(func(unit: BattleUnit): return unit.owner_id == 1 and unit.order == BattleUnit.Order.ATTACK_MOVE), "wave enemies attack-move toward the defended player base")
	await _clear_current_wave()
	check(not game.finished and not game.wave_active and game.wave_index == 1, "clearing the first wave returns to preparation without winning")
	check(is_equal_approx(game.preparation_remaining, 45.0), "cleared wave grants forty-five seconds to rebuild")
	await _destroy_enemy_producers()
	game._advance_waves(44.9)
	check(game.wave_index == 1 and not game.wave_active, "second wave cannot skip its preparation window")
	game._advance_waves(0.11)
	check(game.wave_index == 2 and game.wave_active, "second wave begins when the intermission expires")
	check(game.wave_remaining == ceili(game.waves[1].roster().size() * 0.5), "destroying every producer halves the next wave instead of cancelling it")
	game._advance_waves(1.0)
	var reserves: Array = _current_wave_units()
	check(reserves.size() == 1, "eastern border reserves actually spawn an enemy after all producers are destroyed")
	if not reserves.is_empty():
		var reserve: BattleUnit = reserves[0]
		var entrances: Array[Node] = game.map_instance.get_node("Entrances").get_children()
		check(entrances.any(func(marker: Marker3D): return marker.global_position.distance_to(reserve.global_position) < 8.0), "reserve arrives beside a real authored eastern entry")
		check(_path_reaches_headquarters(reserve.global_position), "border reserve has a complete navigation route to the defended headquarters")
	await _clear_current_wave()
	# Fast-forward only the completed-wave index; exercise final spawning/deaths
	# using the real tenth resource, without a long unattended battle simulation.
	game.wave_index = 9
	game._start_wave()
	check(game.wave_index == 10 and game.wave_active and not game.pending_wave_units.is_empty(), "last authored wave starts with a real pending spawn queue")
	_kill_current_wave()
	game.check_victory()
	await process_frame
	check(not game.finished and game.wave_active, "last wave cannot win while additional enemies are still pending")
	await _clear_current_wave()
	check(game.finished and game.battle_won, "surviving all ten cleared waves wins the defense")
	check(not game.owned_entities(1, "buildings").is_empty(), "victory does not require demolishing eastern enemy buildings")
	var completed_index: int = game.wave_index
	game._advance_waves(1000.0)
	game._start_wave()
	check(game.wave_index == completed_index and game.pending_wave_units.is_empty(), "finished defense never schedules an eleventh wave")
	await _load_battle()
	_freeze_simulation()
	var original: BattleBuilding = game.defended_headquarters
	var replacement_at: Vector3 = original.position + Vector3(20, 0, 18)
	check(game.placement_error(replacement_at, 0, "headquarters") == "每位玩家只能拥有一座大本营（含工地）", "normal defense placement preserves the one-headquarters-per-player rule")
	# Deliberately bypass paid placement only to simulate a stale/replaced generic
	# HQ reference; normal gameplay must continue rejecting a second headquarters.
	var replacement: BattleBuilding = game.spawn_building("headquarters", 0, replacement_at)
	check(game.headquarters == replacement and game.defended_headquarters == original, "a replaced generic headquarters reference cannot replace the defense objective")
	original.receive_damage(original.hp)
	game.check_victory()
	await process_frame
	check(game.finished and not game.battle_won and replacement.alive, "original headquarters loss defeats defense despite a surviving replacement")
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	print("DEFENSE_MODE_RESULTS " + JSON.stringify({"checks": checks, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
