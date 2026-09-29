class_name DefenseScenarioDefinition
extends Resource
## Future encounters can replace this resource without changing the RTS economy.
@export var preparation_seconds: float = 120.0
@export var intermission_seconds: float = 45.0
@export var starting_gold: int = 520
@export var spawn_interval: float = 0.6
@export_range(0.0, 0.8) var maximum_supply_reduction: float = 0.5
@export var waves: Array[DefenseWaveDefinition] = []
