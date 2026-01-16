import logging

# Avoid exposing the abstract base class as a module-level symbol.
import omni.anim.people_api.scripts.character_behavior_base as behavior_base

logger = logging.getLogger(__name__)


class CharacterBehaviorRandomIdle(behavior_base.CharacterBehaviorBase):
    """
    Character controller class that randomly generates
    a 'look around' and 'idle' command for the character to follow.
    """

    def get_simulation_commands(self):
        commands = []
        random_duration = self.random.uniform(self.idle_duration_min, self.idle_duration_max)
        commands.append((None, ["LookAround", str(random_duration * 10)]))
        random_duration = self.random.uniform(self.idle_duration_min, self.idle_duration_max)
        commands.append((None, ["Idle", str(random_duration * 10)]))
        logger.debug("Generated commands: %s", commands)
        return commands
