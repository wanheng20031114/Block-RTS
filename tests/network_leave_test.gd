extends SceneTree
## Real local ENet and relay room state, including actual lobby and process exits.
## Only the socket setup skips DTLS; protocol and production exit paths are real.

class TestLobby extends "res://scripts/lobby.gd":
	func _save_preferences() -> void:
		pass # A regression test must not overwrite the player's saved preferences.

var server: JimuRelayServer
var checks: int = 0
var failures: Array[String] = []
var child_pids: Array[int] = []
var session: Node
var host: RelayClient

func _initialize() -> void:
	_run.call_deferred()

func check(passed: bool, label: String) -> void:
	checks += 1
	if not passed:
		failures.append(label)
		printerr("FAIL ", label)

func until(condition: Callable, timeout_ms: int = 4000) -> bool:
	var deadline: int = Time.get_ticks_msec() + timeout_ms
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return condition.call()

func connect_local(client: RelayClient, local_port: int) -> void:
	client.disconnect_relay()
	client.auto_reconnect = false
	client._leave_queued = false
	client._connection = ENetConnection.new()
	check(client._connection.create_host(1, NetworkProtocol.CHANNEL_COUNT) == OK, "client socket")
	client._peer = client._connection.connect_to_host("127.0.0.1", local_port, NetworkProtocol.CHANNEL_COUNT)
	client._last_received = Time.get_ticks_msec()
	client._set_state("connecting")
	check(await until(func(): return client.connection_state == "connected"), "native hello handshake")

func join_guest(client: RelayClient) -> void:
	await connect_local(client, server.connection.get_local_port())
	client.join_room(host.room.code, "退出回归玩家")
	check(await until(func(): return client.owner_id == 1 and not client.room.is_empty()), "guest joins actual room")

func make_lobby() -> Node3D:
	var lobby: Node3D = load("res://scenes/lobby.tscn").instantiate()
	lobby.set_script(TestLobby)
	root.add_child(lobby)
	current_scene = lobby
	return lobby

