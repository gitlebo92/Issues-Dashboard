"""
Pure-function tests for summarize_recovery_email_status, which collapses
check_missing_recovery_emails's five result lists into one status per unit
for the Graphs modal's email indicator. No network, ERP or ART:

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402


def _row(unit, issue_id="", subject=""):
    return {"unit": unit, "issue_id": issue_id, "url": "u/" + issue_id if issue_id else "",
            "subject": subject, "switch_url": "ignored"}


class SummarizeRecoveryEmailStatusTests(unittest.TestCase):
    def test_each_list_maps_to_its_status(self):
        by_unit = work_tool.summarize_recovery_email_status(
            [_row("RD3132", "ISS-1")],   # needs_recovery_email
            [_row("RD3421", "ISS-2")],   # needs_initial_email
            [_row("FD1040", "ISS-3")],   # potential_false_positive
            [_row("RD3076", "ISS-4")],   # pending_recovery
            [_row("MU9062", "ISS-5")],   # email_status_up_to_date
        )
        self.assertEqual(by_unit["RD3132"]["status"], "needs_recovery_email")
        self.assertEqual(by_unit["RD3421"]["status"], "needs_initial_email")
        self.assertEqual(by_unit["FD1040"]["status"], "potential_false_positive")
        self.assertEqual(by_unit["RD3076"]["status"], "pending_recovery")
        self.assertEqual(by_unit["MU9062"]["status"], "email_status_up_to_date")
        self.assertEqual(by_unit["RD3421"]["issue_id"], "ISS-2")
        self.assertEqual(by_unit["RD3421"]["url"], "u/ISS-2")
        # Only the fields the indicator needs are carried over.
        self.assertNotIn("switch_url", by_unit["RD3421"])

    def test_most_urgent_status_wins_for_a_unit_on_two_tickets(self):
        # RD3132 has one ticket fully emailed and another that never got
        # an outage email — the indicator must show the one needing action.
        by_unit = work_tool.summarize_recovery_email_status(
            [], [_row("RD3132", "ISS-9")], [], [], [_row("RD3132", "ISS-1")],
        )
        self.assertEqual(by_unit["RD3132"]["status"], "needs_initial_email")
        self.assertEqual(by_unit["RD3132"]["issue_id"], "ISS-9")

    def test_plain_strings_and_case_are_handled(self):
        by_unit = work_tool.summarize_recovery_email_status(["rd3132 "], [], [], [], [])
        self.assertEqual(by_unit, {
            "RD3132": {"status": "needs_recovery_email", "issue_id": "", "url": "", "subject": ""},
        })

    def test_empty_report_is_empty(self):
        self.assertEqual(work_tool.summarize_recovery_email_status([], [], [], [], []), {})


class RecoveryEmailStatusAfterValidationTests(unittest.TestCase):
    """A validation that re-pinged the unit re-sorts its email status (RD1020, 2026-10-09)."""

    def after(self, status, category, has_outage=None):
        info = {"status": status}
        if has_outage is not None:
            info["has_outage_email"] = has_outage
        return work_tool.recovery_email_status_after_validation(info, category)

    def test_no_emails_down_then_found_up_is_possible_false_positive(self):
        self.assertEqual(self.after("needs_initial_email", "false_positives", False), "potential_false_positive")

    def test_outage_sent_still_down_then_found_up_needs_recovery_email(self):
        self.assertEqual(self.after("pending_recovery", "false_positives", True), "needs_recovery_email")

    def test_found_down_after_looking_up(self):
        self.assertEqual(self.after("potential_false_positive", "truly_down", False), "needs_initial_email")
        self.assertEqual(self.after("needs_recovery_email", "truly_down", True), "pending_recovery")

    def test_camera_or_speaker_outage_counts_as_up(self):
        self.assertEqual(self.after("needs_initial_email", "camera_outage", False), "potential_false_positive")
        self.assertEqual(self.after("needs_initial_email", "speaker_outage", False), "potential_false_positive")

    def test_compute_down_is_pending_recovery(self):
        self.assertEqual(self.after("needs_initial_email", "nuc_down", False), "pending_recovery")
        self.assertEqual(self.after("needs_recovery_email", "scrypted_outage", True), "pending_recovery")

    def test_up_to_date_and_unknown_units_are_left_alone(self):
        self.assertIsNone(self.after("email_status_up_to_date", "truly_down", True))
        self.assertIsNone(work_tool.recovery_email_status_after_validation(None, "false_positives"))
        self.assertIsNone(self.after("needs_initial_email", "panel_issues", False))

    def test_infers_outage_email_for_results_cached_before_the_flag(self):
        self.assertEqual(self.after("needs_initial_email", "false_positives"), "potential_false_positive")
        self.assertEqual(self.after("needs_recovery_email", "truly_down"), "pending_recovery")
        # pending_recovery could be either, so without the flag it is left alone.
        self.assertIsNone(self.after("pending_recovery", "false_positives"))

    def test_summary_keeps_has_outage_email(self):
        item = {"unit": "RD1020", "issue_id": "ISS-1", "url": "", "subject": "s", "has_outage_email": False}
        by_unit = work_tool.summarize_recovery_email_status([], [item], [], [], [])
        self.assertIs(by_unit["RD1020"]["has_outage_email"], False)


if __name__ == "__main__":
    unittest.main()
