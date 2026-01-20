import logging
import math
import time

import carb

# Avoid exposing the abstract base class as a module-level symbol.
import omni.anim.people_api.scripts.character_behavior_base as behavior_base

logger = logging.getLogger(__name__)

# Global cache for pre-computed NavMesh positions shared across all characters
# This dramatically reduces runtime NavMesh queries
_navmesh_position_cache = []
_navmesh_cache_index = 0
_navmesh_cache_initialized = False
_navmesh_cache_size = 200  # Pre-compute this many positions


class CharacterBehaviorRandomGoto(behavior_base.CharacterBehaviorBase):
    """
    Character controller class that randomly generates a navigation path for the character to follow.

    Unlike the base class which loops the same commands, this class regenerates
    new random destinations each time the command list is exhausted.

    OPTIMIZED: Uses cached NavMesh positions to reduce runtime queries.
    """

    # Maximum attempts to find a valid path before giving up temporarily
    MAX_PATH_ATTEMPTS = 1

    # Throttle NavMesh queries - only regenerate destinations after this many seconds
    MIN_COMMAND_INTERVAL = 2.0  # seconds between destination changes

    def on_update(self, current_time: float, delta_time: float):
        """Override update to regenerate commands instead of looping old ones.

        The base class copies loop_commands when commands are empty, but for
        RANDOM_GOTO we want fresh random destinations each time.

        OPTIMIZED: Throttles position publishing to reduce per-frame overhead.
        """
        try:
            if self.character is None:
                if not self.init_character():
                    return
                # Once character is initialized correctly,
                # register the agent to the AgentManager
                self.register_to_agent_manager()
                # Initialize timing for throttling
                self._last_position_publish_time = 0.0
                self._position_publish_interval = 0.2  # Publish every 200ms instead of every frame

            # OPTIMIZED: Throttle position publishing (every 200ms instead of every frame)
            # This reduces NavMesh queries for dynamic avoidance
            if self.navigation_manager and self.avoidanceOn:
                if not hasattr(self, '_last_position_publish_time'):
                    self._last_position_publish_time = 0.0
                    self._position_publish_interval = 0.2

                self._last_position_publish_time += delta_time
                if self._last_position_publish_time >= self._position_publish_interval:
                    self.navigation_manager.publish_character_positions(delta_time, 0.5)
                    self._last_position_publish_time = 0.0

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
        """OPTIMIZED: Uses cached positions and skips expensive path validation.

        Key optimizations:
        1. Uses global position cache instead of repeated query_random_point calls
        2. Skips NavMesh snapping (positions are pre-validated in cache)
        3. Skips path validation (trust NavMesh connectivity)
        4. Longer idle times to reduce command regeneration frequency
        """
        global _navmesh_position_cache, _navmesh_cache_index, _navmesh_cache_initialized

        current_position = self.get_current_position()
        commands = []

        # Initialize the global cache if needed (one-time cost)
        if not _navmesh_cache_initialized:
            self._initialize_position_cache()

        random_point = None

        # Try to get a position from cache first (no NavMesh query needed)
        if _navmesh_position_cache:
            # Use round-robin from cache for variety
            cache_idx = _navmesh_cache_index % len(_navmesh_position_cache)
            _navmesh_cache_index += 1
            cached_pos = _navmesh_position_cache[cache_idx]
            random_point = carb.Float3(cached_pos[0], cached_pos[1], cached_pos[2])
            logger.debug("Using cached position %d: %s", cache_idx, random_point)
        else:
            # Fallback to direct NavMesh query if cache is empty
            import omni.anim.navigation.core as nav
            inav = nav.acquire_interface()
            area_count = inav.get_area_count()
            area_mask = [1] * max(area_count, 1)
            random_point = self.navmesh.query_random_point(self.character_name, area_mask)

        # If we still don't have a valid point, idle briefly
        if random_point is None:
            logger.debug("No valid destination found, idling")
            idle_duration = self.random.uniform(2.0, 5.0)  # Longer idle to reduce retries
            commands.append((None, ["Idle", str(idle_duration)]))
            return commands

        random_rotation = self.random.uniform(0, 360)
        commands.append(
            (None, ["GoTo", str(random_point[0]), str(random_point[1]), str(random_point[2]), str(random_rotation)])
        )

        # OPTIMIZED: Longer idle times between movements to reduce NavMesh pressure
        # and give more realistic pedestrian behavior
        random_duration = self.random.uniform(
            max(self.idle_duration_min, 2.0),  # Minimum 2 seconds
            max(self.idle_duration_max, 5.0)   # Minimum max of 5 seconds
        )
        commands.append((None, ["Idle", str(random_duration)]))
        logger.debug("Generated commands: %s", commands)
        return commands

    def _initialize_position_cache(self):
        """Pre-compute NavMesh positions for all characters to share.

        This is called once when the first character needs a destination,
        and fills the global cache with valid NavMesh positions.
        """
        global _navmesh_position_cache, _navmesh_cache_initialized, _navmesh_cache_size

        if _navmesh_cache_initialized:
            return

        logger.info("Initializing global NavMesh position cache (%d positions)...", _navmesh_cache_size)
        start_time = time.time()

        import omni.anim.navigation.core as nav
        inav = nav.acquire_interface()
        area_count = inav.get_area_count()
        area_mask = [1] * max(area_count, 1)

        positions = []
        max_attempts = _navmesh_cache_size * 3
        attempts = 0

        while len(positions) < _navmesh_cache_size and attempts < max_attempts:
            attempts += 1
            point = self.navmesh.query_random_point(f"cache_{attempts}", area_mask)
            if point is not None:
                positions.append((float(point[0]), float(point[1]), float(point[2])))

        _navmesh_position_cache = positions
        _navmesh_cache_initialized = True

        elapsed = time.time() - start_time
        logger.info("NavMesh position cache initialized: %d positions in %.2fs",
                   len(positions), elapsed)

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