func _run() -> void:
	session = root.get_node("Session")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "--leave-child" in args:
		await run_child(args)
		return
	server = JimuRelayServer.new()
	server.connection = ENetConnection.new()
	check(server.connection.create_host_bound("127.0.0.1", 0, 16, NetworkProtocol.CHANNEL_COUNT) == OK, "local relay socket")
	server.running = true
	root.add_child(server)
	host = RelayClient.new()
	root.add_child(host)
	await connect_local(host, server.connection.get_local_port())
	host.create_room("1v1", "退出回归房主")
	check(await until(func(): return not host.room.is_empty()), "host creates actual room")
	var guest: RelayClient = session.relay
	await join_guest(guest)
	var lobby := make_lobby()
	lobby._on_open_multiplayer()
	# Exercise the original failing call chain, not a synthetic send/flush pair.
	lobby._on_close_multiplayer()
	check(guest.connection_state == "disconnected" and guest.owner_id == -1, "panel closes without waiting for transport")
	check(await until(func(): return host.room.slots[1].kind == "open"), "actual panel close frees guest seat")
	check(await until(func(): return guest._closing_transports.is_empty()), "acknowledged leave retires old transport")
	check(not lobby.get_node("%OnlinePanel").visible, "panel stays closed after late room replies")

	await join_guest(guest)
	lobby._on_open_sandbox()
	check(await until(func(): return host.room.slots[1].kind == "open"), "actual offline mode switch frees guest seat")
	check(await until(func(): return not session.transition.busy), "scene transition completes independently")
	check(current_scene.scene_file_path == "res://scenes/sandbox.tscn", "offline destination opens")

	await join_guest(guest)
	server.set_process(false)
	guest.leave_room()
	guest.disconnect_relay()
	await create_timer(0.25).timeout
	check(guest._closing_transports.size() == 1, "unacknowledged leave retains transport for retransmission")
	server.set_process(true)
	check(await until(func(): return host.room.slots[1].kind == "open"), "delayed server receives reliable leave")
	check(await until(func(): return guest._closing_transports.is_empty()), "delayed acknowledgement completes disconnect")

	await join_guest(guest)
	guest.disconnect_relay()
	# A replacement transport must not destroy the previous transport's leave.
	await connect_local(guest, server.connection.get_local_port())
	check(await until(func(): return host.room.slots[1].kind == "open"), "immediate reconnect preserves previous leave")
	check(guest.connection_state == "connected" and guest.owner_id == -1, "old replies cannot restore membership")
	guest.join_room(host.room.code)
	check(await until(func(): return guest.owner_id == 1), "new connection can reclaim seat")
	guest.leave_room()
	check(await until(func(): return host.room.slots[1].kind == "open"), "leave without disconnect preserves usable connection")
	guest.join_room(host.room.code)
	check(await until(func(): return guest.owner_id == 1), "same connection rejoins")
	guest.disconnect_relay()
	check(await until(func(): return host.room.slots[1].kind == "open"), "rejoined room also leaves on disconnect")

	for exit_path: String in ["button", "window"]:
		var child_args := PackedStringArray(["--headless", "--audio-driver", "Dummy", "--path", ProjectSettings.globalize_path("res://"),
			"--log-file", ProjectSettings.globalize_path("res://.local/fix-transport-child-" + exit_path + ".log"),
			"--script", "res://tests/network_leave_test.gd", "--", "--leave-child", str(server.connection.get_local_port()), host.room.code, exit_path])
		var pid: int = OS.create_process(OS.get_executable_path(), child_args, false)
		check(pid > 0, exit_path + " child starts")
		if pid <= 0:
			continue
		child_pids.append(pid)
		print("NETWORK_LEAVE_CHILD_PID ", pid)
		check(await until(func(): return host.room.slots[1].kind == "human", 12000), exit_path + " child joins")
		check(await until(func(): return not OS.is_process_running(pid), 10000), exit_path + " process exits within bound")
		check(await until(func(): return host.room.slots[1].kind == "open"), exit_path + " application exit frees seat")

	var old_code: String = host.room.code
	host.leave_room()
	host.disconnect_relay()
	check(await until(func(): return not server.rooms.has(old_code)), "host leave immediately closes room")
	check(await until(func(): return host._closing_transports.is_empty()), "host transport finishes")
	# A vanished server must not retain sockets indefinitely or retry membership.
	await connect_local(guest, server.connection.get_local_port())
	guest.create_room("1v1")
	check(await until(func(): return guest.is_host), "timeout fixture creates room")
	server.stop()
	guest.disconnect_relay()
	var timeout_started: int = Time.get_ticks_msec()
	check(await until(func(): return guest._closing_transports.is_empty(), 4000), "unreachable server is bounded")
	check(Time.get_ticks_msec() - timeout_started < 3500 and guest._retry_at == 0, "active leave never starts reconnect")
	for pid: int in child_pids:
		if OS.is_process_running(pid):
			OS.kill(pid)
	server.queue_free()
	host.queue_free()
	print("NETWORK_LEAVE_RESULTS ", JSON.stringify({"checks": checks, "failed": failures.size(), "failures": failures}))
	quit(0 if failures.is_empty() else 1)

func run_child(args: PackedStringArray) -> void:
	var index: int = args.find("--leave-child")
	await connect_local(session.relay, int(args[index + 1]))
	session.relay.join_room(args[index + 2], "退出子进程")
	if not await until(func(): return session.relay.owner_id == 1 and not session.relay.room.is_empty()):
		quit(1)
		return
	var lobby := make_lobby()
	# Give the supervising server a frame to observe the occupied seat.
	await create_timer(0.1).timeout
	if args[index + 3] == "button":
		lobby._on_quit_game()
	else:
		# Lobby auto_accept_quit takes this same SceneTree shutdown path on X/Alt-F4.
		quit()
