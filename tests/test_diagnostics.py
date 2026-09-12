"""
Tests for the read-only diagnostics and the SQLite validation history.

Like test_parsing.py these are pure: the SSH-backed functions are only
exercised through their input guards, and unit_history runs against a
temporary database rather than the real data dir.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402
import unit_history  # noqa: E402


SAMPLE_SERVICE_OUTPUT = """acme-database.service active running
acme-watchdog.service active running
acme-web.service failed failed
acme-metadata.service active running
"""

SAMPLE_DF = """Filesystem      Size  Used Avail Use% Mounted on
udev            7.8G     0  7.8G   0% /dev
/dev/mapper/pve-root   94G   82G  7.2G  92% /
/dev/nvme0n1p2  511M  328K  511M   1% /boot/efi
"""


class SizeTableParsing(unittest.TestCase):
    def test_picks_out_root_only(self):
        rows = work_tool._parse_size_table(SAMPLE_DF, wanted_mounts=("/",))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mount"], "/")
        self.assertEqual(rows[0]["use_percent"], 92)
        self.assertEqual(rows[0]["size"], "94G")
        self.assertEqual(rows[0]["available"], "7.2G")

    def test_no_match_returns_empty(self):
        self.assertEqual(work_tool._parse_size_table(SAMPLE_DF, wanted_mounts=("/nope",)), [])

    def test_garbage_does_not_raise(self):
        self.assertEqual(work_tool._parse_size_table("not a table"), [])
        self.assertEqual(work_tool._parse_size_table(""), [])


def _windows_ping_block(host, body):
    """One `ping -n 1` block, the shape _ping_host actually concatenates."""
    return (
        f"\nPinging {host} with 32 bytes of data:\n"
        f"{body}\n"
        f"\nPing statistics for {host}:\n"
        f"    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),\n"
    )


class PingStatistics(unittest.TestCase):
    # Four separate `ping -n 1` runs concatenated — three replies, one timeout.
    FIXED_OUTPUT = "".join([
        _windows_ping_block("10.1.1.1", "Reply from 10.1.1.1: bytes=32 time=14ms TTL=62"),
        _windows_ping_block("10.1.1.1", "Reply from 10.1.1.1: bytes=32 time=21ms TTL=62"),
        _windows_ping_block("10.1.1.1", "Reply from 10.1.1.1: bytes=32 time=17ms TTL=62"),
        _windows_ping_block("10.1.1.1", "Request timed out."),
    ])

    def test_extracts_min_avg_max_and_jitter(self):
        stats = work_tool.parse_ping_statistics(self.FIXED_OUTPUT)
        self.assertEqual(stats["samples"], 3)
        self.assertEqual(stats["min_ms"], 14)
        self.assertEqual(stats["max_ms"], 21)
        self.assertAlmostEqual(stats["avg_ms"], 17.3, places=1)
        self.assertGreater(stats["jitter_ms"], 0)

    def test_counts_four_attempts_across_concatenated_blocks(self):
        stats = work_tool.parse_ping_statistics(self.FIXED_OUTPUT)
        self.assertEqual(stats["sent"], 4)
        self.assertEqual(stats["replies"], 3)
        self.assertEqual(stats["loss_percent"], 25)

    def test_unreachable_reply_is_not_counted_as_a_reply(self):
        # Windows prints this as a "Reply from" line, but it carries no TTL=
        # and is not a successful echo.
        text = _windows_ping_block(
            "10.1.1.1", "Reply from 10.1.1.9: Destination host unreachable."
        )
        stats = work_tool.parse_ping_statistics(text)
        self.assertEqual(stats["replies"], 0)
        self.assertEqual(stats["loss_percent"], 100)

    def test_loss_percent_is_never_out_of_range(self):
        for text in (self.FIXED_OUTPUT, "Reply from 10.1.1.1: bytes=32 time=5ms TTL=64",
                     "Request timed out.", "General failure."):
            stats = work_tool.parse_ping_statistics(text)
            if "loss_percent" in stats:
                self.assertGreaterEqual(stats["loss_percent"], 0)
                self.assertLessEqual(stats["loss_percent"], 100)

    def test_all_replies_is_zero_loss(self):
        text = "".join(
            _windows_ping_block("10.1.1.1", "Reply from 10.1.1.1: bytes=32 time=9ms TTL=62")
            for _ in range(4)
        )
        stats = work_tool.parse_ping_statistics(text)
        self.assertEqual(stats["sent"], 4)
        self.assertEqual(stats["replies"], 4)
        self.assertEqual(stats["loss_percent"], 0)

    def test_handles_sub_millisecond_replies(self):
        stats = work_tool.parse_ping_statistics("Reply from 10.1.1.1: bytes=32 time<1ms TTL=64")
        self.assertEqual(stats["samples"], 1)
        self.assertEqual(stats["min_ms"], 1)

    def test_empty_output_returns_empty_dict(self):
        self.assertEqual(work_tool.parse_ping_statistics(""), {})
        self.assertEqual(work_tool.parse_ping_statistics(None), {})


class DiagnosticInputGuards(unittest.TestCase):
    def test_missing_unit_rejected_everywhere(self):
        for fn in (
            work_tool.scrypted_service_status,
            work_tool.pve_host_resources,
            work_tool.camera_reachability_matrix,
            work_tool.run_unit_diagnostics,
        ):
            info, error = fn("")
            self.assertIsNone(info, fn.__name__)
            self.assertTrue(error, fn.__name__)

    def test_ssh_read_requires_host_and_credentials(self):
        out, error = work_tool._ssh_read("", "u", "p", "echo hi")
        self.assertEqual(error, "Missing host")
        out, error = work_tool._ssh_read("10.1.1.1", "", "", "echo hi")
        self.assertIn("Missing SSH credentials", error)

    def test_platform_services_list_is_populated(self):
        self.assertIn("database", work_tool.PLATFORM_SERVICES)
        self.assertIn("cache", work_tool.PLATFORM_SERVICES)
        self.assertEqual(len(set(work_tool.PLATFORM_SERVICES)), len(work_tool.PLATFORM_SERVICES))


class UnitHistoryDatabase(unittest.TestCase):
    def setUp(self):
        # Point the module at a throwaway database for each test.
        self._tmp = tempfile.TemporaryDirectory()
        unit_history._CONN = None
        unit_history._DB_PATH = os.path.join(self._tmp.name, "unit_history.db")

    def tearDown(self):
        if unit_history._CONN is not None:
            unit_history._CONN.close()
        unit_history._CONN = None
        unit_history._DB_PATH = None
        self._tmp.cleanup()

    def test_record_and_read_back(self):
        self.assertTrue(unit_history.record("rd3076", "validate_quick", category="false_positives"))
        entries = unit_history.history("RD3076")
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["healthy"])
        self.assertEqual(entries[0]["category"], "false_positives")

    def test_unit_is_normalised_to_upper(self):
        unit_history.record("rd3076", "validate_quick", category="truly_down")
        self.assertEqual(len(unit_history.history("RD3076")), 1)
        self.assertEqual(len(unit_history.history("rd3076")), 1)

    def test_empty_unit_is_not_recorded(self):
        self.assertFalse(unit_history.record("", "validate_quick"))
        self.assertFalse(unit_history.record(None, "validate_quick"))

    def test_led_overrides_category_for_health(self):
        unit_history.record("RD1", "validate_full", category="nuc_down", led="green")
        self.assertTrue(unit_history.history("RD1")[0]["healthy"])

    def test_flap_summary_counts_transitions_not_checks(self):
        # down, down, up, down, up -> three transitions
        for category in ("truly_down", "truly_down", "false_positives", "truly_down", "false_positives"):
            unit_history.record("RD2", "validate_quick", category=category)
        summary = unit_history.flap_summary("RD2")
        self.assertEqual(summary["checks"], 5)
        self.assertEqual(summary["down_checks"], 3)
        self.assertEqual(summary["transitions"], 3)
        self.assertTrue(summary["currently_healthy"])

    def test_steadily_down_unit_has_no_transitions(self):
        for _ in range(6):
            unit_history.record("RD3", "validate_quick", category="truly_down")
        summary = unit_history.flap_summary("RD3")
        self.assertEqual(summary["transitions"], 0)
        self.assertEqual(summary["down_checks"], 6)
        self.assertFalse(summary["currently_healthy"])

    def test_unknown_unit_summary_is_empty_not_an_error(self):
        summary = unit_history.flap_summary("RD9999")
        self.assertEqual(summary["checks"], 0)
        self.assertIsNone(summary["currently_healthy"])

    def test_fleet_flappers_ranks_by_transitions(self):
        for category in ("truly_down", "false_positives") * 4:
            unit_history.record("RDFLAP", "validate_quick", category=category)
        for _ in range(4):
            unit_history.record("RDSTEADY", "validate_quick", category="false_positives")
        flappers = unit_history.fleet_flappers(min_transitions=3)
        units = [item["unit"] for item in flappers]
        self.assertIn("RDFLAP", units)
        self.assertNotIn("RDSTEADY", units)

    def test_prune_keeps_recent(self):
        unit_history.record("RD4", "validate_quick", category="false_positives")
        self.assertEqual(unit_history.prune(keep_days=180), 0)
        self.assertEqual(len(unit_history.history("RD4")), 1)

    def test_prune_drops_old_rows(self):
        import time as _time
        conn = unit_history._connect()
        old_ts = _time.time() - 200 * 86400
        conn.executemany(
            "INSERT INTO unit_events (unit, ts, kind, category, healthy)"
            " VALUES (?, ?, 'validate_quick', 'truly_down', 0)",
            [("RDOLD", old_ts)] * 20,
        )
        conn.commit()
        unit_history.record("RDNEW", "validate_quick", category="false_positives")
        self.assertEqual(unit_history.prune(keep_days=90), 20)
        self.assertEqual(len(unit_history.history("RDOLD", days=365)), 0)
        self.assertEqual(len(unit_history.history("RDNEW")), 1)

    def test_row_ceiling_is_enforced(self):
        for index in range(30):
            unit_history.record("RDCAP", "validate_quick", category="truly_down",
                                detail=str(index))
        unit_history.prune(keep_days=365, max_events=10)
        self.assertEqual(len(unit_history.history("RDCAP", days=365, limit=999)), 10)

    def test_vacuum_actually_reclaims_disk(self):
        # VACUUM cannot run inside a transaction, and sqlite3 opens one
        # implicitly — get that wrong and prune() silently frees nothing.
        # This test exists because that is exactly what shipped first.
        import time as _time
        conn = unit_history._connect()
        old_ts = _time.time() - 200 * 86400
        conn.executemany(
            "INSERT INTO unit_events (unit, ts, kind, category, healthy, detail)"
            " VALUES (?, ?, 'validate_quick', 'truly_down', 0, ?)",
            [("RDBULK", old_ts, "x" * 200)] * 6000,
        )
        conn.commit()
        unit_history.compact()
        before = unit_history.file_size_bytes()
        deleted = unit_history.prune(keep_days=90)
        self.assertGreaterEqual(deleted, 6000)
        after = unit_history.file_size_bytes()
        self.assertLess(after, before, "prune() did not return disk space to the OS")

    def test_file_size_and_stats_agree(self):
        unit_history.record("RD6", "validate_quick", category="false_positives")
        info = unit_history.stats()
        self.assertGreater(info["bytes"], 0)
        self.assertEqual(info["bytes"], unit_history.file_size_bytes())
        self.assertIsNotNone(info["bytes_per_event"])

    def test_stats_reports_counts(self):
        unit_history.record("RD5", "validate_quick", category="false_positives")
        info = unit_history.stats()
        self.assertTrue(info["ok"])
        self.assertEqual(info["events"], 1)
        self.assertEqual(info["units"], 1)


if __name__ == "__main__":
    unittest.main()
