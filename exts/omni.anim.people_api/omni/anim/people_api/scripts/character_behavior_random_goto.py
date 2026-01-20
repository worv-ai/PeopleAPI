import logging
import math

import carb

# Avoid exposing the abstract base class as a module-level symbol.
import omni.anim.people_api.scripts.character_behavior_base as behavior_base

logger = logging.getLogger(__name__)


class CharacterBehaviorRandomGoto(behavior_base.CharacterBehaviorBase):
    """
    Character controller class that randomly generates a navigation path for the character to follow.

    Unlike the base class which loops the same commands, this class regenerates
    new random destinations each time the command list is exhausted.
    """

    # Maximum attempts to find a valid path before giving up temporarily
    MAX_PATH_ATTEMPTS = 1

    def on_update(self, current_time: float, delta_time: float):
        """Override update to regenerate commands instead of looping old ones.

        The base class copies loop_commands when commands are empty, but for
        RANDOM_GOTO we want fresh random destinations each time.
        """
        try:
            if self.character is None:
                if not self.init_character():
                    return
                # Once character is initialized correctly,
                # register the agent to the AgentManager
                self.register_to_agent_manager()

            if self.navigation_manager and self.avoidanceOn:
                self.navigation_manager.publish_character_positions(delta_time, 0.5)

            if self.commands:
                self.execute_command(self.commands, delta_time)
            elif self.number_of_loop > self.loop_commands_count or self.number_of_loop == math.inf:
                # Instead of copying old loop_commands, generate fresh random commands
                self.commands = self.get_simulation_commands()
                self.loop_commands_count += 1
                logger.debug(
                    "Regenerated commands for %s (loop %d): %s",
                    self.character_name,
                    self.loop_commands_count,
                    self.commands,
                )
        except Exception:
            if not self._update_error_logged:
                carb.log_error(
                    f"CharacterBehaviorRandomGoto update failed for {self.prim_path}:\n"
                    + __import__('traceback').format_exc()
                )
                self._update_error_logged = True

    def get_simulation_commands(self):
        current_position = self.get_current_position()
        commands = []

        # Get area mask to include all navmesh areas
        import omni.anim.navigation.core as nav
        inav = nav.acquire_interface()
        area_count = inav.get_area_count()
        area_mask = [1] * max(area_count, 1)  # Include all areas

        # Snap current position to NavMesh to handle drift during animation
        # Use a smaller agent_radius for snapping to be more permissive
        snapped_start = self._snap_to_navmesh(current_position, agent_radius=0.5)
        if snapped_start is None:
            snapped_start = current_position
            logger.debug("Could not snap start position to NavMesh, using raw position")

        random_point = None
        attempts = 0

        while attempts < self.MAX_PATH_ATTEMPTS:
            attempts += 1
            # query_random_point returns the point directly, not via out parameter
            random_point = self.navmesh.query_random_point(self.character_name, area_mask)
            if random_point is None:
                continue

            # Snap the goal point to NavMesh as well
            snapped_goal = self._snap_to_navmesh(random_point, agent_radius=0.5)
            if snapped_goal is None:
                logger.debug("Random point not on NavMesh, skipping: %s", random_point)
                random_point = None
                continue

            # Try path with snapped positions
            path = self.navmesh.query_shortest_path(snapped_start, snapped_goal, agent_radius=0.5)
            if path is not None:
                logger.debug(
                    "Successfully generated the character's next position. %s -> %s",
                    snapped_start,
                    snapped_goal,
                )
                random_point = snapped_goal  # Use snapped goal for the GoTo command
                break
            else:
                logger.debug(
                    "Failed to generate the character's next position. %s -> %s (attempt %d/%d)",
                    snapped_start,
                    snapped_goal,
                    attempts,
                    self.MAX_PATH_ATTEMPTS,
                )
                random_point = None

        # If we couldn't find a valid path, idle briefly then try again
        # The overridden on_update() will call get_simulation_commands() again after idle completes
        if random_point is None:
            logger.warning(
                "Could not find valid path after %d attempts from %s. "
                "Character will idle briefly and retry. NavMesh may have disconnected regions.",
                self.MAX_PATH_ATTEMPTS,
                current_position,
            )
            idle_duration = self.random.uniform(1.0, 3.0)
            commands.append((None, ["Idle", str(idle_duration)]))
            return commands

        random_rotation = self.random.uniform(0, 360)
        commands.append(
            (None, ["GoTo", str(random_point[0]), str(random_point[1]), str(random_point[2]), str(random_rotation)])
        )

        random_duration = self.random.uniform(self.idle_duration_min, self.idle_duration_max)
        commands.append((None, ["Idle", str(random_duration)]))
        logger.debug("Generated commands: %s", commands)
        return commands

    def _snap_to_navmesh(self, position, agent_radius=0.5):
        """Snap a position to the nearest valid point on the NavMesh.

        This helps handle cases where:
        1. Character position drifts slightly off NavMesh during animation
        2. Random points are at NavMesh boundaries

        Args:
            position: The position to snap (tuple or carb.Float3)
            agent_radius: Agent radius for the query

        Returns:
            Snapped position as carb.Float3, or None if not on NavMesh
        """
        try:
            import carb

            # Convert to Float3 if needed
            if hasattr(position, '__getitem__'):
                query_point = carb.Float3(position[0], position[1], position[2])
            else:
                query_point = position

            # Query closest point on NavMesh
            result = self.navmesh.query_closest_point(query_point, agent_radius=agent_radius)

            if result is None:
                return None

            closest_point = result[0] if isinstance(result, tuple) else result

            # Check if the closest point is reasonably close (within 1m tolerance)
            # If too far, the original point is likely in a disconnected/invalid region
            dx = abs(query_point[0] - closest_point[0])
            dy = abs(query_point[1] - closest_point[1])

            if dx > 1.0 or dy > 1.0:
                logger.debug(
                    "Closest NavMesh point too far: original=%s, closest=%s",
                    query_point, closest_point
                )
                return None

            return carb.Float3(closest_point[0], closest_point[1], closest_point[2])

        except Exception as e:
            logger.debug("Failed to snap to NavMesh: %s", e)
            return None
