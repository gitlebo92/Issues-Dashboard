"""
Tests for the Up Steady re-check (flask_endpoints._revalidate_shared_list and
_revalidate_up_steady_from_email_check). The per-ticket check
(work_tool.revalidate_list_entry) is mocked, so nothing is pinged:

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("WORK_TOOL_ENV", "sandbox")
os.environ.setdefault("WORK_TOOL_DATA_DIR", tempfile.mkdtemp(prefix="work_tool_test_"))

import flask_endpoints as fe  # noqa: E402


def _ticket(unit, issue_id):
    return {"unit": unit, "issue_id": issue_id, "led_status": "green"}


class UpSteadyRecheck(unittest.TestCase):
    def setUp(self):
        results = {key: [] for key in fe.ISSUE_RESULT_KEYS}
        results["false_positives"] = [_ticket("RD3073", "ISS-1"), _ticket("RD3010", "ISS-2")]
        self.job = {
            "done": True,
            "results": results,
            "poll_lock": threading.Lock(),
            "state_lock": threading.RLock(),
            "version": 0,
        }
        patches = [
            mock.patch.dict(fe.stream_jobs, {fe.SHARED_ISSUES_JOB_ID: self.job}),
            mock.patch.object(fe, "JobStdout"),
            mock.patch.object(fe.work_tool, "ensure_net_array"),
            mock.patch.object(fe.work_tool, "generate_net_array"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _check(self, down_units):
        def fake(list_id, item):
            if item["unit"] in down_units:
                return "truly_down", {"led_status": "red"}, "", None
            return "false_positives", {"led_status": "green"}, "", None
        return mock.patch.object(fe.work_tool, "revalidate_list_entry", side_effect=fake)

    def units(self, list_id):
        return [item["unit"] for item in self.job["results"][list_id]]

    def test_scheduled_recheck_moves_a_unit_that_went_down(self):
        with self._check({"RD3073"}):
            result, status = fe._revalidate_shared_list("false_positives", scheduled=True)
        self.assertIsNone(status)
        self.assertEqual((result["checked"], result["moved"]), (2, 1))
        self.assertEqual(self.units("false_positives"), ["RD3010"])
        self.assertEqual(self.units("truly_down"), ["RD3073"])
        self.assertEqual(self.job["results"]["truly_down"][0]["led_status"], "red")
        self.assertEqual(self.job["version"], 1)
        fe.work_tool.generate_net_array.assert_not_called()  # never reloads in the background

    def test_skips_instead_of_queueing_when_busy(self):
        self.job["poll_lock"].acquire()
        try:
            result, status = fe._revalidate_shared_list("false_positives", scheduled=True)
        finally:
            self.job["poll_lock"].release()
        self.assertEqual(status, 409)
        self.assertEqual(self.units("false_positives"), ["RD3073", "RD3010"])

    def test_email_check_rechecks_only_down_units_in_up_steady(self):
        by_unit = {
            "RD3073": {"status": "needs_initial_email"},   # down, in Up Steady -> re-checked
            "RD3010": {"status": "needs_recovery_email"},  # back up -> left alone
            "RD9999": {"status": "pending_recovery"},      # down, but not in Up Steady
        }
        with self._check({"RD3073", "RD3010"}) as check:
            fe._revalidate_up_steady_from_email_check(by_unit)
        self.assertEqual([c.args[1]["unit"] for c in check.call_args_list], ["RD3073"])
        self.assertEqual(self.units("truly_down"), ["RD3073"])
        self.assertEqual(self.units("false_positives"), ["RD3010"])

    def test_email_check_trusts_the_recheck_not_the_email_status(self):
        # The email check said down, but the fresh check finds it up: it stays.
        with self._check(set()):
            fe._revalidate_up_steady_from_email_check({"RD3073": {"status": "needs_initial_email"}})
        self.assertEqual(self.units("false_positives"), ["RD3073", "RD3010"])
        self.assertEqual(self.units("truly_down"), [])


class DownFullRecheck(unittest.TestCase):
    """Down Full re-check: a unit that's back moves to Up Steady and gets its cell/power check."""

    # Same job fixture and helpers as UpSteadyRecheck, without re-running its tests.
    setUp = UpSteadyRecheck.setUp
    _check = UpSteadyRecheck._check
    units = UpSteadyRecheck.units

    def _down_full(self, *units):
        self.job["results"]["false_positives"] = []
        self.job["results"]["truly_down"] = [_ticket(u, f"ISS-{u}") for u in units]

    def test_unit_back_up_moves_to_up_steady_and_gets_cell_power_check(self):
        self._down_full("RD3064", "RD3330")
        with self._check({"RD3330"}), \
                mock.patch.object(fe, "_recheck_power_vs_cell_for_units") as recheck:
            result, status = fe._revalidate_shared_list("truly_down", scheduled=True)
        self.assertIsNone(status)
        self.assertEqual(self.units("false_positives"), ["RD3064"])
        self.assertEqual(self.units("truly_down"), ["RD3330"])
        recheck.assert_called_once()
        self.assertEqual(list(recheck.call_args.args[0]), ["RD3064"])

    def test_up_steady_recheck_never_runs_cell_power_check(self):
        with self._check(set()), \
                mock.patch.object(fe, "_recheck_power_vs_cell_for_units") as recheck:
            fe._revalidate_shared_list("false_positives", scheduled=True)
        recheck.assert_not_called()

    def test_email_check_rechecks_only_up_units_in_down_full(self):
        self._down_full("RD3064", "RD3330")
        by_unit = {
            "RD3064": {"status": "needs_recovery_email"},  # up, in Down Full -> re-checked
            "RD3330": {"status": "pending_recovery"},      # still down -> left alone
        }
        with self._check(set()) as check, \
                mock.patch.object(fe, "_recheck_power_vs_cell_for_units"):
            fe._revalidate_down_full_from_email_check(by_unit)
        self.assertEqual([c.args[1]["unit"] for c in check.call_args_list], ["RD3064"])
        self.assertEqual(self.units("false_positives"), ["RD3064"])


if __name__ == "__main__":
    unittest.main()
