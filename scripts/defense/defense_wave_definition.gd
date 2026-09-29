class_name DefenseWaveDefinition
extends Resource
## Authored encounter data, independent from the ten-wave battle lifecycle.
@export var title: String = "敌军来袭"
@export var units: Dictionary[String, int] = {}
@export var clear_reward: int = 100

func roster() -> Array[String]:
	var result: Array[String] = []
	# Interleave troop types so the opening of a wave already shows its composition.
	var remaining := units.duplicate()
	while not remaining.is_empty():
		for kind: String in remaining.keys():
			if remaining[kind] > 0:
				result.append(kind)
			remaining[kind] -= 1
			if remaining[kind] <= 0:
				remaining.erase(kind)
	return result
