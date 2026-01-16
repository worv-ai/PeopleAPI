import logging

import carb

# Avoid exposing the abstract base class as a module-level symbol.
import omni.anim.people_api.scripts.character_behavior_base as behavior_base

logger = logging.getLogger(__name__)


class CharacterBehaviorRandomGoto(behavior_base.CharacterBehaviorBase):
    """
    Character controller class that randomly generates a navigation path for the character to follow.
    """

    def get_simulation_commands(self):
        current_position = self.get_current_position()
        commands = []
        while True:
            random_point = carb.Float3(0, 0, 0)
            if not self.navmesh.query_random_point(self.character_name, random_point):
                continue
            path = self.navmesh.query_shortest_path(current_position, random_point)
            if path is not None:
                logger.debug(
                    "Successfully generated the character's next position. %s -> %s",
                    current_position,
                    random_point,
                )
                break
            else:
                logger.debug(
                    "Failed to generate the character's next position. %s -> %s",
                    current_position,
                    random_point,
                )
        random_rotation = self.random.uniform(0, 360)
        commands.append(
            (None, ["GoTo", str(random_point[0]), str(random_point[1]), str(random_point[2]), str(random_rotation)])
        )

        random_duration = self.random.uniform(self.idle_duration_min, self.idle_duration_max)
        commands.append((None, ["Idle", str(random_duration)]))
        logger.debug("Generated commands: %s", commands)
        return commands
