extends Node
## Persistent native transport and the small configuration crossing scene changes.
signal load_failed(message: String)
var config: Dictionary = {}
var online: bool = false
@onready var relay: RelayClient = $RelayClient
@onready var settings: GameSettings = $Settings
@onready var rogue: RogueSession = $Rogue
@onready var transition: UITransition = $Transition

func _ready() -> void:
	transition.failed.connect(_on_transition_failed)
	record_diagnostic("startup", {"engine": Engine.get_version_info().string, "display": DisplayServer.get_name(),
		"renderer": RenderingServer.get_current_rendering_method(), "audio": AudioServer.get_driver_name(),
		"shader_uniform_slots": ProjectSettings.get_setting("rendering/limits/global_shader_variables/buffer_size"),
		"gpu": RenderingServer.get_video_adapter_name() if DisplayServer.get_name() != "headless" else "headless"})
	if "--network-smoke" in OS.get_cmdline_user_args():
		get_tree().change_scene_to_file.call_deferred("res://scripts/network/release_probe.tscn")
	elif "--match-smoke" in OS.get_cmdline_user_args():
		add_child.call_deferred(preload("res://scripts/qa/release_match_probe.tscn").instantiate())
	elif "--rogue-release-smoke" in OS.get_cmdline_user_args():
		add_child.call_deferred(preload("res://scripts/qa/rogue_release_probe.tscn").instantiate())

func start_offline(mode: String, bot_difficulty: String = "normal") -> Error:
	if transition.busy:
		return ERR_BUSY
	if mode not in NetworkProtocol.MODES:
		load_failed.emit("所选对局模式无效，请重新选择")
		return ERR_INVALID_PARAMETER
	if bot_difficulty not in NetworkProtocol.BOT_DIFFICULTIES:
		load_failed.emit("所选电脑难度无效，请重新选择")
		return ERR_INVALID_PARAMETER
	record_diagnostic("load_match", {"online": false, "mode": mode})
	online = false
	config = offline_config(mode, bot_difficulty)
	return _load_match_scene()

static func offline_config(mode: String, bot_difficulty: String = "normal") -> Dictionary:
	var match_data: Dictionary = {"mode": mode, "players": []}
	for owner: int in int(NetworkProtocol.MODES[mode].slots):
		match_data.players.append({"owner_id": owner, "team_id": NetworkProtocol.default_alliance(mode, owner),
			"controller": "human" if owner == 0 else "bot", "name": "指挥官" if owner == 0 else "王国将领 %d" % owner,
			"bot_difficulty": "normal" if owner == 0 else bot_difficulty})
	return match_data

func start_online(match_data: Dictionary) -> Error:
	if transition.busy:
		return ERR_BUSY
	if not NetworkProtocol.match_config_error(match_data).is_empty():
		relay.leave_room()
		online = false
		config.clear()
		load_failed.emit("对局席位配置无效，请重新创建或加入房间")
		return ERR_INVALID_DATA
	record_diagnostic("load_match", {"online": true, "mode": match_data.mode})
	online = true
	config = match_data.duplicate(true)
	return _load_match_scene()

func start_sandbox(map_mode: String = "1v1") -> Error:
	if transition.busy:
		return ERR_BUSY
	if map_mode not in NetworkProtocol.MODES:
		return ERR_INVALID_PARAMETER
	relay.leave_room()
	relay.disconnect_relay()
	online = false
	config = {"mode": map_mode}
	var error := change_scene("res://scenes/sandbox.tscn")
	if error != OK:
		config.clear()
		load_failed.emit("无法载入自由沙盘，请检查游戏文件后重试")
	return error

func start_moba_test1() -> Error:
	if transition.busy: return ERR_BUSY
	relay.leave_room()
	relay.disconnect_relay()
	online = false
	config = {"mode": "moba_test1"}
	var error := change_scene("res://scenes/moba/test1.tscn")
	if error != OK:
		config.clear()
		load_failed.emit("无法载入 MOBA 卡牌测试场景，请检查游戏文件后重试")
	return error

func start_defense() -> Error:
	if transition.busy:
		return ERR_BUSY
	relay.leave_room()
	relay.disconnect_relay()
	online = false
	config = {"mode": "defense"}
	record_diagnostic("load_match", {"online": false, "mode": "defense"})
	var error := change_scene("res://scenes/defense/battle.tscn")
	if error != OK:
		config.clear()
		load_failed.emit("无法载入雪原防卫，请检查游戏文件后重试")
	return error

func _load_match_scene() -> Error:
	var error := change_scene("res://scenes/main.tscn")
	if error != OK:
		if online:
			relay.leave_room()
		online = false
		config.clear()
		load_failed.emit("无法载入 Block-RTS 战场，请检查游戏文件后重试")
	return error

func back_to_lobby() -> void:
	if transition.busy:
		return
	record_diagnostic("return_to_lobby")
	get_tree().paused = false
	relay.leave_room()
	online = false
	config.clear()
	var error: Error = change_scene("res://scenes/lobby.tscn")
	if error != OK:
		load_failed.emit("无法返回主菜单，请检查游戏文件后重试")

func change_scene(path: String) -> Error:
	return transition.change_scene(path)

func _on_transition_failed(path: String, _error: Error) -> void:
	# Resource validation is synchronous. If SceneTree itself cannot instantiate
	# the validated scene, the curtain still opens and the old screen can retry.
	if path in ["res://scenes/main.tscn", "res://scenes/sandbox.tscn", "res://scenes/moba/test1.tscn", "res://scenes/defense/battle.tscn"]:
		if online:
			relay.leave_room()
		online = false
		config.clear()
	if path in [RogueSession.MAP_SCENE, RogueSession.BATTLE_SCENE]:
		rogue.error_message = "无法加载远征场景，请检查游戏文件后重试"
		rogue.changed.emit()
	load_failed.emit("无法切换场景，请检查游戏文件后重试")

func record_diagnostic(event: String, details: Dictionary = {}) -> void:
	# Only bounded lifecycle/health facts reach this local log. Never dump the
	# room config, endpoint, invitation or reconnect credentials.
	print("JIMU_DIAGNOSTIC ", JSON.stringify({"event": event, "build": NetworkProtocol.BUILD_ID, "release": NetworkProtocol.RELEASE_ID,
		"pid": OS.get_process_id(), "seconds": snappedf(Time.get_ticks_msec() / 1000.0, 0.001), "details": details}))

func _record_health() -> void:
	var scene: Node = get_tree().current_scene
	if not is_instance_valid(scene):
		return
	var details := {"scene": scene.scene_file_path, "paused": get_tree().paused,
		"fps": Engine.get_frames_per_second(), "nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"video_memory_bytes": int(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED))}
	if scene.scene_file_path == "res://scenes/main.tscn" and scene._match_ready:
		details.merge({"online": scene.online, "authority": scene.is_authority, "tick": scene.simulation_tick,
			"finished": scene.finished, "closing": scene._closing, "units": scene.unit_container.get_child_count(),
			"effects": scene.effect_container.get_child_count()})
	record_diagnostic("health", details)

func _exit_tree() -> void:
	record_diagnostic("session_exit")
