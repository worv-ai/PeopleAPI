from typing import Optional


class CharacterSeedRegistry:
    """Simple registry to store character seeds that can be accessed by behavior scripts."""

    _instance = None
    _seeds = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_seed(self, character_name: str, seed: int):
        """Set the seed for a character."""
        self._seeds[character_name] = seed

    def get_seed(self, character_name: str) -> Optional[int]:
        """Get the seed for a character."""
        return self._seeds.get(character_name)

    def clear(self):
        """Clear all stored seeds."""
        self._seeds.clear()
