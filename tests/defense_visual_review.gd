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
	for view: Dictionary in [
		{"name": "snowfield_overview", "center": Vector3.ZERO, "zoom": 107.0},
		{"name": "player_base", "center": Vector3(-54, 0, -1), "zoom": 42.0},
		{"name": "enemy_fortifications", "center": Vector3(56, 0, -3), "zoom": 59.0}
	]:
		game.camera_rig.focus_at(view.center, true)
		game.camera_rig.zoom_target = view.zoom
		game.camera.size = view.zoom
		await capture(view.name)
	await game.prepare_shutdown()
	game.queue_free()
	await process_frame
	await process_frame
	quit()
