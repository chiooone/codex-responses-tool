import tempfile
import unittest
import json
import sqlite3
from pathlib import Path

import app
from app import (
    create_snapshot,
    load_settings,
    patch_codex_config,
    repair_session_provider_metadata,
    restore_snapshot,
    save_settings,
)


class ConfigPatchTests(unittest.TestCase):
    def test_patch_preserves_model_inside_other_table(self):
        original = """# keep
approval_policy = "never"

[other]
model = "do-not-remove"

[model_providers.cpa-gui]
base_url = "old"
model = "provider-model"
"""
        patched = patch_codex_config(
            original,
            "http://127.0.0.1:8317/v1",
            "key",
            "gpt-test",
        )
        self.assertIn('model_provider = "cpa-gui"', patched)
        self.assertIn('model = "do-not-remove"', patched)
        self.assertEqual(patched.count("[model_providers.cpa-gui]"), 1)
        self.assertIn('wire_api = "responses"', patched)
        self.assertNotIn('base_url = "old"', patched)

    def test_patch_writes_custom_provider_display_name(self):
        patched = patch_codex_config(
            "",
            "http://127.0.0.1:8317/v1",
            "key",
            "gpt-test",
            "Chione Codex",
        )
        self.assertIn('name = "Chione Codex"', patched)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self._original_app_dir = app.APP_DIR
        self._original_backup_dir = app.BACKUP_DIR
        self._tempdir = tempfile.TemporaryDirectory()
        app.APP_DIR = Path(self._tempdir.name)
        app.BACKUP_DIR = app.APP_DIR / "backups"

    def tearDown(self):
        app.APP_DIR = self._original_app_dir
        app.BACKUP_DIR = self._original_backup_dir
        self._tempdir.cleanup()

    def test_snapshot_restores_to_current_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-a"
            sqlite_home = root / "sqlite-a"
            codex_home.mkdir()
            sqlite_home.mkdir()
            (codex_home / "config.toml").write_text('model = "old"\n', encoding="utf-8")
            (codex_home / "sessions").mkdir()
            (codex_home / "sessions" / "rollout.jsonl").write_text("{}\n", encoding="utf-8")
            (codex_home / "logs_2.sqlite").write_bytes(b"logs")
            (codex_home / "logs_2.sqlite-wal").write_bytes(b"wal")
            (sqlite_home / "state_5.sqlite").write_bytes(b"sqlite")

            snapshot = create_snapshot(codex_home, sqlite_home, "test")
            target_codex = root / "codex-b"
            target_sqlite = root / "sqlite-b"
            restored = restore_snapshot(snapshot, target_codex, target_sqlite, include_session_data=True)

            self.assertTrue((target_codex / "config.toml").is_file())
            self.assertTrue((target_codex / "sessions" / "rollout.jsonl").is_file())
            self.assertTrue((target_codex / "logs_2.sqlite").is_file())
            self.assertTrue((target_codex / "logs_2.sqlite-wal").is_file())
            self.assertTrue((target_sqlite / "state_5.sqlite").is_file())
            self.assertGreaterEqual(len(restored), 3)

    def test_normal_restore_preserves_current_conversation_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text('model = "before"\n', encoding="utf-8")
            sessions = codex_home / "sessions"
            sessions.mkdir()
            (sessions / "rollout.jsonl").write_text('{"message":"before"}\n', encoding="utf-8")
            snapshot = create_snapshot(codex_home, codex_home, "test")

            (codex_home / "config.toml").write_text('model = "after"\n', encoding="utf-8")
            (sessions / "rollout.jsonl").write_text('{"message":"new Responses API conversation"}\n', encoding="utf-8")

            restored = restore_snapshot(snapshot, codex_home, codex_home)

            self.assertEqual((codex_home / "config.toml").read_text(encoding="utf-8"), 'model = "before"\n')
            self.assertEqual(
                (sessions / "rollout.jsonl").read_text(encoding="utf-8"),
                '{"message":"new Responses API conversation"}\n',
            )
            self.assertEqual(restored, [str(codex_home / "config.toml")])

    def test_provider_repair_keeps_existing_threads_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            rollout = codex_home / "sessions" / "2026" / "08" / "rollout.jsonl"
            rollout.parent.mkdir(parents=True)
            rollout.write_text(
                '{"type":"session_meta","payload":{"id":"thread-1","cwd":"H:/Work","model_provider":"openai"}}\r\n'
                '{"type":"event_msg","payload":{"type":"user_message"}}\r\n',
                encoding="utf-8",
                newline="",
            )
            database = codex_home / "state_5.sqlite"
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    "CREATE TABLE threads (id TEXT PRIMARY KEY, model_provider TEXT, has_user_event INTEGER, cwd TEXT)"
                )
                connection.execute(
                    "INSERT INTO threads VALUES (?, ?, ?, ?)",
                    ("thread-1", "openai", 0, "H:/Old"),
                )
                connection.commit()
            finally:
                connection.close()

            result = repair_session_provider_metadata(codex_home, codex_home, "cpa-gui")

            records = [json.loads(line) for line in rollout.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["payload"]["model_provider"], "cpa-gui")
            connection = sqlite3.connect(database)
            try:
                row = connection.execute(
                    "SELECT model_provider, has_user_event, cwd FROM threads WHERE id = ?",
                    ("thread-1",),
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row, ("cpa-gui", 1, "H:/Work"))
            self.assertEqual(result["rollout_files_updated"], 1)
            self.assertGreaterEqual(result["sqlite_rows_updated"], 1)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self._original_app_dir = app.APP_DIR
        self._original_backup_dir = app.BACKUP_DIR
        self._tempdir = tempfile.TemporaryDirectory()
        app.APP_DIR = Path(self._tempdir.name)
        app.BACKUP_DIR = app.APP_DIR / "backups"

    def tearDown(self):
        app.APP_DIR = self._original_app_dir
        app.BACKUP_DIR = self._original_backup_dir
        self._tempdir.cleanup()

    def test_settings_round_trip_uses_app_data(self):
        values = {
            "base_url": "https://api.example.com",
            "api_key": "test-key",
            "model": "gpt-test",
        }
        save_settings(values)

        self.assertEqual(load_settings(), values)
        self.assertTrue((app.APP_DIR / "settings.json").is_file())


if __name__ == "__main__":
    unittest.main()
