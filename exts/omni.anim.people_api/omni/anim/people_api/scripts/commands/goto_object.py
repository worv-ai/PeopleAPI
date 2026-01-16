from ..utils import Utils
from omni.metropolis.utils.carb_util import CarbUtil
from typing import Any
from .base_command import Command
import carb
import omni.usd
import math


class GoToObject(Command):
    """
    Command class to go to a location/locations.
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
        # try:
        try:
            target_object_path = command_dict.get("Target_Object_Path")

            stage = omni.usd.get_context().get_stage()
            object_prim = stage.GetPrimAtPath(target_object_path)
            # target prim either does not exist or does not activated
            if not (object_prim and object_prim.IsValid() and object_prim.IsActive()):
                carb.log_warn(
                    "{target_object_path} is not a valid prim in stage".format(
                        target_object_path=target_object_path)
                )
                return False

            accessible_point = Utils.get_closest_accessible_point(
                target_prim=object_prim, character_pos=target_character_pos
            )
            # There is no accessible point nearby the target object:
            if accessible_point is None:
                carb.log_warn(
                    "{target_object_path} is not accessible to {target_character}".format(
                        target_object_path=target_object_path, target_character=target_character_name
                    )
                )
                return False

            return True

        except ImportError as e:
            carb.log_warn(f"command is not valid, error occur: {e}")
            return False

    @classmethod
    def set_command_description_usage(cls):
        """set command descriptions"""
        super().set_command_description_usage()
        cls.command_description = "Moves the character to a target object in the stage"
        cls.command_usage = (
            "Navigate the character to a target object. Interaction commnads could be added after this command to "
            "mimic the interact between character and target object."
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
            name="GoToObject",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match",
            constant_match=True,
            example_input="GoToObject",
        )

        cls.define_parameter(
            name="Target_Object_Path",
            param_type=str,
            length=1,
            description="The usd prim path of the target object",
            example_input="/World/Object",
        )
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_name = "GoToObject"

    # decide the rotation of character when they reach the object
    def generate_final_rotation_position(self, object_path):
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(str(object_path))
        transform_matrix = omni.usd.get_world_transform_matrix(prim)
        object_pos_raw = transform_matrix.ExtractTranslation()
        object_pos = carb.Float3(object_pos_raw[0], object_pos_raw[1], 0)
        destination_pos = Utils.get_closest_navmesh_point(object_pos)
        final_distance = CarbUtil.dist3(destination_pos, object_pos)
        # convert the result to the format that x y z z_rot
        result = []
        result.append(destination_pos[0])
        result.append(destination_pos[1])
        result.append(destination_pos[2])

        # if final distance > 0.25 their still have space between character and object, we rotate character to object
        if final_distance > 0.25:
            destination_pos_projection = carb.Float3(destination_pos[0], destination_pos[1], 0)
            direction_vector = CarbUtil.sub3(object_pos, destination_pos_projection)
            rotation = math.atan2(direction_vector[0], -direction_vector[1])
            result.append(math.degrees(rotation))

        # if distance < 0.25 set the rotation to "_"

        else:
            result.append("_")

        return result

    # set up rotation and position of walk
    def setup(self):
        super().setup()
        prim_path = self.command[1]
        result = self.generate_final_rotation_position(prim_path)
        self.character.set_variable("Action", "Walk")
        self.navigation_manager.generate_goto_path(result)

    def execute(self, dt):
        if self.finished:
            return True

        if not self.is_setup:
            self.setup()
        return self.update(dt)

    def update(self, dt):
        self.time_elapsed += dt
        if self.walk(dt):
            carb.log_warn("Reached the Destination")
            return self.exit_command()

    def force_quit_command(self):
        return super().force_quit_command()
