import os
import tempfile
from unittest import mock

import omni.kit.test

from omni.anim.people_api import python_ext
from omni.anim.people_api.scripts.custom_command.defines import get_anim_prim_name
from omni.anim.people_api.scripts.utils import Utils


class TestPeopleApiBasics(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        super().setUp()
        self.extension = python_ext.get_instance()
        self.assertIsNotNone(self.extension, "Extension instance should be available for tests.")
        self.manager = self.extension.get_custom_command_manager()
        self.assertIsNotNone(self.manager, "CustomCommandManager should be initialized on startup.")
        self.original_tracking_file = self.manager.get_tracking_file_path()
        if self.original_tracking_file:
            self.manager.load_tracking_file(self.original_tracking_file)

    async def tearDown(self):
        if self.manager and self.original_tracking_file:
            self.manager.load_tracking_file(self.original_tracking_file)
        super().tearDown()

    async def test_extension_startup_sets_tracking_file(self):
        self.assertTrue(self.manager.get_tracking_file_path())

    async def test_generate_unique_id(self):
        with mock.patch("time.time", return_value=1.234), mock.patch(
            "random.choices", return_value=list("ABCDEFGH")
        ):
            unique_id = Utils.generate_unique_id("Alice", prefix="CMD", length=8)
        self.assertEqual(unique_id, "Alice-CMD-1234-ABCDEFGH")

    async def test_check_command_type(self):
        self.assertEqual(Utils.check_command_type("walk"), "string")
        self.assertEqual(Utils.check_command_type(("idle", "5")), "pair")
        self.assertEqual(Utils.check_command_type(("single",)), "unknown")
        self.assertEqual(Utils.check_command_type(42), "unknown")

    async def test_get_anim_prim_name_replaces_delimiters(self):
        name = get_anim_prim_name("file:///tmp/My-Custom.anim.usd")
        self.assertEqual(name, "My_Custom_anim_usd")

    async def test_load_empty_tracking_file_resets_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "custom_command_tracking.json")
            with open(json_path, "w", encoding="utf-8") as file:
                file.write('{"animations": []}')
            self.manager.load_tracking_file(json_path)
            self.assertEqual(self.manager.get_tracking_file_path(), json_path)
            self.assertEqual(self.manager.get_all_custom_commands(), [])
