extends SceneTree
## Real menu scenes and native input exercise interruption and context scoping.
## Settings are only opened/closed; this test never applies or saves preferences.

const LOBBY := "res://scenes/lobby.tscn"
const FIXTURE := "res://tests/ui_motion_fixture.tscn"
const SETTINGS_SECTIONS: Array[NodePath] = [
	NodePath("Center/Panel"), NodePath("Center/Panel/Layout/Heading"),
	NodePath("Center/Panel/Layout/Body/Sidebar"), NodePath("Center/Panel/Layout/Body/Content"),
	NodePath("Center/Panel/Layout/Actions"),
]
var checks := 0
var failures: Array[String] = []
var _had_lobby_preferences := false
var _lobby_preferences: PackedByteArray = []

func _initialize() -> void:
	_run.call_deferred()

func check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)
		printerr("FAIL ", label)

func _settle(seconds: float = 0.60) -> void:
	await create_timer(seconds, true, false, true).timeout

func _move(at: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = at
	event.global_position = at
	root.push_input(event, true)

func _click(button: Button) -> void:
	var at := button.get_global_rect().get_center()
	_move(at)
	for down: bool in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = at
		event.global_position = at
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = down
		root.push_input(event, true)

func _capture(scene: Node, paths: Array[NodePath]) -> Array[Dictionary]:
	var snapshot: Array[Dictionary] = []
	for path: NodePath in paths:
		var control: Control = scene.get_node(path)
		snapshot.append({"control": control, "position": control.position,
			"scale": control.scale, "alpha": control.modulate.a})
	return snapshot

func _check_restored(snapshot: Array[Dictionary], label: String) -> void:
	for state: Dictionary in snapshot:
		var control: Control = state.control
		check(control.position.is_equal_approx(state.position), "%s: %s restores position" % [label, control.name])
		check(control.scale.is_equal_approx(state.scale), "%s: %s restores scale" % [label, control.name])
		check(is_equal_approx(control.modulate.a, state.alpha), "%s: %s restores opacity" % [label, control.name])

func _check_entrance(scene: Node, label: String) -> void:
	var entrance: Node = scene.get_node("MenuEntrance")
	check(entrance.started, "%s starts its scene-authored entrance" % label)
	for path: NodePath in entrance.sections:
		var control: Control = scene.get_node(path)
		check(control.scale.is_equal_approx(Vector2.ONE) and is_equal_approx(control.modulate.a, 1.0),
			"%s: %s finishes at authored transform and opacity" % [label, control.name])

func _restore_lobby_preferences() -> void:
	var path := "user://lobby_preferences.cfg"
	if _had_lobby_preferences:
		var file := FileAccess.open(path, FileAccess.WRITE)
		assert(file != null)
		file.store_buffer(_lobby_preferences)
	elif FileAccess.file_exists(path):
		assert(DirAccess.remove_absolute(path) == OK)

func _run() -> void:
	_had_lobby_preferences = FileAccess.file_exists("user://lobby_preferences.cfg")
	if _had_lobby_preferences:
		_lobby_preferences = FileAccess.get_file_as_bytes("user://lobby_preferences.cfg")
	create_timer(45.0, true, false, true).timeout.connect(func():
		_restore_lobby_preferences()
		quit(3))
	root.size = Vector2i(1600, 900)
	var session: Node = root.get_node("Session")
	var settings: GameSettings = session.settings
	var original_preferences: Dictionary = settings.snapshot()
	await _check_transition(session)
	for resolution: Vector2i in [Vector2i(1600, 900), Vector2i(1280, 720)]:
		root.size = resolution
		await _check_lobby(resolution)
	await _check_settings(settings)
	await _check_battle_profile(settings)
	check(settings.snapshot() == original_preferences, "menu motion never changes saved preference values")
	_restore_lobby_preferences()
	print("MENU_MOTION_TEST checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)

func _check_transition(session: Node) -> void:
	change_scene_to_file(FIXTURE)
	await scene_changed
	check(session.change_scene(LOBBY) == OK, "real paper transition accepts the RTS lobby")
	await scene_changed
	var picker: Node3D = current_scene
	var entrance: Node = picker.get_node("MenuEntrance")
	check(session.transition.busy and not entrance.started, "native scene_changed does not start an entrance beneath the paper")
	await _settle(0.08)
	check(session.transition.busy and not entrance.started, "entrance waits while the paper is still opening")
	for path: NodePath in entrance.sections:
		check(is_zero_approx(picker.get_node(path).modulate.a), "covered section stays hidden: %s" % path)
	await session.transition.completed
	check(entrance.started, "transition completed starts the waiting entrance")
	await _settle(0.80) # Nine authored lobby groups complete after 0.66 seconds.
	_check_entrance(picker, "transitioned lobby")

func _check_lobby(resolution: Vector2i) -> void:
	change_scene_to_file(LOBBY)
	await scene_changed
	await _settle(0.80)
	var lobby: Node3D = current_scene
	_check_entrance(lobby, "RTS lobby %s" % resolution)
	_click(lobby.get_node("%SoloMenu"))
	await _settle()
	var solo: Control = lobby.get_node("%SoloPanel")
	var baseline := _capture(lobby, [NodePath("%SoloPanel"), NodePath("%MapTitle"), NodePath("%SoloDescription")])
	for mode: String in ["2v2", "4v4", "1v1"]:
		_click(lobby.get_node("%Mode" + mode))
		await _settle(0.035)
	lobby._on_close_solo()
	check(not solo.visible, "solo panel closes immediately during entrance")
	_click(lobby.get_node("%SoloMenu"))
	await _settle()
	_check_restored(baseline, "solo panel reopened at %s" % resolution)
	check(lobby.mode == "1v1", "rapid mode changes retain final RTS mode")
	_click(lobby.get_node("%Multiplayer"))
	await _settle(0.04)
	lobby._on_close_multiplayer()
	check(not lobby.get_node("%OnlinePanel").visible, "online panel closes immediately during entrance")
	_click(lobby.get_node("%Multiplayer"))
	await _settle()
	check(is_equal_approx(lobby.get_node("%OnlinePanel").modulate.a, 1.0), "online panel reopens fully opaque")
	lobby._on_close_multiplayer()
	_move(Vector2(4, 4))

func _check_settings(settings: GameSettings) -> void:
	settings.open_menu()
	await _settle(0.04)
	var opening_panel: Control = settings.menu.get_node("Center/Panel")
	check(opening_panel.get_meta(UIMotion.PANEL_META).active and opening_panel.modulate.a < 1.0,
		"first settings layout preserves a visible entrance instead of cancelling it")
	await _settle()
	var menu: Control = settings.menu
	var baseline := _capture(menu, SETTINGS_SECTIONS)
	check(is_equal_approx(menu.get_node("Center/Panel").get_meta(UIMotion.PANEL_META).start_scale, 0.96), "settings use the menu profile from a menu scene")
	for page: String in ["Audio", "Controls", "Graphics"]:
		_click(menu.get_node("%Categories/" + page))
		await _settle(0.03)
		var changing_page: Control = menu.get_node("%Pages/" + page)
		check(changing_page.get_meta(UIMotion.PANEL_META).active and changing_page.modulate.a < 1.0,
			"first layout of %s preserves its delayed page transition" % page)
	settings.close_menu()
	check(not settings.is_open(), "closing settings interrupts active page transitions immediately")
	settings.open_menu()
	await _settle(0.04)
	settings.close_menu()
	settings.open_menu()
	await _settle()
	_check_restored(baseline, "settings reopened during entrance")
	for node_name: String in ["SectionTitle", "SectionHint", "Pages/Graphics"]:
		check(is_equal_approx(menu.get_node("%" + node_name).modulate.a, 1.0), "reopened settings detail is opaque: %s" % node_name)
	settings.close_menu()
	_move(Vector2(4, 4))

func _check_battle_profile(settings: GameSettings) -> void:
	# An authored scene outside animated_menu exercises the same context gate
	# used by battles without running combat or creating dynamic test nodes.
	change_scene_to_file(FIXTURE)
	await scene_changed
	await process_frame
	var fixture: Control = current_scene
	UIMotion.bind_buttons(fixture)
	var button: Button = fixture.get_node("Buttons/Primary")
	check(not button.get_meta(UIMotion.BUTTON_META).menu, "ordinary combat-style binding does not opt into menu feedback")
	button.button_down.emit()
	await _settle(0.16)
	check(button.scale.is_equal_approx(Vector2.ONE * 0.98), "ordinary buttons retain the restrained combat press scale")
	button.button_up.emit()
	var panel: Control = fixture.get_node("Independent")
	var motion: Tween = UIMotion.reveal(panel)
	check(panel.scale.is_equal_approx(Vector2.ONE * 0.985), "ordinary panels retain the combat reveal scale")
	motion.custom_step(0.19)
	check(not panel.get_meta(UIMotion.PANEL_META).active and panel.scale.is_equal_approx(Vector2.ONE), "ordinary reveal completes at the original 0.18-second duration")
	settings.open_menu()
	var settings_panel: Control = settings.menu.get_node("Center/Panel")
	check(is_equal_approx(settings_panel.get_meta(UIMotion.PANEL_META).start_scale, 0.985), "settings restore the original profile outside menu scenes")
	var settings_motion: Tween = settings_panel.get_meta(UIMotion.PANEL_META).tween
	settings_motion.custom_step(0.19)
	check(not settings_panel.get_meta(UIMotion.PANEL_META).active and is_equal_approx(settings_panel.modulate.a, 1.0), "non-menu settings complete with their original timing and full opacity")
	settings.close_menu()
