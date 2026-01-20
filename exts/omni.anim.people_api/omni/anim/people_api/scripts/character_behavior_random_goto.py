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

        # Get area mask to include all navmesh areas
        import omni.anim.navigation.core as nav
        inav = nav.acquire_interface()
        area_count = inav.get_area_count()
        area_mask = [1] * max(area_count, 1)  # Include all areas

        while True:
            # query_random_point returns the point directly, not via out parameter
            random_point = self.navmesh.query_random_point(self.character_name, area_mask)
            if random_point is None:
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
