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


if __name__ == "__main__":
    unittest.main()
