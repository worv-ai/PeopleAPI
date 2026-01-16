# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from .base_command import Command, MetadataTag


class Idle(Command):
    """
    Command class to stay idle
    """

    @classmethod
    def set_command_description_usage(cls):
        super().set_command_description_usage()
        cls.command_description = "The character stands still for a duration."
        cls.command_usage = "This command could be used to present, thinking, resting or idling behavior."

    @classmethod
    def define_all_parameters(cls):
        super().define_all_parameters()
        """define the placeholder, type and explaination """
        cls.parameters_info.clear()
        cls.define_parameter(
            name="Character_Name",
            param_type=str,
            length=1,
            description="The name of target character",
            example_input="Tom",
        )

        cls.define_parameter(
            name="Idle",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match",
            constant_match=True,
            example_input="Idle",
        )

        cls.define_parameter(
            name="Idle_Time",
            param_type=float,
            length=1,
            description="How long (in second) should the character maintain Idle",
            example_input="10",
        )

        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.command) > 1:
            self.duration = float(self.command[1])
        # reset the command name to Idle
        self.command_name = "Idle"

    def setup(self):
        super().setup()
        self.character.set_variable("Action", "None")
        # set the action tag to idle
        self.update_metadata_callback(
            agent_name=self.character_name, data_name=MetadataTag.AgentActionTag, data_value="Idle"
        )

    def update(self, dt):
        return super().update(dt)

    def force_quit_command(self):
        return super().force_quit_command()
