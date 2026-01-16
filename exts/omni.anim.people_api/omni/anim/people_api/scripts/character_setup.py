# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from typing import Optional
import logging
import math
import random
import uuid
from collections import UserDict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import carb
import omni.anim.graph.core as ag
import omni.anim.navigation.core as nav
import omni.kit.commands
import omni.kit.app
import omni.usd
import omni.client
from omni.anim.people_api import PeopleSettings
from omni.anim.people_api.scripts.custom_command.populate_anim_graph import populate_anim_graph
from omni.anim.people_api.scripts.global_character_position_manager import GlobalCharacterPositionManager
from isaacsim.core.api import SimulationContext
from isaacsim.core.utils import prims
from isaacsim.storage.native import get_assets_root_path
from omni.kit.scripting import ScriptManager
from pxr import Gf, Sdf, UsdGeom
from pydantic import BaseModel, ValidationError

from omni.anim.people_api.scripts.character_behavior_base import CharacterSeedRegistry
from .utils import Utils

logger = logging.getLogger(__name__)


class ObservableDict(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._modified = False

    def __setitem__(self, key, value):
        if self.data.get(key) != value:
            self._modified = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._modified = True
        super().__delitem__(key)

    def clear_modified(self):
        self._modified = False

    def is_modified(self):
        return self._modified


@dataclass
class CharacterBehaviorData:
    name: str
    script_path: str


class CharacterBehavior(Enum):
    RANDOM_GOTO = CharacterBehaviorData(
        "RandomGoto",
        omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)
        + "/omni/anim/people_api/scripts/character_behavior_random_goto.py",
    )
    RANDOM_IDLE = CharacterBehaviorData(
        "RandomIdle",
        omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)
        + "/omni/anim/people_api/scripts/character_behavior_random_idle.py",
    )
    DYNAMIC_OBSTACLE = CharacterBehaviorData(
        "DynamicObstacle",
        omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)
        + "/omni/anim/people_api/scripts/dynamic_obstacle.py",
    )

    @staticmethod
    def from_name(name: str):
        for behavior in CharacterBehavior:
            if behavior.value.name == name:
                return behavior
        return None


class CharacterData(BaseModel):
    usd_path: str
    behavior: str
    position: list[float]
    rotation: float
    random_seed: int
    nav_random_seed: int


class CharacterState(BaseModel):
    data: list[CharacterData]


