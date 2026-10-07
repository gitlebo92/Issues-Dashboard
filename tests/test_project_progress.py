"""
Tests for work_tool/project_progress.py — the Project Progress check's
classification and its ERP (America/Boise) timestamp conversion. Pure
functions, no network:

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool.project_progress as pp  # noqa: E402


def _erp_stamp(utc_dt, offset_hours):
    """An ERP-style naive local timestamp for a UTC instant."""
    return (utc_dt + timedelta(hours=offset_hours)).strftime("%Y-%m-%d %H:%M:%S.%f")


class ErpTimeToUtc(unittest.TestCase):
    def test_summer_is_utc_minus_6(self):
        # 2026-10-07 09:09 Boise (MDT) is 15:09 UTC — the live sample.
        self.assertEqual(
            pp.erp_time_to_utc("2026-10-07 09:09:49.416155"),
            datetime(2026, 10, 7, 15, 9, 49, 416155, tzinfo=timezone.utc),
        )

    def test_winter_is_utc_minus_7(self):
        self.assertEqual(
            pp.erp_time_to_utc("2026-01-15 08:00:00"),
            datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
        )

    def test_dst_boundaries_2026(self):
        # DST starts Sun 2026-03-08 02:00 MST (09:00 UTC), ends Sun 2026-11-01 02:00 MDT (08:00 UTC).
        self.assertEqual(pp.erp_time_to_utc("2026-03-08 01:59:00").hour, 8)   # still MST
        self.assertEqual(pp.erp_time_to_utc("2026-03-08 03:00:00").hour, 9)   # MDT
        self.assertEqual(pp.erp_time_to_utc("2026-11-01 00:30:00").hour, 6)   # still MDT
        self.assertEqual(pp.erp_time_to_utc("2026-11-01 03:00:00").hour, 10)  # MST again

    def test_blank_or_garbage_is_none(self):
        self.assertIsNone(pp.erp_time_to_utc(""))
        self.assertIsNone(pp.erp_time_to_utc(None))
        self.assertIsNone(pp.erp_time_to_utc("not a date"))


class ProjectProgressStatus(unittest.TestCase):
    NOW = datetime(2026, 10, 7, 16, 0, tzinfo=timezone.utc)

    def _status(self, percent, idle_hours):
        modified = _erp_stamp(self.NOW - timedelta(hours=idle_hours), -6)
        return pp.project_progress_status(percent, modified, now=self.NOW)

    def test_noc_done_at_83_3_regardless_of_age(self):
        self.assertEqual(self._status(83.3, 1)["status"], pp.PROGRESS_DONE)
        self.assertEqual(self._status(95.12, 500)["status"], pp.PROGRESS_DONE)
        self.assertFalse(self._status(95.12, 500)["needs_attention"])

    def test_stalled_band_needs_two_days_idle(self):
        self.assertEqual(self._status(45, 49)["status"], pp.PROGRESS_STALLED)
        self.assertTrue(self._status(45, 49)["needs_attention"])
        self.assertEqual(self._status(45, 47)["status"], pp.PROGRESS_IN_PROGRESS)

    def test_band_edges(self):
        self.assertEqual(self._status(10.01, 72)["status"], pp.PROGRESS_STALLED)
        self.assertEqual(self._status(81.99, 72)["status"], pp.PROGRESS_STALLED)
        self.assertEqual(self._status(10, 72)["status"], pp.PROGRESS_NOT_STARTED)
        # 82-83.3 is the gap no real task count lands in: never flagged.
        self.assertEqual(self._status(82.5, 72)["status"], pp.PROGRESS_IN_PROGRESS)

    def test_not_started(self):
        result = self._status(0, 24 * 5 + 1)
        self.assertEqual(result["status"], pp.PROGRESS_NOT_STARTED)
        self.assertEqual(result["idle_days"], 5)
        self.assertEqual(self._status(None, 72)["status"], pp.PROGRESS_NOT_STARTED)
        self.assertEqual(self._status(0, 3)["status"], pp.PROGRESS_IN_PROGRESS)

    def test_unknown_modified_never_flags(self):
        result = pp.project_progress_status(45, "", now=self.NOW)
        self.assertEqual(result["status"], pp.PROGRESS_IN_PROGRESS)
        self.assertIsNone(result["idle_days"])


if __name__ == "__main__":
    unittest.main()
