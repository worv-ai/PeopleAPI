# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
import carb
import omni.ext
import omni.kit.app
import omni.kit.commands
import omni.usd
from omni.anim.people_api.scripts.custom_command.command_manager import CustomCommandManager
from pxr import Sdf

_extension_instance = None
_ext_id = None
_ext_path = None


def get_instance():
    return _extension_instance


def get_ext_id():
    return _ext_id


def get_ext_path():
    return _ext_path


def add_dynamic_obstacle_behavior_script(prim_path):
    carb.log_info(f"[OAP] Adding dynamic obstacle behavior script to {prim_path}")
    script_path = (
        omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module("omni.anim.people_api")
        + "/omni/anim/people_api/scripts/dynamic_obstacle.py"
    )

    stage = omni.usd.get_context().get_stage()
    prim = stage.GetPrimAtPath(prim_path)

    omni.kit.commands.execute("ApplyScriptingAPICommand", paths=[Sdf.Path(prim_path)])
    attr = prim.GetAttribute("omni:scripting:scripts")
    script_list_usd = attr.Get()
    script_list = [r"{}".format(script_path)]

    if script_list_usd:
        for script_path in script_list_usd:
            script_list.append(script_path)

    attr.Set(script_list)


class Main(omni.ext.IExt):
    def on_startup(self, ext_id):
        carb.log_info("[omni.anim.people_api] startup")
        global _extension_instance
        _extension_instance = self
        global _ext_id
        _ext_id = ext_id
        global _ext_path
        _ext_path = omni.kit.app.get_app().get_extension_manager().get_extension_path(ext_id)
        # Custom command manager
        self._cmd_manager = CustomCommandManager(_ext_path)
        self._cmd_manager.startup()

    def on_shutdown(self):
        carb.log_info("[omni.anim.people_api] shutdown")
        global _extension_instance
        _extension_instance = None
        global _ext_id
        _ext_id = None
        global _ext_path
        _ext_path = None

        self._cmd_manager.shutdown()
        self._cmd_manager = None

    def get_custom_command_manager(self):
        return self._cmd_manager
