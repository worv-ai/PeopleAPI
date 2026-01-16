import os

import omni.kit.app
import omni.kit.test
from omni.kit.scripting import BehaviorScript
from pxr import Usd

from omni.anim.people_api import python_ext
from omni.anim.people_api.scripts import character_behavior
from omni.anim.people_api.scripts import character_behavior_base
from omni.anim.people_api.scripts import character_behavior_random_goto
from omni.anim.people_api.scripts import character_behavior_random_idle


class TestPeopleApiExposure(omni.kit.test.AsyncTestCase):
    async def test_extension_exposed_and_scripts_present(self):
        ext_path = python_ext.get_ext_path()
        self.assertTrue(ext_path)
        self.assertTrue(os.path.isdir(ext_path))

        ext_manager = omni.kit.app.get_app().get_extension_manager()
        module_path = ext_manager.get_extension_path_by_module(character_behavior.__name__)
        self.assertIsNotNone(module_path)
        self.assertEqual(os.path.normpath(module_path), os.path.normpath(ext_path))

        behavior_path = os.path.join(
            ext_path, "omni", "anim", "people_api", "scripts", "character_behavior.py"
        )
        self.assertTrue(os.path.isfile(behavior_path))

        script_dir = os.path.join(ext_path, "omni", "anim", "people_api", "scripts")
        for script_name in (
            "character_behavior.py",
            "character_behavior_base.py",
            "character_behavior_random_goto.py",
            "character_behavior_random_idle.py",
            "dynamic_obstacle.py",
        ):
            self.assertTrue(os.path.isfile(os.path.join(script_dir, script_name)))

        self.assertTrue(issubclass(character_behavior.CharacterBehavior, BehaviorScript))
        self.assertTrue(issubclass(character_behavior_base.CharacterBehaviorBase, BehaviorScript))
        self.assertTrue(
            issubclass(
                character_behavior_random_goto.CharacterBehaviorRandomGoto,
                character_behavior_base.CharacterBehaviorBase,
            )
        )
        self.assertTrue(
            issubclass(
                character_behavior_random_idle.CharacterBehaviorRandomIdle,
                character_behavior_base.CharacterBehaviorBase,
            )
        )

    async def test_usd_importable(self):
        stage = Usd.Stage.CreateInMemory()
        self.assertIsNotNone(stage)
