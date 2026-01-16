# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from .base_command import Command, MetadataTag


class LookAround(Command):
    """
    Command class to look around (moving head from left to right).
    """

    @classmethod
    def set_command_description_usage(cls):
        super().set_command_description_usage()
        cls.command_description = "The character stays in place and looks around for a specified duration."
        cls.command_usage = (
            "The command can be used to present movements such as checking, monitoring, or simple interactions"
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
            name="LookAround",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match",
            constant_match=True,
            example_input="LookAround",
        )

        cls.define_parameter(
            name="LookAround_Time",
            param_type=float,
            length=1,
            description="How long (in second) should the character LookAround",
            example_input="13",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.command) > 1:
            self.duration = float(self.command[1])
        self.command_name = "LookAround"

    def setup(self):
        super().setup()
        self.character.set_variable("Action", "None")
        self.character.set_variable("lookaround", 1.0)
        self.update_metadata_callback(
            agent_name=self.character_name, data_value=MetadataTag.AgentActionTag, data_name="LookingAround"
        )

    def exit_command(self):
        self.character.set_variable("lookaround", 0.0)
        return super().exit_command()

    def update(self, dt):
        return super().update(dt)

    def force_quit_command(self):
        self.character.set_variable("lookaround", 0.0)
        return super().force_quit_command()
