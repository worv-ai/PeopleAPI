from ..utils import Utils
from typing import Any
from .base_command import Command
import carb


class GoToSection(Command):
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
            target_section_name = command_dict.get("Target_Section_Name")
            # check whether target navigation area exist
            if Utils.get_navmesh_area_index(target_section_name) == -1:
                carb.log_warn("The area is not found")
                return False
            # check whether target area is accessible.
            if (
                Utils.get_accessible_point_within_area(
                    area_name=target_section_name, character_position=target_character_pos, max_attempts=100
                )
                is None
            ):
                carb.log_warn("The area is not accessible")
                return False
            return True
        except ImportError as e:
            carb.log_warn(f"failing due to import error in gotosection: {e}")
            return False

    @classmethod
    def set_command_description_usage(cls):
        """set command descriptions"""
        super().set_command_description_usage()
        cls.command_description = "Moves the character to a target section in the stage."

    @classmethod
    def define_all_parameters(cls):
        """define the placeholder, type and explaination"""
        super().define_all_parameters()
        cls.parameters_info.clear()
        cls.define_parameter(
            name="Character_Name",
            param_type=str,
            length=1,
            description="The name of target character.",
            example_input="Tom",
        )

        cls.define_parameter(
            name="GoToSection",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match.",
            constant_match=True,
            example_input="GoToSection",
        )

        cls.define_parameter(
            name="Target_Section_Name",
            param_type=str,
            length=1,
            description="The name of the target section in the stage.",
            example_input="Aisle",
        )
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_name = "GoToSection"
        self.section_name = self.command[1]
        self.character_random_id = self.character_name

    def setup(self):
        super().setup()

        if Utils.get_navmesh_area_index(self.section_name) != -1:
            character_pos = Utils.get_character_pos(self.character)
            position = Utils.get_accessible_point_within_area(
                self.section_name, random_id=None, character_position=character_pos
            )
            target_position = [position[0], position[1], position[2]]

            # goto section do not take specific rotation value as setting
            self.character.set_variable("Action", "Walk")
            self.navigation_manager.generate_path([character_pos, target_position], None)
        else:
            # if the section does not exist in current stage's data
            carb.log_error(
                f"character {self.character_name} attempts to access an invalid section {self.section_name}."
            )
        # self.navigation_manager.generate_goto_path(self.command[1:])

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
