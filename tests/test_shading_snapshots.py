"""
Regression tests for shading_snapshots.py's task lifecycle and its date
math — the "schedule for the following day, verify before capturing,
retry up to N times, then clean up after a week" state machine described
in the module's own docstring.

    python -m unittest discover -s tests -v

Each test gets its own temp SQLite file (see setUp/tearDown) so these
never touch a real data directory, mirroring tests/test_diagnostics.py's
own pattern for unit_history.py.
"""

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shading_snapshots  # noqa: E402


class NextOccurrenceFollowingDay(unittest.TestCase):
    def test_lands_on_tomorrows_date_at_the_given_utc_hour(self):
        # Pin "now" to a known UTC instant (2025-09-13, ~10:40 UTC) so the
        # expected date is exact, not relative to whenever the test runs.
        now = 1_757_760_000
        result = shading_snapshots.next_occurrence_following_day(15, now=now)
        expected = datetime(2025, 9, 14, 15, 0, 0)
        self.assertEqual(datetime.utcfromtimestamp(result), expected)

    def test_still_the_following_day_even_if_the_hour_hasnt_passed_yet(self):
        # "Following day" is literal, not "at least 24h from now" — even
        # if hour_utc is still hours away today, this must land tomorrow,
        # never today. now here is 2025-09-12, ~21:40 UTC; hour 10 hasn't
        # happened yet that same day, but the result must still be
        # 2025-09-13's occurrence, not 2025-09-12's.
        now_at_hour_10 = shading_snapshots.next_occurrence_following_day(10, now=1_757_713_200)
        self.assertEqual(
            datetime.utcfromtimestamp(now_at_hour_10),
            datetime(2025, 9, 13, 10, 0, 0),
        )

    def test_days_ahead_parameter_moves_further_out(self):
        now = 1_757_760_000  # 2025-09-13, ~10:40 UTC
        result = shading_snapshots.next_occurrence_following_day(9, now=now, days_ahead=3)
        self.assertEqual(datetime.utcfromtimestamp(result), datetime(2025, 9, 16, 9, 0, 0))

    def test_hour_wraps_modulo_24(self):
        now = 1_757_760_000
        result = shading_snapshots.next_occurrence_following_day(25, now=now)  # 25 -> hour 1
        self.assertEqual(datetime.utcfromtimestamp(result).hour, 1)


