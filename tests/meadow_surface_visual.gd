extends SceneTree
## Capture the six RTS battlefields with the same saved lighting as main.tscn.
## Use tools/run_godot_private_desktop.py with --script-arg=1v1 to review one map.
## The first user argument is the output directory; remaining arguments are modes.

const DEFAULT_OUTPUT := "res://artifacts/grass_refinement/rts/"
var camera: Camera3D
var output := DEFAULT_OUTPUT

func _initialize() -> void:
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, true)
	DisplayServer.window_set_position(Vector2i(-20000, -20000))
	_run.call_deferred()

func capture(label: String, focus: Vector3, zoom: float) -> void:
	camera.global_position = focus + Vector3(-60, 84, 60)
	camera.look_at(focus)
	camera.size = zoom
	camera.reset_physics_interpolation()
	for frame: int in 45:
		await process_frame
	await RenderingServer.frame_post_draw
	assert(root.get_texture().get_image().save_png(output.path_join(label + ".png")) == OK)
	print("MEADOW_CAPTURE ", label, " size=", camera.size)

func _run() -> void:
	create_timer(120.0, true, false, true).timeout.connect(func(): quit(3))
	var arguments := OS.get_cmdline_user_args()
	var requested: PackedStringArray = []
	if not arguments.is_empty():
		output = arguments[0]
		requested = arguments.slice(1)
	for mode: String in requested:
		assert(mode in NetworkProtocol.MODES, "Unknown RTS map mode: " + mode)
	assert(DirAccess.make_dir_recursive_absolute(output) == OK)
	root.size = Vector2i(1600, 900)
	root.gui_disable_input = true
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	change_scene_to_file("res://tests/meadow_surface_review.tscn")
	await scene_changed
	var gallery := current_scene
	camera = gallery.get_node("Camera3D")
	for mode: String in NetworkProtocol.MODES:
		if not requested.is_empty() and mode not in requested:
			continue
		var definition: MapDefinition = load(NetworkProtocol.map_path(mode))
		var map: Node3D = definition.scene.instantiate()
		gallery.get_node("MapContainer").add_child(map)
		await capture(mode + "_overview", Vector3.ZERO, maxf(definition.size.x, definition.size.y) * 1.45)
		var samples: Array[float] = []
		for frame: int in 90:
			await process_frame
			samples.append(RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid()))
		samples.sort()
		print("MEADOW_GPU_MS ", mode, " median=", samples[45], " p95=", samples[85])
		var focus := Vector3(-12, 0, 14)
		await capture(mode + "_ground", focus, 20.0)
		if mode == "1v1":
			# Inspect texture anchoring and TAA at the RTS camera's normal zoom.
			await capture("1v1_tactical", focus, 31.0)
			await capture("1v1_shift", focus + Vector3(0.35, 0, 0.22), 31.0)
			await capture("1v1_shift_still", focus + Vector3(0.35, 0, 0.22), 31.0)
		map.queue_free()
		await process_frame
	quit()
