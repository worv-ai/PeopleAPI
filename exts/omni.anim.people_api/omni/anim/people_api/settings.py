PERSISTENT_SETTINGS_PREFIX = "/persistent"


class PeopleSettings:
    COMMAND_FILE_PATH = "/exts/omni.anim.people_api/command_settings/command_file_path"
    ROBOT_COMMAND_FILE_PATH = "/exts/omni.anim.people_api/command_settings/robot_command_file_path"
    NUMBER_OF_LOOP = "/exts/omni.anim.people_api/command_settings/number_of_loop"
    DYNAMIC_AVOIDANCE_ENABLED = "/exts/omni.anim.people_api/navigation_settings/dynamic_avoidance_enabled"
    NAVMESH_ENABLED = "/exts/omni.anim.people_api/navigation_settings/navmesh_enabled"
    IDLE_DURATION_MIN = "/exts/omni.anim.people_api/command_settings/idle/duration/min"
    IDLE_DURATION_MAX = "/exts/omni.anim.people_api/command_settings/idle/duration/max"
    CHARACTER_ASSETS_PATH = (
        f"{PERSISTENT_SETTINGS_PREFIX}/exts/omni.anim.people_api/asset_settings/character_assets_path"
    )
    BEHAVIOR_SCRIPT_PATH = (
        f"{PERSISTENT_SETTINGS_PREFIX}/exts/omni.anim.people_api/behavior_script_settings/behavior_script_path"
    )
    CHARACTER_PRIM_PATH = f"{PERSISTENT_SETTINGS_PREFIX}/exts/omni.anim.people_api/character_prim_path"
    CACHE_ACTION_METADATA = "/exts/omni.anim.people_api/cache_action_metadata"
    CHARACTER_FINAL_TARGET_DISTANCE = "/exts/omni.anim.people_api/final_target_distance"


class AgentEvent:
    AgentRegistered = "omni.anim.people/REGISTER_AGENT"
    CommandStartEvent = "omni.anim.people/CommandStartEvent"
    CommandEndEvent = "omni.anim.people/CommandEndEvent"
    MetadataUpdateEvent = "omni.anim.people/MetadataUpdateEvent"


class MetadataTag:
    AgentActionTag = "action_tag"


class CommandID:
    auto_prefix = "Auto"
    cutomized_command = "Cust"


class ConstantAddress:
    command_folder = "omni/anim/people_api/scripts"


class TaskStatus:
    interrupted = "interrupted"
    failed = "failed"
    default = "default"
