# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
from __future__ import annotations


class GlobalQueueManager:
    """Global class which facilitates all queue interactions between characters"""

    __instance: GlobalQueueManager = None

    def __init__(self):
        if self.__instance is not None:
            raise RuntimeError("Only one instance of GlobalQueueManager is allowed")
        self._queues: dict[str, Queue] = {}
        GlobalQueueManager.__instance = self

    def create_queue(self, queue_name):
        if queue_name not in self._queues:
            self._queues[queue_name] = Queue()
        return self._queues[queue_name]

    def get_queue(self, queue_name) -> Queue:
        return self._queues[queue_name]

    # remove character from the queue, free the queue spot occupied by character
    def remove_character_from_queue(self, character_name):
        for queue in self._queues.values():
            queue.free_queue_spot(character_name)

    def destroy(self):
        GlobalQueueManager.__instance = None

    @classmethod
    def get_instance(cls) -> GlobalQueueManager:
        if cls.__instance is None:
            GlobalQueueManager()
        return cls.__instance


class Queue:
    """
    Represents a logical structure for a Qsueue.
    """

    def __init__(self):
        self.num_spots = 0
        self.spots: list[QueueSpot] = []

    def create_spot(self, index, pos, rot):
        if index < self.num_spots:
            return

        if index > self.num_spots:
            raise ValueError("Invalid Queue Creation")

        self.num_spots += 1
        self.spots.append(QueueSpot(index, pos, rot))

    def get_num_spots(self):
        return self.num_spots

    def get_first_empty_spot(self):
        for spot in self.spots:
            if not spot.is_occupied():
                return spot

    def get_spot(self, index) -> QueueSpot:
        return self.spots[index]

    # free queue spot if it is occupied by target_character
    def free_queue_spot(self, target_character_name):
        for spot in self.spots:
            if str(spot.get_occupier()) == target_character_name:
                spot.set_occupier(None)


class QueueSpot:
    """
    Represents a logical structure for a queue spot.
    """

    def __init__(self, index, pos, rot):
        self.pos = pos
        self.rot = rot
        self.index = index
        self.occupier = None

    def get_index(self):
        return self.index

    def set_occupier(self, character_name):
        self.occupier = character_name

    def is_occupied(self):
        return self.occupier is not None

    def get_occupier(self):
        return self.occupier

    def get_transform(self):
        return (self.pos, self.rot)

    def get_translation(self):
        return self.pos

    def get_rotation(self):
        return self.rot

    def set_transform(self, pos, rot):
        self.pos = pos
        self.rot = rot
