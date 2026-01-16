import math
import random

import carb
import numpy as np
import omni.anim.navigation.core as nav

from omni.anim.people_api.scripts.utils import Utils
from omni.metropolis.utils.carb_util import CarbUtil
from omni.metropolis.utils.type_util import TypeUtil
from pxr import Gf
from typing import Any

from .base_command import Command


class Talk(Command):
    """
    Command class to control character to talk with another character in stage.
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
            target_character_name = command_dict.get("Target_Character_Name")
            if Utils.fetch_target_character_instance_by_name(target_character_name) is None:
                return False
            return True
        except ImportError as e:
            carb.log_warn(f"Talk command is not valid, error occur: {e}")
            return False

    @classmethod
    def set_command_description_usage(cls):
        """set command descriptions"""
        super().set_command_description_usage()
        cls.command_description = (
            "Moves the character to another character in the stage, then let two characters talk for a duration"
        )
        cls.command_usage = (
            "Can be used to show behaviors such as discussing, chatting, joking, or other talking like behaviors."
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
            description="The name of the character who will move and initiate the conversation.",
            example_input="Tom",
        )

        cls.define_parameter(
            name="Talk",
            param_type=str,
            length=1,
            description="The Command Name, need to be exactly match",
            constant_match=True,
            example_input="Talk",
        )

        cls.define_parameter(
            name="Target_Character_Name",
            param_type=str,
            length=1,
            description="The name of the character to converse with.",
            example_input="Leo",
        )

        cls.define_parameter(
            name="Talk_Time",
            param_type=float,
            length=1,
            description="Duration of the conversation in seconds.",
            example_input="10",
        )
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_character_name = self.command[1]
        self.command_name = "Talk"
        # This is the max attempts of finding a destination around people
        self.max_attempts = 100
        self.max_talk_distance = 2
        self.min_talk_distance = 1.5
        self.interaction_position = None
        self.target_character_position = None
        self.current_action = "walking"
        # how long should the talk animation last
        if len(self.command) <= 2:
            self.talk_time = 10
        else:
            self.talk_time = float(self.command[2])
        self.current_waiting_time = 0
        self.default_waiting_time = 0.5

        # whether character walk directly to the character
        # or
        # choose a random dot around the character
        self.random_interact_position = False

    def get_character_pos(self, character_name):
        # get character position base on their name
        character_position = Utils.get_character_position_by_name(character_name)
        return character_position

    # TODO: complete a stage checking method to check whether other character is ready to talk
    def check_target_character_state(self):
        # check whether target character's state is interruptable
        state_interruptable = Utils.is_agent_task_interruptable(self.target_character_name)
        return state_interruptable

    # TODO: complete this method to check whether target character has started talking.
    # if so, inject talking command to character
    def start_talking(self, character_name=""):
        return True

    # pcik random point around a 2d point
    def random_point_around(self):
        r = random.uniform(self.min_talk_distance, self.max_talk_distance)
        theta = random.uniform(0, 2 * math.pi)
        x, y = self.target_character_position[0], self.target_character_position[1]
        x_prime = x + r * math.cos(theta)
        y_prime = y + r * math.sin(theta)
        return x_prime, y_prime

    # choose an approriate point on the radius of the navigation
    def best_point_around(self):
        character_pos = self.get_character_pos(self.character_name)
        target_character_pos = self.target_character_position
        # generate a nav path that connect current character's position and target character position
        navmesh = nav.acquire_interface().get_navmesh()
        path = navmesh.query_shortest_path(character_pos, target_character_pos, agent_radius=0.5).get_points()
        # get nav path's intersect point between the circle center by target character, with radius = min_talk_distance
        best_point = self.find_last_intersection_point(
            character_pos, target_character_pos, self.min_talk_distance, path
        )
        return best_point

    def find_last_intersection_point(self, A, B, R, path):
        B = np.array(B)
        intersections = []

        for i in range(len(path) - 1):
            A = np.array(path[i])
            next_point = np.array(path[i + 1])

            # Direction vector for the current segment
            D = next_point - A

            # Quadratic coefficients
            a = np.dot(D, D)
            b = 2 * np.dot(D, A - B)
            c = np.dot(A - B, A - B) - R**2

            # Discriminant
            discriminant = b**2 - 4 * a * c

            if discriminant < 0:
                # No intersection for this segment
                continue

            # Find the two solutions for t
            t1 = (-b + np.sqrt(discriminant)) / (2 * a)
            t2 = (-b - np.sqrt(discriminant)) / (2 * a)

            # Check if the solutions are within the segment
            if 0 <= t1 <= 1:
                intersection1 = A + t1 * D
                intersections.append(intersection1)
            if 0 <= t2 <= 1:
                intersection2 = A + t2 * D
                intersections.append(intersection2)

        if not intersections:
            # No intersection found
            return path[0]

        # Find the last intersection point (the one farthest along the path)
        last_intersection = max(intersections, key=lambda point: np.linalg.norm(point - np.array(path[0])))

        return last_intersection.tolist()

    def calculate_desintation_pos(self):
        # calculate the distance between character and target characters.
        character_pos = self.get_character_pos(self.character_name)
        self.target_character_position = self.get_character_pos(self.target_character_name)
        # if user request character to talk with multiple characters at the sametime.

        if self.random_interact_position:
            attempts = 0
            # pick random dot around the character, when multiple character need to talk with the same character:
            while attempts < self.max_attempts:
                # ensure: min_talk_distance < the distance between interaction point and character < max_talk_distance
                random_x, random_y = self.random_point_around()
                new_point = carb.Float3(random_x, random_y, 0)
                # check whether the interaction point in on the navmesh
                if Utils.accessible_navmesh_point(new_point, character_pos):
                    return Utils.get_closest_navmesh_point(new_point)

        else:
            # pick the shortest way to walk toward the character:
            new_point = self.best_point_around()

            return new_point

        return self.target_character_position

    def calculate_distance(self, point1, point2):
        """distance between two points"""
        return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)

    # check whether target character's position has been modified:
    def require_new_talk_position(self):

        if not self.interaction_position or not self.target_character_position:
            return True
        current_target_character_pos = self.get_character_pos(self.target_character_name)
        distance = self.calculate_distance(self.target_character_position, current_target_character_pos)
        # if the distance between target charcter's current position and last position > threshold
        # recalculate the navpath:
        if distance > 0.2:
            return True
        return False

    #     return result
    def update(self, dt):
        # carb.log_info("udpate is called ")
        if self.current_action == "walking":
            if self.require_new_talk_position():
                # calculate the final interaction position between character and target character
                interaction_position_raw = self.calculate_desintation_pos()
                # object position
                object_pos = carb.Float3(self.target_character_position[0], self.target_character_position[1], 0)
                # interaction position around the character
                self.interaction_position = carb.Float3(interaction_position_raw[0], interaction_position_raw[1], 0)
                # calculate the distance between characters
                final_distance = self.calculate_distance(self.target_character_position, self.interaction_position)
                current_character_position = self.get_character_pos(self.character_name)
                end_rot = None
                # if final distance > 0.25 we rotate character to object
                if final_distance > 0.2 and self.random_interact_position:
                    direction_vector = CarbUtil.normalize3(CarbUtil.sub3(object_pos, self.interaction_position))
                    # rotation = math.atan2(direction_vector[0], -direction_vector[1])
                    end_dir = Gf.Vec3d(direction_vector[0], direction_vector[1], 0).GetNormalized()
                    end_quat = Gf.Rotation(Gf.Vec3d(0, -1.0, 0), end_dir).GetQuat()
                    end_rot = TypeUtil.gf_quatd_to_carb_float4(end_quat)

                self.navigation_manager.generate_path([current_character_position, self.interaction_position], end_rot)

            target_pos_distance = self.calculate_distance(
                self.interaction_position, self.get_character_pos(self.character_name)
            )

            # Check whether characters are close enough to trigger the talk behavior, this step is to finish the
            # walking state immediately
            if target_pos_distance < Utils.CONFIG["TalkDistance"]:
                # finish the walking method a
                self.desired_walk_speed = 0.0
                self.character.set_variable("Action", "None")
                self.navigation_manager.set_path_points([])
                self.navigation_manager.set_path_target_rot(None)
                self.navigation_manager.clean_path_targets()

            # Check whether character finish walking
            if self.walk(dt):
                if self.check_target_character_state():
                    # inject command to the target character
                    talk_command = "{char_name} TalkWith {target_char} {talk_time}".format(
                        char_name=self.target_character_name, target_char=self.character_name, talk_time=self.talk_time
                    )
                    Utils.runtime_inject_command(
                        character_name=self.target_character_name, command_list=[talk_command], force_inject=True
                    )
                    self.current_action = "waiting"

        elif self.current_action == "waiting":
            carb.log_warn("start talking!!")
            if self.start_talking(self.target_character_name):
                carb.log_warn(" host character start talking!!")
                # set state to wait to quit
                self.current_action = "quiting"
                # inject command to the current character
                talk_command = "{character_name} TalkWith {target_character} {talk_time}".format(
                    character_name=self.character_name,
                    target_character=self.target_character_name,
                    talk_time=self.talk_time,
                )
                # interrupt current command, but do not show in the status
                Utils.runtime_inject_command(
                    character_name=self.character_name,
                    command_list=[talk_command],
                    force_inject=True,
                    set_status=False,
                )

        # quit the command
        elif self.current_action == "quiting":
            self.character.set_variable("Action", "None")
            return self.exit_command()

        return

    # set up rotation and position of walk
    def setup(self):
        super().setup()
        # set current state to walking
        self.current_action = "walking"

    def execute(self, dt):
        if self.finished:
            return True

        if not self.is_setup:
            self.setup()
        return self.update(dt)

    def force_quit_command(self):
        return super().force_quit_command()
