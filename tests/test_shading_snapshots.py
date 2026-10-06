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


class NextOccurrenceAtOrAfter(unittest.TestCase):
    def test_lands_today_when_the_hour_hasnt_passed_yet(self):
        # now is 2025-09-12, ~21:40 UTC; hour 23 hasn't happened yet today —
        # unlike next_occurrence_following_day, this must NOT wait for
        # tomorrow (see record_attempt_failure's new_peak_hour_utc: a
        # freshly-found retarget hour still ahead today shouldn't make a
        # tech wait an extra day for it).
        result = shading_snapshots.next_occurrence_at_or_after(23, now=1_757_713_200)
        self.assertEqual(datetime.utcfromtimestamp(result), datetime(2025, 9, 12, 23, 0, 0))

    def test_lands_tomorrow_when_the_hour_already_passed_today(self):
        # Same now as above (~21:40 UTC); hour 10 already happened today.
        result = shading_snapshots.next_occurrence_at_or_after(10, now=1_757_713_200)
        self.assertEqual(datetime.utcfromtimestamp(result), datetime(2025, 9, 13, 10, 0, 0))


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

    def test_new_peak_hour_utc_retargets_instead_of_a_plain_retry(self):
        # Live regression, RD3365/MU7034, 2026-09-16: scheduled for 7am off
        # a detection that (correctly, at the time) found that hour worst,
        # but the trailer's real dip was around noon by the time an
        # attempt actually ran. A plain retry would just check 7am again;
        # retargeting updates peak_hour_utc so the NEXT attempt aims at
        # the hour that's actually dipping.
        now = time.time()
        task_id, _, first_attempt = shading_snapshots.schedule_task(
            "RD3365", "", "fisheye", 7, attempts_total=3, now=now,
        )
        shading_snapshots.record_attempt_failure(
            task_id, "found, but not near enough to now", now=first_attempt, new_peak_hour_utc=12,
        )
        task = shading_snapshots.get_task(task_id)
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["attempts_used"], 1)
        self.assertEqual(task["peak_hour_utc"], 12)

    def test_force_exhaust_skips_straight_to_exhausted_with_attempts_remaining(self):
        # COMPRESSED_WINDOW_V1 fix: a classic dip-mode task whose target
        # hour no longer reads as productive is a dead end no retry can
        # fix — force_exhaust lets the caller stop it immediately rather
        # than burning through the rest of attempts_total identically.
        now = time.time()
        task_id, _, attempt_at = shading_snapshots.schedule_task(
            "RD1", "", "fisheye", 12, attempts_total=3, now=now,
        )
        shading_snapshots.record_attempt_failure(
            task_id, "Hour 12:00 (UTC) isn't a productive hour", now=attempt_at, force_exhaust=True,
        )
        task = shading_snapshots.get_task(task_id)
        self.assertEqual(task["status"], "exhausted")
        self.assertEqual(task["attempts_used"], 1)  # only the one real attempt, not all 3

    def test_verify_mode_and_window_minutes_are_stored_and_default_to_dip(self):
        dip_id, _, _ = shading_snapshots.schedule_task("RD1", "", "fisheye", 12)
        dip_task = shading_snapshots.get_task(dip_id)
        self.assertEqual(dip_task["verify_mode"], "dip")
        self.assertIsNone(dip_task["window_start_minutes_utc"])
        self.assertIsNone(dip_task["window_end_minutes_utc"])

        cw_id, _, _ = shading_snapshots.schedule_task(
            "RD2", "", "fisheye", 19,
            verify_mode="compressed_window", window_start_minutes_utc=945, window_end_minutes_utc=1155,
        )
        cw_task = shading_snapshots.get_task(cw_id)
        self.assertEqual(cw_task["verify_mode"], "compressed_window")
        self.assertEqual(cw_task["window_start_minutes_utc"], 945)
        self.assertEqual(cw_task["window_end_minutes_utc"], 1155)

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
