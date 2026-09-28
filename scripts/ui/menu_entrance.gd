extends Node
## Scene-authored menu choreography. Sections stay hidden beneath a transition,
## then enter after its completed signal instead of animating behind the sheet.

@export var sections: Array[NodePath] = []
@export_range(0.0, 0.1) var stagger: float = 0.045

var started := false
var _controls: Array[Control] = []
var _alphas: PackedFloat32Array = []

func _ready() -> void:
	for path: NodePath in sections:
		var control: Control = get_parent().get_node(path)
		_controls.append(control)
		_alphas.append(control.modulate.a)
		control.modulate.a = 0.0
	_begin.call_deferred()

func _begin() -> void:
	# A deferred scene change can detach this menu before this callback runs.
	if not is_inside_tree():
		return
	# Containers reset child scale during initial layout (Control documentation).
	# A node-bound connection also disappears if rapid navigation frees this menu.
	get_tree().process_frame.connect(_after_layout, CONNECT_ONE_SHOT)

func _after_layout() -> void:
	var transition: UITransition = get_node("/root/Session/Transition")
	if transition.busy:
		transition.completed.connect(_play, CONNECT_ONE_SHOT)
	else:
		_play()

func _play() -> void:
	started = true
	for index: int in _controls.size():
		var control := _controls[index]
		control.modulate.a = _alphas[index]
		UIMotion.reveal_menu(control, Vector2(0, 18), index * stagger)
