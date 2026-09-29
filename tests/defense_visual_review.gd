extends SceneTree
## Private-desktop review of the real menu, opening defense and snowfield.
var game: Node3D
var output: String

func _initialize() -> void:
	output = OS.get_cmdline_user_args()[0]
	_run.call_deferred()

func capture(name: String) -> void:
	await create_timer(0.5).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name + ".png"))

func _run() -> void:
	root.size = Vector2i(1600, 900)
	change_scene_to_file("res://scenes/lobby.tscn")
	await scene_changed
	await create_timer(1.0).timeout
	await capture("lobby")
	# Exercise the production entry and scene transition, including the new button.
	current_scene.get_node("%DefenseMode").pressed.emit()
	await scene_changed
	game = current_scene
	game.camera_rig.edge_scroll = false
	await create_timer(1.2).timeout
	game.set_physics_process(false)
	await capture("opening")
	game._start_wave()
	for index: int in 8:
		game._advance_waves(1.0)
		await physics_frame
	await capture("wave_warning")
	# The following composition shots deliberately show the whole authored map.
	game.set_process(false)
	game.get_node("FogOfWar/Overlay").hide()
	game.get_node("HUD").hide()
	game.get_node("Atmosphere").hide()
	for building: BattleBuilding in get_nodes_in_group("buildings"):
		building.show()
	for mine: ResourceVein in get_nodes_in_group("resource_veins"):
		mine.show()
	var residences: Array = game.owned_entities(1, "buildings").filter(func(building: BattleBuilding): return building.building_type == "residence")
	for view: Dictionary in [
		{"name": "snowfield_overview", "center": Vector3.ZERO, "zoom": 180.0},
		{"name": "player_base", "center": game.defended_headquarters.position + Vector3(10, 0, -1), "zoom": 61.0},
		{"name": "enemy_fortifications", "center": Vector3(100, 0, -3), "zoom": 75.0},
		{"name": "enemy_town", "center": Vector3(91, 0, -2), "zoom": 101.0},
		{"name": "frozen_river", "center": Vector3(8, 0, 0), "zoom": 89.0},
		{"name": "north_ice_crossing", "center": Vector3(-3, 0, -40), "zoom": 46.0}
	]:
		game.camera_rig.focus_at(view.center, true)
		game.camera_rig.zoom_target = view.zoom
		game.camera.size = view.zoom
		await capture(view.name)
	for kind: String in ["residence_cottage", "residence_townhouse", "residence_longhouse"]:
		var residence: BattleBuilding = residences.filter(func(building: BattleBuilding): return building.get_combat_definition().model == kind)[0]
		game.camera_rig.focus_at(residence.global_position + Vector3(0, 0, -1.8), true)
		game.camera_rig.zoom_target = 18.0
		game.camera.size = 18.0
		await capture(kind)
	var inspected: BattleBuilding = residences[0]
	game.camera_rig.focus_at(inspected.global_position + Vector3(0, 0, -2), true)
	game.camera_rig.zoom_target = 24.0
	game.camera.size = 24.0
	game.get_node("HUD").show()
	game.select_entities([inspected])
	await capture("residence_selected")
	game.get_node("HUD").hide()
	inspected.receive_damage(inspected.hp)
	await create_timer(1.4).timeout
	await capture("residence_destroyed")
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	quit()
