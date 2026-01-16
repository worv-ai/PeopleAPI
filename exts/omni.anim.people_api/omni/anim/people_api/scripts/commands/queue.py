# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from ..global_queue_manager import GlobalQueueManager
from ..utils import Utils
from .base_command import Command


class QueueCmd(Command):
    """
    Command class that implements a queue structure. Moves the character to an available queue spot, and controls
    character movement in the queue until they reach the top of the queue.
    """

    def __init__(self, queue_manager: GlobalQueueManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_manager: GlobalQueueManager = queue_manager
        self.queue = self.queue_manager.get_queue(self.command[1])
        self.current_spot = None
        self.target_spot = None
        self.walking = False
        self.wait_time_for_rot_correction = 0
        self.command_name = "QueueCmd"

    def setup(self):
        super().setup()
        self.walking = True

    def update(self, dt):
        if self.target_spot is None or (self.current_spot != self.target_spot and self.target_spot.is_occupied()):
            self.walking = True
            self.target_spot = self.queue.get_first_empty_spot()
            char_pos = Utils.get_character_pos(self.character)
            self.navigation_manager.generate_path(
                [char_pos, self.target_spot.get_translation()], self.target_spot.get_rotation()
            )
            return

        if not self.walking:
            if self.current_spot.get_index() == 0:
                return self.exit_command()
            else:
                nextIndex = self.current_spot.get_index() - 1
                nextSpot = self.queue.get_spot(nextIndex)
                if not nextSpot.is_occupied():
                    self.target_spot = nextSpot
                    self.walking = True
                    self.navigation_manager.generate_path(
                        [Utils.get_character_pos(self.character), self.target_spot.get_translation()],
                        self.target_spot.get_rotation(),
                    )
                    self.current_spot.set_occupier(None)
        else:
            self.wait_time_for_rot_correction = 0.0
            if self.navigation_manager.check_proximity_to_point(
                self.target_spot.get_translation(), Utils.CONFIG["DistanceToOccupyQueueSpot"]
            ):
                self.current_spot = self.target_spot
                self.target_spot.set_occupier(self.character_name)

            if self.walk(dt):
                self.walking = False
        return

    def force_quit_command(self):
        if self.current_spot is not None:
            self.current_spot.set_occupier(None)

        return super().force_quit_command()
