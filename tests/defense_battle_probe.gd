extends SceneTree
## Simulate the first attack along the entire snowy battlefield, without teleporting.
var game: Node3D

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
	game.preparation_remaining = 0.0
	var reached_west := false
	var attacks_observed := false
	var first_wave_finished := false
	var limit: float = game.elapsed + 150.0
	while game.elapsed < limit and not game.finished:
		for unit: BattleUnit in get_nodes_in_group("units"):
			if unit.owner_id == 1 and unit.position.x < -35.0:
				reached_west = true
			if unit.hp < unit.max_hp:
				attacks_observed = true
		if game.wave_index == 1 and not game.wave_active:
			first_wave_finished = true
			break
		await physics_frame
	var result := {"reached_west": reached_west, "combat_observed": attacks_observed,
		"first_wave_cleared": first_wave_finished, "elapsed": game.elapsed,
		"pending": game.pending_wave_units.size(), "remaining": game.wave_remaining,
		"base_hp": game.defended_headquarters.hp}
	print("DEFENSE_BATTLE_PROBE ", JSON.stringify(result))
	Engine.time_scale = 1.0
	Engine.physics_ticks_per_second = 30
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	quit(0 if reached_west and attacks_observed else 1)
