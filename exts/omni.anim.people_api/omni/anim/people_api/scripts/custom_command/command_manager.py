import carb
from typing import List
from omni.anim.people_api.scripts.custom_command.defines import (
    CustomCommandTemplate,
    CustomCommand,
    get_anim_prim_name,
)
from omni.metropolis.utils.file_util import JSONFileUtil
from omni.metropolis.utils.carb_util import CarbSettingUtil
from pxr import Sdf, Usd, UsdGeom


class CustomCommandManager:

    CUSTOM_COMMAND_TRACKING_FILE = "/persistent/exts/omni.anim.people_api/custom_command_tracking_file_path"
    CUSTOM_COMMAND_CHANGED_EVENT = "omni.anim.people_api.CUSTOM_COMMAND_CHANGED"

    __instance = None

    @classmethod
    def get_instance(cls):
        # Instance is created during extension start up
        return cls.__instance

    def __init__(self, ext_path):
        if CustomCommandManager.__instance is not None:
            raise RuntimeError("Only one instance of CustomCommandManager is allowed")
        CustomCommandManager.__instance = self
        self._ext_path = ext_path
        self._default_json_path = f"{self._ext_path}/data/custom_command_tracking.json"
        # Json file that stores all custom commands links.
        self._tracking_file_path = ""
        self._commands: List[CustomCommand] = []  # CustomCommand loaded.
        self._stage = None  # Ghost stage to load all anim usd.

    def startup(self):
        self._setup_stage()
        self.load_entry_tracking_file()

    def shutdown(self):
        self._stage = None
        CustomCommandManager.__instance = None

    def register_custom_command_changed_callback(self, on_event: callable):
        return carb.eventdispatcher.get_eventdispatcher().observe_event(
            event_name=CustomCommandManager.CUSTOM_COMMAND_CHANGED_EVENT,
            on_event=on_event,
            observer_name="omni/anim/people_api/ON_CUSTOM_COMMAND_CHANGED",
        )

    def get_tracking_file_path(self):
        return self._tracking_file_path

    def _setup_stage(self):
        self._stage = Usd.Stage.CreateInMemory()
        default_prim = UsdGeom.Xform.Define(self._stage, Sdf.Path("/World")).GetPrim()
        self._stage.SetDefaultPrim(default_prim)

    def _load_anim_to_stage(self, anim_path):
        prim_name = get_anim_prim_name(anim_path)
        prim = UsdGeom.Xform.Define(self._stage, Sdf.Path(f"/World/{prim_name}")).GetPrim()
        prim.GetPayloads().AddPayload(assetPath=anim_path)
        # Load basic attributes
        attr_name = prim.GetAttribute("CustomCommandName")
        attr_template = prim.GetAttribute("CustomCommandTemplate")
        attr_start_time = prim.GetAttribute("CustomCommandAnimStartTime")
        attr_end_time = prim.GetAttribute("CustomCommandAnimEndTime")
        attr_loop = prim.GetAttribute("CustomCommandAnimLoop")
        attr_backwards = prim.GetAttribute("CustomCommandAnimBackwards")
        # Temp error checking before USD schema
        if not (attr_name.IsValid() and attr_template.IsValid()):
            carb.log_error(
                f"Animation USD {anim_path} misses custom command attributes."
                "\nRequired attributes: 'CustomCommandName', 'CustomCommandTemplate'"
            )
            return None
        name = attr_name.Get()
        template = attr_template.Get()
        start_time = attr_start_time.Get()
        end_time = attr_end_time.Get()
        loop = attr_loop.Get()
        backwards = attr_backwards.Get()
        if name is None:
            carb.log_error(f"Animation USD {anim_path} has empty attribute CustomCommandName.")
            return None
        if template is None:
            carb.log_error(f"Animation USD {anim_path} has empty attribute CustomCommandTemplate.")
            return None
        cmd = CustomCommand(
            anim_path=anim_path,
            name=name,
            template=CustomCommandTemplate(template),
        )
        if start_time is not None:
            cmd.start_time = start_time
        if end_time is not None:
            cmd.end_time = end_time
        if loop is not None:
            cmd.loop = loop
        if backwards is not None:
            cmd.backwards = backwards
        # Unique attributes for different templates
        if cmd.template == CustomCommandTemplate.GOTO_BLEND:
            attr_filter_joint = prim.GetAttribute("CustomCommandFilterJoint")
            if attr_filter_joint.IsValid():
                cmd.filter_joint = attr_filter_joint.Get()
        # Randomization attribute
        if cmd.template == CustomCommandTemplate.TIMING or cmd.template == CustomCommandTemplate.TIMING_TO_OBJECT:
            cmd.min_random_time = prim.GetAttribute("CustomCommandRandomMinTime").Get()
            cmd.max_random_time = prim.GetAttribute("CustomCommandRandomMaxTime").Get()
            if cmd.template == CustomCommandTemplate.TIMING_TO_OBJECT:
                cmd.interact_object_filter = prim.GetAttribute("CustomCommandInteractObjectFilter").Get()
        # Unload prim after info is extracted
        self._stage.RemovePrim(prim.GetPrimPath())
        return cmd

    def load_entry_tracking_file(self):
        file_path = CarbSettingUtil.get_value_by_key(
            key=CustomCommandManager.CUSTOM_COMMAND_TRACKING_FILE,
            fallback_value=self._default_json_path,
            override_setting=True,
        )
        self.load_tracking_file(file_path)

    def load_tracking_file(self, json_file_path):
        self._commands.clear()
        self._tracking_file_path = json_file_path
        CarbSettingUtil.set_value_by_key(
            key=CustomCommandManager.CUSTOM_COMMAND_TRACKING_FILE, new_value=self._tracking_file_path
        )
        json_data = JSONFileUtil.load_from_file(json_file_path)
        if not json_data:
            carb.log_error("Loading custom commands json fails.")
            return
        if "animations" not in json_data:
            carb.log_error(f"Unable to find 'animations' from {json_file_path}, loading custom commands fails.")
            return
        animations_data = json_data["animations"]
        for anim_path in animations_data:
            self.add_custom_command(anim_path)

    def save_tracking_file(self):
        if not self._tracking_file_path:
            carb.log_error("Custom commands json is not loaded. Saving custom commands fails.")
            return
        data = {}
        data["animations"] = []
        for cmd in self._commands:
            data["animations"].append(cmd.anim_path)
        if JSONFileUtil.write_to_file(self._tracking_file_path, data):
            carb.log_info("Custom Command Tracking File is saved.")

    def add_custom_command(self, anim_path):
        if self.is_custom_command_anim_exist(anim_path):
            carb.log_warn("Animation USD is already in the list.")
            return False
        item = self._load_anim_to_stage(anim_path)
        if self.is_custom_command_name_exist(item.name):
            carb.log_warn("Custom command '{item.name}' is already in the list.")
            return False
        self._commands.append(item)
        carb.eventdispatcher.get_eventdispatcher().dispatch_event(
            event_name=CustomCommandManager.CUSTOM_COMMAND_CHANGED_EVENT, payload={}
        )
        return True

    def remove_custom_command(self, anim_path):
        item_to_remove = None
        for item in self._commands:
            if item.anim_path == anim_path:
                item_to_remove = item
                break
        if item_to_remove:
            self._commands.remove(item_to_remove)
            carb.log_info("Command {} has been removed:".format(str(item_to_remove.name)))
            carb.eventdispatcher.get_eventdispatcher().dispatch_event(
                event_name=CustomCommandManager.CUSTOM_COMMAND_CHANGED_EVENT, payload={}
            )
            return True
        return False

    def is_custom_command_name_exist(self, name):
        for item in self._commands:
            if name == item.name:
                return True
        return False

    def is_custom_command_anim_exist(self, anim_path):
        for item in self._commands:
            if anim_path == item.anim_path:
                return True
        return False

    def get_all_custom_commands(self):
        return self._commands

    def get_custom_command_by_name(self, name):
        for item in self._commands:
            if name == item.name:
                return item
        return None

    def get_all_custom_command_names(self):
        names = []
        for item in self._commands:
            names.append(item.name)
        return names

    def get_latest_command(self):
        return self._commands[-1]

    def get_command_by_anim_path(self, anim_path):
        for item in self._commands:
            if item.anim_path == anim_path:
                return item

    def get_command_template_by_name(self, name):
        command = self.get_custom_command_by_name(name)
        if not command:
            return None
        return command.template
