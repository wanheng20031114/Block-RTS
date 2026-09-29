extends "res://scripts/game.gd"
## Offline defense owns its objectives and waves; combat and economy remain RTS.
signal wave_started(index: int)
signal wave_cleared(index: int)

@export var scenario: DefenseScenarioDefinition
var waves: Array[DefenseWaveDefinition]:
	get: return scenario.waves
var wave_index: int = 0
var wave_active: bool = false
var preparation_remaining: float = 0.0
var defended_headquarters: BattleBuilding
var pending_wave_units: Array[String] = []
var wave_remaining: int:
	get: return pending_wave_units.size() + living_wave_units()
var battle_won: bool = false
var _spawn_remaining: float = 0.0
var _spawn_serial: int = 0
var _order_remaining: float = 0.0
var _initial_producers: int = 0
var _resolution_queued: bool = false
var _blocked_spawn_seconds: float = 0.0

func _ready() -> void:
	await super._ready()
	hud.get_node("HelpOverlay/Paper/Intro").text = "守住十波并保护初始大本营；经济与升级规则不变。\n摧毁敌兵营与工厂，最多削减一半后续增援。"
	hud.toast("守护左侧大本营 · 守住十波敌袭\n%d 秒准备：采矿、扩军、布置防线" % ceili(scenario.preparation_seconds), 8.0)
	hud.refresh()

func _setup_match() -> void:
	assert(not Session.online, "Snowfield defense is offline")
	online = false
	is_authority = true
	local_owner_id = 0
	match_config = {"mode": "defense"}
	players = [PlayerState.new(0, 0), PlayerState.new(1, 1)]
	players[0].display_name = "雪原守军"
	players[0].gold = scenario.starting_gold
	players[1].display_name = "霜境军团"
	players[1].controller = "bot"
	players[1].gold = 0
	map_definition = preload("res://data/defense/snowfield.tres")
	map_size = map_definition.size
	map_instance = map_definition.scene.instantiate()
	$MapContainer.add_child(map_instance)
	_spawn_indices = {0: 0, 1: 1}
	defended_headquarters = spawn_building("headquarters", 0, get_spawn_marker(0).global_position)
	for marker: Marker3D in map_instance.get_node("StartingBuildings").get_children():
		spawn_building(marker.get_meta("kind"), 0, marker.global_position)
	for marker: Marker3D in map_instance.get_node("EnemyBuildings").get_children():
		var kind: String = marker.get_meta("kind")
		var residence: BuildingDefinition
		if kind == "residence":
			residence = BalanceCatalog.building(kind).duplicate()
			residence.model = marker.get_meta("model")
		var building := spawn_building(kind, 1, marker.global_position, false, 0, residence)
		if kind == "residence":
			building.rotation.y = marker.rotation.y
		building.rally_point = defended_headquarters.position
		if building.building_type in ["barracks", "factory"]:
			_initial_producers += 1
	assert(_initial_producers > 0, "Defense maps require enemy production buildings")
	var mine := nearest_mine(defended_headquarters.position)
	defended_headquarters.production.rally_mine = mine
	defended_headquarters.rally_point = mine.position
	for marker: Marker3D in map_instance.get_node("StartingUnits").get_children():
		var unit: BattleUnit = spawn_unit(marker.get_meta("kind"), 0, marker.global_position)
		if unit.unit_type == "farmer":
			unit.issue_gather(mine)
	preparation_remaining = scenario.preparation_seconds
	camera_rig.focus_at(defended_headquarters.position + Vector3(8, 0, 0), true)

func building_definition_for(kind: String, owner: int) -> BuildingDefinition:
	if owner == 0:
		return null
	var definition: BuildingDefinition = BalanceCatalog.building(kind).duplicate(true)
	# The wave director alone owns enemy recruitment; defenses retain their weapons.
	definition.produces = PackedStringArray()
	return definition

func mode_display_name() -> String:
	return "十波防卫"

func objective_text() -> String:
	if finished:
		return "十波防线已守住" if battle_won else "大本营失守"
	if wave_active:
		return "第 %d / %d 波 · %s" % [wave_index, waves.size(), waves[wave_index - 1].title]
	return "%s · %d 秒" % ["首波准备" if wave_index == 0 else "第 %d 波前整备" % (wave_index + 1), ceili(preparation_remaining)]

func enemy_status_text() -> String:
	if wave_active:
		return "本波剩余 %d（增援 %d） · 击败 %d" % [wave_remaining, pending_wave_units.size(), kills]
	return "已守住 %d / %d 波 · 保护初始大本营" % [wave_index, waves.size()]

func result_description(victory: bool) -> String:
	return "十波敌袭全部击退，大本营屹立在风雪中。" if victory else "初始大本营已被摧毁。下次尝试扩张矿场，并用前排部队保护远程火力。"

func living_wave_units() -> int:
	var count := 0
	for unit: BattleUnit in $Units.get_children():
		if unit.alive and unit.owner_id == 1 and unit.has_meta("defense_wave"):
			count += 1
	return count

func _physics_process(delta: float) -> void:
	if not _match_ready or finished or get_tree().paused:
		return
	super._physics_process(delta)
	_advance_waves(delta)

