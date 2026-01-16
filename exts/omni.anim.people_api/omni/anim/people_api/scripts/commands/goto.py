# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from typing import Any

import carb

from ..utils import Utils
from .base_command import Command


class GoTo(Command):
    """
    Command class to go to a location/locations.
    """

    @classmethod
    def is_valid_command(
        cls, command: list[str] | str, target_character_pos: Any = None, target_character_name: str | None = None
    ):
        """check whether the command is correct"""
        command_dict = cls.validate_command_format(command=command)
        if not command_dict:
            return False
        try:
            target_position = command_dict.get("Target_Position")
            accessible = Utils.accessible_navmesh_point(point=target_position, character_position=target_character_pos)
            return accessible
        except ImportError as e:
            carb.log_warn(f"failing due to import error in goto: {e}")
            return False

    @classmethod
    def set_command_description_usage(cls):
        """set command descriptions"""
        super().set_command_description_usage()
        # cls.command_description = "Moves the agent to a target spot in the stage with defined rotation."
        cls.command_description = None

    @classmethod
    def define_all_parameters(cls):
        """define the placeholder, type and explaination"""
        super().define_all_parameters()
        cls.parameters_info.clear()
        cls.define_parameter(
            name="Agent_Name",
            param_type=str, length=1,
            description="The name of target character",
            example_input="Tom"
        )

        cls.define_parameter(
            name="GoTo",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match",
            constant_match=True,
            example_input="GoTo",
        )

        cls.define_parameter(
            name="Target_Position",
            param_type=list[float],
            length=3,
            description="The x, y, z coordinate of the target position",
            example_input=["10", "11", "0"],
        )

        cls.define_parameter(
            name="Target_Rotation",
            param_type=float,
            length=1,
            description="The degree of character's rotation, if not specified, please input _ as a placeholder",
            example_input="90",
            special_value=tuple([str, "_", 1]),
        )

        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_name = "GoTo"

    def setup(self):
        super().setup()
        self.character.set_variable("Action", "Walk")
        self.navigation_manager.generate_goto_path(self.command[1:])

    def execute(self, dt):
        if self.finished:
            return True

        if not self.is_setup:
            self.setup()
        return self.update(dt)

    def update(self, dt):
        self.time_elapsed += dt
        if self.walk(dt):
            return self.exit_command()

    def force_quit_command(self):
        return super().force_quit_command()