class CharacterSetup:
    """
    Character setup class that handles character initialization, loading, and removal.
    Unlike the 'omni.anim.people' extension, this class exposes the character setup as an API,
    not an UI.
    """

    def __init__(
        self,
        robot_prim_path: str,
        num_characters: int,
        starting_point=(0, 0, 0),
        is_warmup=False,
        seed: Optional[int] = None,
    ):
        self.robot_prim_path = robot_prim_path
        self.starting_point = starting_point
        self.default_biped_usd = "Biped_Setup"
        self.default_biped_asset_name = "biped_demo"
        # Root path of character assets
        self.assets_root_path = ""
        # List to track characters that are available for Spawning.
        self.available_character_list = None
        self.character_data_dict = ObservableDict()
        self.is_imported = False

        self.trigger_state_api_dict = {}
        self.character_manager = GlobalCharacterPositionManager.get_instance()

        self.stage = omni.usd.get_context().get_stage()
        self.inav = nav.acquire_interface()
        self.navmesh = self.inav.get_navmesh()

        self._init_assets()
        if is_warmup:
            num_warmup = len(self._get_character_asset_list())
            self.load_random_characters(num_warmup, CharacterBehavior.RANDOM_IDLE)
            context = SimulationContext.instance()
            for _ in range(100):
                context.step()
            self.remove_characters(list(self.character_data_dict.keys()))
        self.load_random_characters(num_characters, CharacterBehavior.RANDOM_GOTO)

    def shutdown(self):
        self.character_data_dict = None
        self.available_character_list = None

    def get_all_character_pos(self):
        all_character_pos = []
        for prim_path in self.character_manager.get_all_managed_characters():
            if str(prim_path).startswith(self.character_root_prim_path):
                character = ag.get_character(prim_path)
                all_character_pos.append(Utils.get_character_transform(character))
        return all_character_pos

    def get_collision_info(self):
        collision_info = []
        for character_name, (character_prim, trigger_state_api_list) in self.trigger_state_api_dict.items():
            is_collided = False
            for trigger_state_api in trigger_state_api_list:
                trigger_colliders = trigger_state_api.GetTriggeredCollisionsRel().GetTargets()
                for trigger_collider in trigger_colliders:
                    if str(trigger_collider).startswith(self.robot_prim_path):
                        is_collided = True
                        break
                if is_collided:
                    break
            if is_collided:
                character = ag.get_character(character_prim)
                position = Utils.get_character_pos(character)
                collision_info.append((character_prim, list(position)))
        return collision_info

    def load_random_characters(self, num_characters: int, character_behavior: CharacterBehavior):
        if self.is_imported:
            self.remove_characters(list(self.character_data_dict.keys()))
            self.is_imported = False

        random_position_list = self._get_random_position_list(num_characters)
        character_name_list = self._init_characters(random_position_list, character_behavior)
        self._setup_characters(character_name_list, character_behavior)
        return character_name_list

    def load_characters(self, position_list: list[tuple[float, float]], character_behavior: CharacterBehavior):
        if self.is_imported:
            self.remove_characters(list(self.character_data_dict.keys()))
            self.is_imported = False

        position_list = self._convert_xy_to_xyz(position_list)
        character_name_list = self._init_characters(position_list, character_behavior)
        self._setup_characters(character_name_list, character_behavior)
        return character_name_list

    def export_character_state(self, check_modified=True) -> str:
        if self.character_data_dict.is_modified() or not check_modified:
            self.character_data_dict.clear_modified()
            character_data_list = list(self.character_data_dict.values())
            return CharacterState(data=character_data_list).model_dump_json()
        return None

    def import_character_state(self, character_state_str: str):
        try:
            character_state = CharacterState.model_validate_json(character_state_str)
        except ValidationError as e:
            logger.error("Failed to import the character state. %s", e)
            return

        self.remove_characters(list(self.character_data_dict.keys()))
        behavior_to_character_name_list = {}
        for character_data in character_state.data:
            while True:
                character_name = f"character_{str(uuid.uuid4()).replace('-', '_')}"
                if character_name not in self.character_data_dict:
                    break
            character_behavior = CharacterBehavior.from_name(character_data.behavior)
            self._init_character(
                character_name,
                character_data.usd_path,
                character_behavior,
                character_data.position,
                character_data.rotation,
                character_data.random_seed,
                character_data.nav_random_seed,
            )
            behavior_to_character_name_list.setdefault(character_behavior, []).append(character_name)
        for behavior, character_name_list in behavior_to_character_name_list.items():
            self._setup_characters(character_name_list, behavior)
        self.is_imported = True

    def _init_assets(self):
        setting_dict = carb.settings.get_settings()
        # Get root assets path from setting, if not set, get the Isaac-Sim asset path
        people_asset_folder = setting_dict.get(PeopleSettings.CHARACTER_ASSETS_PATH)
        character_root_prim_path = setting_dict.get(PeopleSettings.CHARACTER_PRIM_PATH)
        if not character_root_prim_path:
            character_root_prim_path = "/World/Characters"

        if people_asset_folder:
            self.assets_root_path = people_asset_folder
        else:
            root_path = get_assets_root_path()
            if root_path is None:
                carb.log_error("Could not find Isaac Sim assets folder")
                return
            self.assets_root_path = f"{root_path}/Isaac/People/Characters"

        if not self.assets_root_path:
            carb.log_error("Could not find people assets folder")

        result, properties = omni.client.stat(self.assets_root_path)
        if result != omni.client.Result.OK:
            carb.log_error("Could not find people asset folder : " + str(self.assets_root_path))
            return

        if not Sdf.Path.IsValidPathString(character_root_prim_path):
            carb.log_error(str(character_root_prim_path) + " is not a valid character root prim's path")

        if not self.stage.GetPrimAtPath(character_root_prim_path):
            prims.create_prim(character_root_prim_path, "Xform")
        self.character_root_prim_path = character_root_prim_path

        # Reload biped and animations
        if not self.stage.GetPrimAtPath("{}/{}".format(self.character_root_prim_path, self.default_biped_usd)):
            biped_demo_usd = "{}/{}.usd".format(self.assets_root_path, self.default_biped_usd)
            prim = prims.create_prim(
                "{}/{}".format(self.character_root_prim_path, self.default_biped_usd), "Xform", usd_path=biped_demo_usd
            )
            prim.GetAttribute("visibility").Set("invisible")

        self.stage = omni.usd.get_context().get_stage()
        self.anim_graph_prim = None
        for prim in self.stage.Traverse():
            if prim.GetTypeName() == "AnimationGraph":
                self.anim_graph_prim = prim
                break

        if self.anim_graph_prim is None:
            carb.log_warn("Unable to find an animation graph on stage.")
            return

    def _get_character_asset_list(self):
        # List all files in characters directory
        result, folder_list = omni.client.list("{}/".format(self.assets_root_path))

        if result != omni.client.Result.OK:
            carb.log_error("Unable to get character assets from provided asset root path.")
            return

        # Prune items from folder list that are not directories.
        pruned_folder_list = [
            folder.relative_path
            for folder in folder_list
            if (folder.flags & omni.client.ItemFlags.CAN_HAVE_CHILDREN) and not folder.relative_path.startswith(".")
        ]

        if self.default_biped_asset_name in pruned_folder_list:
            pruned_folder_list.remove(self.default_biped_asset_name)
        return pruned_folder_list

    def _get_path_for_character_prim(self, agent_name):
        # Get a list of available character assets
        if not self.available_character_list:
            self.available_character_list = self._get_character_asset_list()
            if not self.available_character_list:
                return
        # Check if a folder with agent_name exists. If exists we load the character, else we load a random character
        agent_folder = "{}/{}".format(self.assets_root_path, agent_name)
        result, properties = omni.client.stat(agent_folder)
        if result == omni.client.Result.OK:
            char_name = agent_name
        else:
            # Pick a random character from available character list
            char_name = random.choice(self.available_character_list)

        # Get the usd present in the character folder
        character_folder = "{}/{}".format(self.assets_root_path, char_name)
        character_usd = self._get_usd_in_folder(character_folder)
        if not character_usd:
            return

        if len(self.available_character_list) != 0 and (char_name in self.available_character_list):
            self.available_character_list.remove(char_name)

        # Return the character name (folder name) and the usd path to the character
        return (char_name, "{}/{}".format(character_folder, character_usd))

    def _get_usd_in_folder(self, character_folder_path):
        result, folder_list = omni.client.list(character_folder_path)

        if result != omni.client.Result.OK:
            carb.log_error("Unable to read character folder path at {}".format(character_folder_path))
            return

        for item in folder_list:
            if item.relative_path.endswith(".usd"):
                return item.relative_path

        carb.log_error("Unable to file a .usd file in {} character folder".format(character_folder_path))

    def remove_characters(self, character_name_list: list[str]):
        if character_name_list is None:
            return
        character_root_prim_path = Path(self.character_root_prim_path)
        seed_registry = CharacterSeedRegistry.get_instance()

        for character_name in character_name_list:
            character_path = str(character_root_prim_path / character_name)
            if prims.is_prim_path_valid(character_path):
                prims.delete_prim(character_path)
            if character_name in self.trigger_state_api_dict:
                del self.trigger_state_api_dict[character_name]
            if character_name in self.character_data_dict:
                del self.character_data_dict[character_name]
            # Remove seed from registry
            seed_registry._seeds.pop(character_name, None)

        script_manager = ScriptManager.get_instance()
        script_manager._unload_all_scripts()

    def _get_random_position_list(self, num_characters: int):
        position_list = []
        for _ in range(num_characters):
            while True:
                random_position = carb.Float3(0, 0, 0)
                if not self.navmesh.query_random_point("test", random_position):
                    continue
                path = self.navmesh.query_shortest_path(random_position, self.starting_point)
                if path is not None:
                    logger.debug(
                        "Successfully generated the character's initial position. %s",
                        random_position,
                    )
                    break
                else:
                    logger.debug(
                        "Failed to generate the character's initial position. %s",
                        random_position,
                    )
            position_list.append(list(random_position))
        return position_list

    def _convert_xy_to_xyz(self, position_list: list[tuple[float, float]], radius: float = 1.5):
        result = []
        for position in position_list:
            height = 0.0
            while True:
                random_angle = random.uniform(0, 2 * math.pi)
                random_radius = radius * math.sqrt(random.uniform(0, 1))
                point = (
                    position[0] + random_radius * math.cos(random_angle),
                    position[1] + random_radius * math.sin(random_angle),
                    height,
                )
                path = self.navmesh.query_shortest_path(point, self.starting_point)
                if path is not None:
                    result.append(list(path.get_points()[0]))
                    break
                if 10.0 < height:
                    break
                height = -height
                if height >= 0:
                    height += 0.1
        return result

    def _init_characters(self, position_list: list[list[float]], character_behavior: CharacterBehavior):
        character_name_list = []
        # Reload character assets
        for position in position_list:
            while True:
                character_name = f"character_{str(uuid.uuid4()).replace('-', '_')}"
                if character_name not in self.character_data_dict:
                    break
            char_name, char_usd_file = self._get_path_for_character_prim(character_name)
            if char_usd_file:
                # Store agent names for deletion
                character_name_list.append(character_name)

                random_rotation = random.uniform(0, 360)
                random_seed = random.randint(0, 2**32 - 1)
                nav_random_seed = random.randint(0, 2**32 - 1)
                self._init_character(
                    character_name,
                    char_usd_file,
                    character_behavior,
                    position,
                    random_rotation,
                    random_seed,
                    nav_random_seed,
                )
            else:
                raise ValueError("Unable to load character assets")
        return character_name_list

    def _init_character(
        self,
        character_name: str,
        char_usd_file: str,
        character_behavior: CharacterBehavior,
        position: list[float],
        rotation: float,
        random_seed: int,
        nav_random_seed: int,
    ):
        prim = prims.create_prim(
            f"{self.character_root_prim_path}/{character_name}",
            "Xform",
            usd_path=char_usd_file,
        )
        prim.GetAttribute("xformOp:translate").Set(Gf.Vec3d(*position))
        if isinstance(prim.GetAttribute("xformOp:orient").Get(), Gf.Quatf):
            prim.GetAttribute("xformOp:orient").Set(
                Gf.Quatf(Gf.Rotation(Gf.Vec3d(0, 0, 1), float(rotation)).GetQuat())
            )
        else:
            prim.GetAttribute("xformOp:orient").Set(Gf.Rotation(Gf.Vec3d(0, 0, 1), float(rotation)).GetQuat())

        self.inav.set_random_seed(character_name, nav_random_seed)

        # Register the seed in the registry for behavior scripts to access
        seed_registry = CharacterSeedRegistry.get_instance()
        seed_registry.set_seed(character_name, random_seed)

        self.character_data_dict[character_name] = CharacterData(
            usd_path=char_usd_file,
            behavior=character_behavior.value.name,
            position=position,
            rotation=rotation,
            random_seed=random_seed,
            nav_random_seed=nav_random_seed,
        )

    def _setup_characters(self, character_name_list: list[str], character_behavior: CharacterBehavior):
        for prim in self.stage.Traverse():
            if (
                prim.GetTypeName() == "SkelRoot"
                and UsdGeom.Imageable(prim).ComputeVisibility() != UsdGeom.Tokens.invisible
            ):
                is_target = None
                for character_name in character_name_list:
                    if character_name in str(prim.GetPrimPath()):
                        is_target = character_name
                        break
                if is_target is not None:
                    # Remove animation graph attribute if it exists
                    omni.kit.commands.execute("RemoveAnimationGraphAPICommand", paths=[Sdf.Path(prim.GetPrimPath())])

                    # Apply animation graph api on skeleton root
                    omni.kit.commands.execute(
                        "ApplyAnimationGraphAPICommand",
                        paths=[Sdf.Path(prim.GetPrimPath())],
                        animation_graph_path=Sdf.Path(self.anim_graph_prim.GetPrimPath()),
                    )
                    # Apply command api
                    omni.kit.commands.execute("ApplyScriptingAPICommand", paths=[Sdf.Path(prim.GetPrimPath())])
                    attr = prim.GetAttribute("omni:scripting:scripts")

                    setting_dict = carb.settings.get_settings()
                    ext_path = setting_dict.get(PeopleSettings.BEHAVIOR_SCRIPT_PATH)
                    if not ext_path:
                        ext_path = character_behavior.value.script_path
                    attr.Set([r"{}".format(ext_path)])
                    trigger_state_api_list = Utils.add_colliders(prim)
                    self.trigger_state_api_dict[is_target] = str(prim.GetPrimPath()), trigger_state_api_list
                    Utils.add_rigid_body_dynamics(prim)

        # Custom command
        populate_anim_graph()