class TaskLifecycle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        shading_snapshots._CONN = None
        shading_snapshots._DB_PATH = None
        self._prev_env = os.environ.get("WORK_TOOL_DATA_DIR")
        os.environ["WORK_TOOL_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        if shading_snapshots._CONN is not None:
            shading_snapshots._CONN.close()
        shading_snapshots._CONN = None
        shading_snapshots._DB_PATH = None
        if self._prev_env is None:
            os.environ.pop("WORK_TOOL_DATA_DIR", None)
        else:
            os.environ["WORK_TOOL_DATA_DIR"] = self._prev_env
        self._tmp.cleanup()

    def test_schedule_creates_a_pending_task_for_the_following_day(self):
        now = time.time()
        task_id, created, next_attempt_at = shading_snapshots.schedule_task(
            "rd3439", "PHX - RD3439 - ...", "fisheye", 16, now=now,
        )
        self.assertIsNotNone(task_id)
        self.assertTrue(created)
        self.assertGreater(next_attempt_at, now)
        task = shading_snapshots.get_task(task_id)
        self.assertEqual(task["unit"], "RD3439")  # normalized upper
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["attempts_used"], 0)
        self.assertEqual(task["attempts_total"], shading_snapshots.DEFAULT_ATTEMPTS_TOTAL)

    def test_scheduling_twice_for_the_same_unit_does_not_duplicate(self):
        id1, created1, _ = shading_snapshots.schedule_task("RD3439", "", "fisheye", 16)
        id2, created2, _ = shading_snapshots.schedule_task("RD3439", "", "fisheye", 16)
        self.assertEqual(id1, id2)
        self.assertTrue(created1)
        self.assertFalse(created2)

    def test_different_camera_targets_get_separate_tasks(self):
        id1, _, _ = shading_snapshots.schedule_task("RD3439", "", "fisheye", 16)
        id2, created2, _ = shading_snapshots.schedule_task("RD3439", "", "camera1", 16)
        self.assertNotEqual(id1, id2)
        self.assertTrue(created2)

    def test_due_tasks_only_returns_tasks_whose_time_has_arrived(self):
        now = time.time()
        task_id, _, _ = shading_snapshots.schedule_task("RD1", "", "fisheye", 12, now=now)
        self.assertEqual(shading_snapshots.due_tasks(now=now), [])
        tomorrow_afternoon = now + 2 * 86400
        due = shading_snapshots.due_tasks(now=tomorrow_afternoon)
        self.assertEqual([t["id"] for t in due], [task_id])

    def test_attempt_failure_reschedules_when_attempts_remain(self):
        now = time.time()
        task_id, _, first_attempt = shading_snapshots.schedule_task(
            "RD1", "", "fisheye", 12, attempts_total=3, now=now,
        )
        shading_snapshots.record_attempt_failure(task_id, "no dip observed", now=first_attempt)
        task = shading_snapshots.get_task(task_id)
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["attempts_used"], 1)
        self.assertGreater(task["next_attempt_at"], first_attempt)

    def test_task_is_exhausted_after_all_attempts_fail(self):
        now = time.time()
        task_id, _, attempt_at = shading_snapshots.schedule_task(
            "RD1", "", "fisheye", 12, attempts_total=2, now=now,
        )
        shading_snapshots.record_attempt_failure(task_id, "attempt 1 failed", now=attempt_at)
        task = shading_snapshots.get_task(task_id)
        shading_snapshots.record_attempt_failure(task_id, "attempt 2 failed", now=task["next_attempt_at"])
        task = shading_snapshots.get_task(task_id)
        self.assertEqual(task["status"], "exhausted")
        self.assertEqual(task["attempts_used"], 2)

    def test_captured_task_saves_image_and_is_readable_back(self):
        task_id, _, attempt_at = shading_snapshots.schedule_task("RD1", "", "fisheye", 12)
        image_bytes = b"\xff\xd8\xff\xe0fakejpegdata"
        shading_snapshots.record_captured(task_id, image_bytes, "dip confirmed", now=attempt_at)
        task = shading_snapshots.get_task(task_id)
        self.assertEqual(task["status"], "captured")
        self.assertTrue(task["image_filename"])
        path = shading_snapshots.image_path_for(task_id)
        self.assertIsNotNone(path)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), image_bytes)

    def test_latest_tasks_by_unit_returns_only_the_newest_per_unit(self):
        id_old, _, attempt_at = shading_snapshots.schedule_task("RD1", "", "fisheye", 12, attempts_total=1)
        shading_snapshots.record_attempt_failure(id_old, "exhausted on first try", now=attempt_at)
        id_new, _, _ = shading_snapshots.schedule_task("RD1", "", "camera1", 14)
        latest = shading_snapshots.latest_tasks_by_unit(["RD1"])
        self.assertEqual(latest["RD1"]["id"], id_new)

    def test_cancel_only_affects_pending_tasks(self):
        task_id, _, _ = shading_snapshots.schedule_task("RD1", "", "fisheye", 12)
        self.assertTrue(shading_snapshots.cancel_task(task_id))
        self.assertEqual(shading_snapshots.get_task(task_id)["status"], "cancelled")

    def test_prune_removes_old_tasks_and_their_images(self):
        now = time.time()
        old_task_id, _, attempt_at = shading_snapshots.schedule_task(
            "RDOLD", "", "fisheye", 12, now=now - 10 * 86400,
        )
        shading_snapshots.record_captured(old_task_id, b"\xff\xd8old", "old capture", now=now - 9 * 86400)
        image_path = shading_snapshots.image_path_for(old_task_id)
        self.assertTrue(os.path.isfile(image_path))

        new_task_id, _, _ = shading_snapshots.schedule_task("RDNEW", "", "fisheye", 12, now=now)

        deleted = shading_snapshots.prune_old(retention_days=7, now=now)
        self.assertEqual(deleted, 1)
        self.assertIsNone(shading_snapshots.get_task(old_task_id))
        self.assertFalse(os.path.isfile(image_path))
        self.assertIsNotNone(shading_snapshots.get_task(new_task_id))


if __name__ == "__main__":
    unittest.main()
