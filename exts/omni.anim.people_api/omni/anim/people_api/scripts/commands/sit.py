# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import carb
import omni.usd
from omni.metropolis.utils.carb_util import CarbUtil
from ..interactable_object_helper import InteractableObjectHelper
from omni.anim.people_api.settings import TaskStatus

from ..utils import Utils
from .base_command import Command, MetadataTag
from typing import Any


class Sit(Command):
    """
    Command class that implements the sit command.
    """

    @classmethod
    def is_valid_command(
        cls, command: list[str] | str, target_character_pos: Any = None, target_character_name: str | None = None
    ):
        """check whether the command is correct"""
        command_dict = cls.validate_command_format(command=command)
        carb.log_warn("This is the command dict" + str(command_dict))
        if not command_dict:
            return False
        try:
            target_object_path = command_dict.get("Target_Object_Path")
            stage = omni.usd.get_context().get_stage()
            object_prim = stage.GetPrimAtPath(target_object_path)
            # target prim either does not exist or does not activated
            if not (object_prim and object_prim.IsValid() and object_prim.IsActive()):
                return False

            # when it comes to the agent generation:
            # we require each object has preset walk_to_offset and interactable_offset
            # Check walk_to_offset prim can prevent agent from sitting on some wired objects.
            walk_to_offset_prim = stage.GetPrimAtPath(f"{target_object_path}/walk_to_offset")
            if not walk_to_offset_prim.IsValid():
                carb.log_warn(
                    f"No 'walk_to_offset' under prim '{target_object_path}', will use prim's transform instead."
                )
                return False
            target_pos_raw = omni.usd.get_world_transform_matrix(walk_to_offset_prim).ExtractTranslation()
            target_pos = carb.Float3(target_pos_raw[0], target_pos_raw[1], 0)
            destination_pos = Utils.get_closest_navmesh_point(target_pos)
            if not Utils.accessible_navmesh_point(point=destination_pos, character_position=target_character_pos):
                carb.log_warn(f"No 'walk_to_offset' under prim '{target_object_path}', is not accessible")
                return False

            return True
        except ImportError as e:
            carb.log_warn(f"failing due to import error in sit: {e}")
            return False

    @classmethod
    def set_command_description_usage(cls):
        """set command descriptions"""
        super().set_command_description_usage()
        cls.command_description = (
            "Moves the character to a target object in the stage, "
            "then let the character sit on the object for a specified duration."
        )
        cls.command_usage = (
            "Navigate the character to a target object, then let the character sit on the chair. "
            "Can be used to show behaviors such as resting or waiting."
        )

    @classmethod
    def define_all_parameters(cls):
        """define the placeholder, type and explaination"""
        super().define_all_parameters()
        cls.parameters_info.clear()
        cls.define_parameter(
            name="Character_Name",
            param_type=str,
            length=1,
            description="The name of target character",
            example_input="Tom",
        )

        cls.define_parameter(
            name="Sit",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match",
            constant_match=True,
            example_input="Sit",
        )

        cls.define_parameter(
            name="Target_Object_Path",
            param_type=str,
            length=1,
            description="The usd prim path of the target object that you want the character to Sit on",
            example_input="/World/Chair",
        )

        cls.define_parameter(
            name="Sit_Time",
            param_type=float,
            length=1,
            description="How long should the character sit on the object",
            example_input="10",
        )
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage = omni.usd.get_context().get_stage()
        self.seat_prim = self.stage.GetPrimAtPath(self.command[1])
        if len(self.command) > 2:
            self.duration = float(self.command[2])
        self.sit_time = 0
        self.current_action = None
        self.command_name = "Sit"

    def __del__(self):
        if self.seat_prim is not None:
            InteractableObjectHelper.remove_owner(target_prim=self.seat_prim, agent_name=self.character_name)

    def setup(self):
        super().setup()
        (
            self.walk_to_pos,
            self.walk_to_rot,
            self.interact_pos,
            self.interact_rot,
        ) = InteractableObjectHelper.get_interact_prim_offsets(self.stage, self.seat_prim)
        character_pos = Utils.get_character_pos(self.character)
        self.navigation_manager.generate_path([character_pos, self.walk_to_pos], self.walk_to_rot)
        self.current_action = "walk"
        self._char_lerp_t = 0
        self.stand_animation_time = 0

    def force_quit_command(self):
        if self.seat_prim is not None:
            InteractableObjectHelper.remove_owner(target_prim=self.seat_prim, agent_name=self.character_name)

        if self.current_action == "walk" or self.current_action is None:
            return super().force_quit_command()

        if self.current_action == "sit":
            self.character.set_variable("Action", "Sit")
            self.character.set_variable("Action", "None")
            self._char_lerp_t = 0.0
            self.current_action = "stand"
            self.update_metadata_callback(
                agent_name=self.character_name, data_name=MetadataTag.AgentActionTag, data_value="StandingUp"
            )
            return

    def update(self, dt):
        if self.current_action == "walk" or self.current_action is None:
            if self.walk(dt):
                # NOTE: enable the command it self to decide whether it is conduct successfully.
                # if we found the object is not interactable
                if not InteractableObjectHelper.is_object_interactable(self.seat_prim):
                    # check whether the object has already been occupied
                    # if so, break current command and return false
                    carb.log_warn("Fail to sit... Object is not interactable now")
                    self.command_status = TaskStatus.failed
                    self.force_quit_command()

                InteractableObjectHelper.add_owner(target_prim=self.seat_prim, agent_name=self.character_name)
                self.current_action = "sit"
                self._char_start_pos, self._char_start_rot = Utils.get_character_transform(self.character)
                self.update_metadata_callback(
                    agent_name=self.character_name, data_name=MetadataTag.AgentActionTag, data_value="Sitting"
                )

        elif self.current_action == "sit":
            # Start to play sit animation
            # At the same time adjust players's tranlatation to fit the seat
            self._char_lerp_t = min(self._char_lerp_t + dt, 1.0)
            lerp_pos = CarbUtil.lerp3(self._char_start_pos, self.interact_pos, self._char_lerp_t)
            self.character.set_world_transform(lerp_pos, self._char_start_rot)
            self.character.set_variable("Action", "Sit")
            self.sit_time += dt
            if self.sit_time > self.duration:
                self.character.set_variable("Action", "None")
                self._char_lerp_t = 0.0
                self.current_action = "stand"
                self.update_metadata_callback(
                    agent_name=self.character_name, data_name=MetadataTag.AgentActionTag, data_value="StndingUp"
                )
                InteractableObjectHelper.remove_owner(target_prim=self.seat_prim, agent_name=self.character_name)

        elif self.current_action == "stand":
            if self.stand_animation_time < 1.5:
                # adjust character's position while play "stand" animation
                self._char_lerp_t = min(self._char_lerp_t + dt, 1.0)
                lerp_pos = CarbUtil.lerp3(self.interact_pos, self._char_start_pos, self._char_lerp_t)
                current_pos, current_rot = Utils.get_character_transform(self.character)
                self.character.set_world_transform(lerp_pos, current_rot)
                self.stand_animation_time += dt

            if self.stand_animation_time > 1.5:
                # set character's position to position before the sit animation, enter the idle stage
                current_pos, current_rot = Utils.get_character_transform(self.character)
                self.character.set_world_transform(self._char_start_pos, current_rot)
                return self.exit_command()
