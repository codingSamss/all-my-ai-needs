import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MOD_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pixel_buddy_install", MOD_ROOT / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerSafety(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.cache = self.root / "private-cache"

    def tearDown(self):
        self.temporary.cleanup()

    def test_source_integrity_and_licensed_graphics(self):
        origin, files = installer.source_files()
        self.assertIn("hooks/scene.ts", files)
        self.assertIn(b"MIT License", files["hooks/scene-NOTICES.txt"])
        self.assertEqual(origin["upstream"]["commit"], "3fc00b3ad2ef3a57ac043f8d28e7abcbd1679a6c")
        self.assertFalse(any(str(Path.home()).encode() in value for value in files.values()))

    def test_install_lock_refuses_second_writer(self):
        with installer.install_lock(self.cache):
            with self.assertRaises(installer.Refusal):
                with installer.install_lock(self.cache):
                    self.fail("second writer entered")
        self.assertFalse((self.cache / ".install-lock").exists())

    def test_cache_symlink_rejected(self):
        self.cache.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(installer.Refusal):
            installer.private_dir(self.cache)

    def test_offline_assembly_is_complete_and_repeatable(self):
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            plugin, files, fingerprint = installer.assemble(self.cache, True)
            installer.verify_tree(plugin, files)
            again, _, same = installer.assemble(self.cache, True)
        self.assertEqual((again, same), (plugin, fingerprint))

    def test_built_source_drift_preserved(self):
        plugin, _, _ = installer.assemble(self.cache, True)
        scene = plugin / "hooks/scene.ts"
        scene.write_bytes(b"local modification")
        with self.assertRaises(installer.Refusal):
            installer.assemble(self.cache, True)
        self.assertEqual(scene.read_bytes(), b"local modification")

    def test_missing_license_notice_rejected(self):
        origin, _ = installer.source_files()
        del origin["source_sha256"]["hooks/scene-NOTICES.txt"]
        with mock.patch.object(installer, "read_json", return_value=origin):
            with self.assertRaises(installer.Refusal):
                installer.source_files()

    def test_original_enabled_refuses_before_build_or_cli(self):
        config = self.root / "config"
        config.mkdir()
        settings = json.dumps({"enabledPlugins": {installer.ORIGINAL_ID: True}, "env": {"TEST_ONLY": "fixture"}}).encode()
        (config / "settings.json").write_bytes(settings)
        with mock.patch.object(installer, "conflicts"), mock.patch.object(installer, "assemble", side_effect=AssertionError("build")):
            with self.assertRaises(installer.Refusal):
                installer.install("unused-cli", config, self.cache, False)
        self.assertEqual((config / "settings.json").read_bytes(), settings)

    def test_local_plugin_drift_is_not_overwritten(self):
        plugin = self.root / "plugin"
        plugin.mkdir()
        (plugin / "entry.ts").write_bytes(b"hand edited")
        with self.assertRaises(installer.Refusal):
            installer.verify_tree(plugin, {"entry.ts": b"release"})
        self.assertEqual((plugin / "entry.ts").read_bytes(), b"hand edited")

    def test_extra_code_is_not_silently_ignored(self):
        plugin = self.root / "plugin"
        plugin.mkdir()
        (plugin / "entry.ts").write_bytes(b"release")
        (plugin / "unknown.ts").write_bytes(b"unknown")
        with self.assertRaises(installer.Refusal):
            installer.verify_tree(plugin, {"entry.ts": b"release"})

    def test_escape_in_source_catalog_rejected(self):
        origin, _ = installer.source_files()
        origin["source_sha256"] = {"../escape.ts": "0" * 64}
        with mock.patch.object(installer, "read_json", return_value=origin):
            with self.assertRaises(installer.Refusal):
                installer.source_files()

    def test_unconfirmed_license_rejected(self):
        origin, _ = installer.source_files()
        origin["upstream"]["license_status"] = "unknown"
        with mock.patch.object(installer, "read_json", return_value=origin):
            with self.assertRaises(installer.Refusal):
                installer.source_files()

    def test_existing_marketplace_edits_preserved(self):
        catalog = self.cache / "marketplace" / ".claude-plugin" / "marketplace.json"
        catalog.parent.mkdir(parents=True)
        prior = json.dumps({"name": "different", "plugins": []}).encode()
        catalog.write_bytes(prior)
        with self.assertRaises(installer.Refusal):
            installer.publish_catalog(self.cache, self.root, {}, "0" * 16)
        self.assertEqual(catalog.read_bytes(), prior)

    def test_malformed_plugin_registry_stops(self):
        config = self.root / "config"
        config.mkdir()
        (config / "settings.json").write_text(json.dumps({"enabledPlugins": []}))
        with self.assertRaises(installer.Refusal):
            installer.state(config)


if __name__ == "__main__":
    unittest.main()