func _advance_waves(delta: float) -> void:
	if finished or not _match_ready or get_tree().paused:
		return
	if not wave_active:
		preparation_remaining = maxf(0.0, preparation_remaining - delta)
		if preparation_remaining <= 0.0:
			_start_wave()
		return
	_spawn_remaining -= delta
	if not pending_wave_units.is_empty() and _spawn_remaining <= 0.0:
		_spawn_remaining = scenario.spawn_interval
		_spawn_next_unit()
	_order_remaining -= delta
	if _order_remaining <= 0.0:
		_order_remaining = 2.0
		for unit: BattleUnit in $Units.get_children():
			if unit.alive and unit.owner_id == 1 and unit.order == BattleUnit.Order.IDLE:
				unit.issue_move(defended_headquarters.position, true)
	check_victory()

func _start_wave() -> void:
	if finished or wave_active or wave_index >= waves.size() or get_tree().paused:
		return
	wave_index += 1
	wave_active = true
	preparation_remaining = 0.0
	pending_wave_units = waves[wave_index - 1].roster()
	# Raiding supply buildings weakens future waves; border reserves keep all ten.
	var surviving := _living_producers().size()
	var lost_fraction := 1.0 - float(surviving) / float(_initial_producers)
	var target_count := maxi(1, ceili(pending_wave_units.size() * (1.0 - scenario.maximum_supply_reduction * lost_fraction)))
	pending_wave_units.resize(target_count)
	_spawn_remaining = 0.0
	_blocked_spawn_seconds = 0.0
	_order_remaining = 0.0
	$WaveBell.play()
	wave_started.emit(wave_index)
	hud.toast("警钟响起 · 第 %d / %d 波：%s\n%d 名敌军正从东侧出击" % [wave_index, waves.size(), waves[wave_index - 1].title, pending_wave_units.size()], 6.0)
	hud.refresh()

func _living_producers(kind: String = "") -> Array[BattleBuilding]:
	var result: Array[BattleBuilding] = []
	for building: BattleBuilding in $Buildings.get_children():
		if building.alive and building.owner_id == 1 and building.building_type in ["barracks", "factory"]:
			if kind.is_empty() or building.building_type == kind:
				result.append(building)
	return result

func _spawn_next_unit() -> void:
	var kind: String = pending_wave_units[0]
	var producers := _living_producers(str(BalanceCatalog.unit(kind).production_building))
	var at := Vector3.INF
	for offset: int in producers.size():
		var source: BattleBuilding = producers[(_spawn_serial + offset) % producers.size()]
		at = find_recruit_position(kind, source)
		if at.is_finite():
			break
	if producers.is_empty() or (not at.is_finite() and _blocked_spawn_seconds >= 8.0):
		at = _border_recruit_position(kind)
	# A besieged producer must not hold up every other troop type. After eight
	# blocked seconds the same unit arrives with the authored eastern reserves.
	if not at.is_finite():
		_blocked_spawn_seconds += scenario.spawn_interval
		pending_wave_units.append(pending_wave_units.pop_front())
		return
	_blocked_spawn_seconds = 0.0
	pending_wave_units.pop_front()
	_spawn_serial += 1
	var unit: BattleUnit = spawn_unit(kind, 1, at)
	unit.set_meta("defense_wave", wave_index)
	unit.issue_move(defended_headquarters.position, true)

func _border_recruit_position(kind: String) -> Vector3:
	var definition := BalanceCatalog.unit(kind)
	var shape := CapsuleShape3D.new()
	shape.radius = definition.radius + 0.1
	shape.height = maxf(shape.radius * 2.0, definition.collision_height)
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = shape
	query.collision_mask = 6 | 128
	var entrances := map_instance.get_node("Entrances").get_children()
	var spacing := maxf(2.0, shape.radius * 2.0 + 0.2)
	for offset: int in entrances.size():
		var marker: Marker3D = entrances[(_spawn_serial + offset) % entrances.size()]
		for index: int in 15:
			var at := marker.global_position + Vector3(-(index / 5) * spacing, 0, ((index % 5) - 2) * spacing)
			if not $ConstructionNavigation.contains_walkable_point(at):
				continue
			query.transform.origin = at + Vector3.UP * shape.height * 0.5
			if get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty():
				return at
	return Vector3.INF

func check_victory() -> void:
	if finished or not _match_ready or _resolution_queued:
		return
	_resolution_queued = true
	_resolve_wave.call_deferred()

func _resolve_wave() -> void:
	_resolution_queued = false
	if finished or not _match_ready:
		return
	# Resolve after the native physics tick; losing the base wins simultaneous ties.
	if not is_instance_valid(defended_headquarters) or not defended_headquarters.alive:
		end_battle(false)
	elif wave_active and wave_remaining == 0:
		wave_active = false
		players[0].gold += waves[wave_index - 1].clear_reward
		wave_cleared.emit(wave_index)
		if wave_index == waves.size():
			end_battle(true)
		else:
			preparation_remaining = scenario.intermission_seconds
			hud.toast("第 %d 波已击退 · 补给 +%d 金币\n%d 秒后下一波来袭" % [wave_index, waves[wave_index - 1].clear_reward, ceili(preparation_remaining)], 5.0)
			hud.refresh()

func on_entity_died(entity: Node3D) -> void:
	super.on_entity_died(entity)
	check_victory()

func end_battle(victory: bool, winner: int = -2) -> void:
	if finished:
		return
	battle_won = victory
	$WaveBell.stop()
	super.end_battle(victory, winner)

func prepare_shutdown() -> void:
	$WaveBell.stop()
	$WaveBell.stream = null
	await super.prepare_shutdown()
