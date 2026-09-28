class_name UserDataMigration
extends RefCounted
## Import the former combined game's preferences and roguelike checkpoint once.
## Existing Block-RTS files win; source data, logs and network sessions are untouched.
const PREVIOUS_PROJECT_DIRECTORY := "积木争霸"
const DATA_FILES: PackedStringArray = ["settings.cfg", "lobby_preferences.cfg", "rogue_run.json"]

static func migrate(previous_directory: String, current_directory: String) -> Error:
	for filename: String in DATA_FILES:
		var source := previous_directory.path_join(filename)
		var destination := current_directory.path_join(filename)
		if FileAccess.file_exists(destination) or not FileAccess.file_exists(source):
			continue
		var error := DirAccess.copy_absolute(source, destination)
		if error != OK:
			return error
	return OK
