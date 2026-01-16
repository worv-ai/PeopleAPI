import carb
import omni.usd
from omni.metropolis.utils.carb_util import CarbUtil
from omni.anim.people_api.scripts.commands.base_command import Command
from omni.anim.people_api.scripts.utils import Utils
from omni.anim.people_api.settings import TaskStatus
from omni.anim.people_api.scripts.interactable_object_helper import InteractableObjectHelper


class CommandTemplateBase(Command):
    def __init__(self, command_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_name = command_name
        self.action_name = command_name  # Action name is the command name for simplicity

    def setup(self):
        super().setup()

    def update(self, dt):
        return super().update(dt)

    def force_quit_command(self):
        return super().force_quit_command()


class TimingTemplate(CommandTemplateBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.command) > 1:
            self.duration = float(self.command[1])
        # To allow state machine some time to update
        self._is_exiting = False
        self._exit_time = 0.1

    def setup(self):
        super().setup()
        self.character.set_variable("Action", self.action_name)

    def update(self, dt):
        self.time_elapsed += dt
        if not self._is_exiting:
            if self.time_elapsed > self.duration:
                self._is_exiting = True
                self.character.set_variable("Action", "None")
        else:
            if self.time_elapsed > self.duration + self._exit_time:
                return self.exit_command()

    def force_quit_command(self):
        return super().force_quit_command()


class TimingToObjectTemplate(CommandTemplateBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.command) > 2:
            stage = omni.usd.get_context().get_stage()
            self.obj_prim = stage.GetPrimAtPath(self.command[1])
            self.duration = float(self.command[2])
        self.interact_time = 0
        self.interact_pos = None
        self.current_action = None
        # Pre-define param
        self.end_time = 1.0

    def __del__(self):
        if self.obj_prim is not None:
            InteractableObjectHelper.remove_owner(target_prim=self.obj_prim, agent_name=self.character_name)

    def setup(self):
        super().setup()
        stage = omni.usd.get_context().get_stage()
        (
            self.walk_to_pos,
            self.walk_to_rot,
            self.interact_pos,
            self.interact_rot,
        ) = InteractableObjectHelper.get_interact_prim_offsets(stage, self.obj_prim)
        character_pos = Utils.get_character_pos(self.character)
        self.navigation_manager.generate_path([character_pos, self.walk_to_pos], self.walk_to_rot)
        self.current_action = "walk"
        self.lerp_to_timer = 0
        self.lerp_back_timer = 0

    def update(self, dt):
        if self.current_action == "walk" or self.current_action is None:
            if self.walk(dt):
                # Check if object is interactable
                if not InteractableObjectHelper.is_object_interactable(self.obj_prim):
                    carb.log_warn(
                        f"Fail to perform {self.command_name}. Object {self.obj_prim.GetPrimPath()} "
                        "can not be interacted with (missing interactable attribute or being occupied)."
                    )
                    self.set_status(TaskStatus.failed)
                    self.force_quit_command()
                    return
                InteractableObjectHelper.add_owner(target_prim=self.obj_prim, agent_name=self.character_name)
                self.current_action = self.action_name
                self.char_interact_start_pos, self.char_interact_start_rot = Utils.get_character_transform(
                    self.character
                )

        elif self.current_action == self.action_name:
            # Snap to interact position and rotation
            self.lerp_to_timer += dt
            lerp_val = min(self.lerp_to_timer, 1.0)
            lerp_pos = CarbUtil.lerp3(self.char_interact_start_pos, self.interact_pos, lerp_val)
            lerp_rot = CarbUtil.lerp4(self.char_interact_start_rot, self.interact_rot, lerp_val)
            self.character.set_world_transform(lerp_pos, lerp_rot)
            # Play animation
            self.interact_time += dt
            self.character.set_variable("Action", self.action_name)
            if self.interact_time > self.duration:
                self.character.set_variable("Action", "None")
                self.current_action = "Ending"
                InteractableObjectHelper.remove_owner(target_prim=self.obj_prim, agent_name=self.character_name)

        elif self.current_action == "Ending":
            # Resume to initial state
            self.character.set_variable("Action", "None")
            self.lerp_back_timer += dt
            # Lerp back to initial spot
            if self.lerp_back_timer < self.end_time:
                lerp_val = min(self.lerp_back_timer, 1.0)
                lerp_pos = CarbUtil.lerp3(self.interact_pos, self.char_interact_start_pos, lerp_val)
                lerp_rot = CarbUtil.lerp4(self.interact_rot, self.char_interact_start_rot, lerp_val)
                self.character.set_world_transform(lerp_pos, lerp_rot)
            else:
                self.character.set_world_transform(self.char_interact_start_pos, self.char_interact_start_rot)
                return self.exit_command()

    def force_quit_command(self):
        if self.obj_prim is not None:
            InteractableObjectHelper.remove_owner(target_prim=self.obj_prim, agent_name=self.character_name)

        if self.current_action == "walk" or self.current_action is None:
            return super().force_quit_command()

        if self.current_action == self.action_name:
            self.current_action = "Ending"


class GoToBlendTemplate(CommandTemplateBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setup(self):
        super().setup()
        self.character.set_variable("Action", self.action_name)
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

    # A copy of the walk(dt) from base command class. The only change is the state variable
    def walk(self, dt):
        if self.navigation_manager.destination_reached():
            self.desired_walk_speed = 0.0
            if self.actual_walk_speed < 0.001:
                self.character.set_variable("Action", "None")
                self.navigation_manager.set_path_points(None)
                if self.navigation_manager.get_path_target_rot() is not None:
                    if self.rotate(dt):
                        self.character.set_variable("Action", "None")
                        self.navigation_manager.set_path_target_rot(None)
                        self.navigation_manager.clean_path_targets()
                        return True
                    return False
                else:
                    self.character.set_variable("Action", "None")
                    self.navigation_manager.clean_path_targets()
                    return True
        else:
            self.set_rotation = False
            self.desired_walk_speed = 1.0

        self.character.set_variable("Action", self.action_name)
        self.navigation_manager.update_path()
        self.character.set_variable("PathPoints", self.navigation_manager.get_path_points())

        # Blends walking animation when starting or stopping.
        max_change = dt / Utils.CONFIG["WalkBlendTime"]
        delta_walk = CarbUtil.clamp(self.desired_walk_speed - self.actual_walk_speed, -1 * max_change, max_change)
        self.actual_walk_speed = CarbUtil.clamp(self.actual_walk_speed + delta_walk, 0.0, 1.0)
        # self.character.set_variable("Walk", self.actual_walk_speed)

    def force_quit_command(self):
        return super().force_quit_command()
