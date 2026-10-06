"""
Tests for work_tool/locks.py's default data dir and the one-time move of
files the package split left in work_tool/data/live/. Filesystem only, in
a temp dir — no network.

    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool.locks as locks  # noqa: E402


class MergeEntriesByUpdatedAt(unittest.TestCase):
    def test_newer_entry_wins_either_side(self):
        current = {
            "RD1": {"text": "old", "updated_at": "2026-09-12T01:04:05"},
            "RD2": {"text": "keep", "updated_at": "2026-10-05T00:00:00"},
        }
        legacy = {
            "RD1": {"text": "new", "updated_at": "2026-10-02T10:28:50"},
            "RD2": {"text": "stale", "updated_at": "2026-01-01T00:00:00"},
            "RD3": {"text": "only legacy", "updated_at": "2026-10-01T00:00:00"},
        }
        merged = locks._merge_entries_by_updated_at(current, legacy)
        self.assertEqual(merged["RD1"]["text"], "new")
        self.assertEqual(merged["RD2"]["text"], "keep")
        self.assertEqual(merged["RD3"]["text"], "only legacy")


class AdoptLegacyDataFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.package_dir = os.path.join(root, "work_tool")
        self.legacy_dir = os.path.join(self.package_dir, "data", "live")
        self.new_dir = os.path.join(root, "data", "live")
        os.makedirs(self.legacy_dir)
        os.makedirs(self.new_dir)
        self.patches = [
            mock.patch.object(locks, "_PACKAGE_DIR", self.package_dir),
            mock.patch.object(locks, "_LEGACY_PACKAGE_DATA_DIR", self.legacy_dir),
            mock.patch.dict(os.environ, {"WORK_TOOL_DATA_DIR": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _write(self, directory, name, data):
        with open(os.path.join(directory, name), "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_default_dir_is_repo_root_data_live(self):
        self.assertEqual(os.path.normpath(locks._default_data_dir()), os.path.normpath(self.new_dir))

    def test_notes_are_merged_and_legacy_renamed(self):
        self._write(self.new_dir, "unit_notes.json", {"RD1": {"text": "a", "updated_at": "2026-01-01T00:00:00"}})
        self._write(self.legacy_dir, "unit_notes.json", {"RD1": {"text": "b", "updated_at": "2026-02-01T00:00:00"},
                                                         "RD2": {"text": "c", "updated_at": "2026-02-01T00:00:00"}})
        path = locks._unit_notes_path()
        with open(path, encoding="utf-8") as f:
            notes = json.load(f)
        self.assertEqual({k: v["text"] for k, v in notes.items()}, {"RD1": "b", "RD2": "c"})
        self.assertFalse(os.path.exists(os.path.join(self.legacy_dir, "unit_notes.json")))
        self.assertTrue(os.path.exists(os.path.join(self.legacy_dir, "unit_notes.json.migrated")))

    def test_legacy_moved_when_no_new_copy(self):
        self._write(self.legacy_dir, "ticket_state.json", {"ISS-1": {"worked": True, "updated_at": "x"}})
        path = locks._ticket_state_path()
        with open(path, encoding="utf-8") as f:
            self.assertIn("ISS-1", json.load(f))

    def test_explicit_data_dir_is_left_alone(self):
        self._write(self.legacy_dir, "unit_notes.json", {})
        with mock.patch.dict(os.environ, {"WORK_TOOL_DATA_DIR": self.new_dir}):
            locks._adopt_legacy_data_file("unit_notes.json", merge_json=True)
        self.assertTrue(os.path.exists(os.path.join(self.legacy_dir, "unit_notes.json")))


if __name__ == "__main__":
    unittest.main()
