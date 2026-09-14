"""
Tests for the read-only diagnostics and the SQLite validation history.

Like test_parsing.py these are pure: the SSH-backed functions are only
exercised through their input guards, and unit_history runs against a
temporary database rather than the real data dir.
"""

import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402
import work_tool.diagnostics  # noqa: E402
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


class CombinedPowerInfraAlertsSiteFilter(unittest.TestCase):
    # Same "no ERP Site linked = not a real, currently-deployed trailer"
    # exclusion as the fleet reports (see
    # FleetVrmInstallationsSiteFilter in test_weather.py) — a trailer with
    # an active Zabbix/VRM alarm but no Site is noise a tech can't act on.
    def _patched(self, zabbix_by_unit, vrm_by_unit, site_cache_contents):
        def fake_site_map(names, cache, headers=None, quiet=False):
            cache.update(site_cache_contents)

        return (
            mock.patch.object(
                work_tool.diagnostics, "zabbix_active_problems_by_unit",
                return_value=(zabbix_by_unit, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "vrm_active_alarms_by_unit",
                return_value=(vrm_by_unit, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "_erp_heads_for_mu_trailers", return_value=({}, None)
            ),
            mock.patch.object(
                work_tool.diagnostics, "_fetch_erp_component_site_map", side_effect=fake_site_map
            ),
        )

    def test_mu_with_no_site_is_excluded_even_though_alarmed(self):
        zabbix_by_unit = {
            "MU1001": [{"device": "Router", "host": "MU1001-Router", "name": "p", "severity": 3, "clock": 1}],
            "MU1002": [{"device": "Router", "host": "MU1002-Router", "name": "p", "severity": 3, "clock": 1}],
        }
        p1, p2, p3, p4 = self._patched(
            zabbix_by_unit, {},
            {
                "SC-MU1001": {"name": "SC-MU1001", "site": "SITE-A"},
                "SC-MU1002": {"name": "SC-MU1002", "site": ""},
            },
        )
        with p1, p2, p3, p4:
            info, error = work_tool.diagnostics.combined_power_infra_alerts()
        self.assertIsNone(error)
        units = sorted(r["unit"] for r in info["rows"])
        self.assertEqual(units, ["MU1001"])

    def test_non_mu_units_are_never_site_filtered(self):
        # RD/FD heads aren't trailers — the "no Site" exclusion only
        # applies to MU-prefixed rows (see combined_power_infra_alerts).
        zabbix_by_unit = {
            "RD3076": [{"device": "Router", "host": "RD3076-Router", "name": "p", "severity": 3, "clock": 1}],
        }
        p1, p2, p3, p4 = self._patched(zabbix_by_unit, {}, {})
        with p1, p2, p3, p4:
            info, error = work_tool.diagnostics.combined_power_infra_alerts()
        self.assertIsNone(error)
        self.assertEqual([r["unit"] for r in info["rows"]], ["RD3076"])

    def test_site_lookup_failure_fails_open_and_keeps_every_mu(self):
        zabbix_by_unit = {
            "MU1001": [{"device": "Router", "host": "MU1001-Router", "name": "p", "severity": 3, "clock": 1}],
        }
        p1, p2, p3, _p4 = self._patched(zabbix_by_unit, {}, {})
        with p1, p2, p3, mock.patch.object(
            work_tool.diagnostics, "_fetch_erp_component_site_map",
            side_effect=RuntimeError("ERP unreachable"),
        ):
            info, error = work_tool.diagnostics.combined_power_infra_alerts()
        self.assertIsNone(error)
        self.assertEqual([r["unit"] for r in info["rows"]], ["MU1001"])


class ParseSwitchUptimeSeconds(unittest.TestCase):
    def test_real_robofiber_text_with_singular_hour(self):
        # Checked live (RD3343): "1 Hour", not "1 Hours" — the parser has
        # to handle both, since Netonix's own text is always plural (see
        # _format_switch_uptime_seconds).
        seconds = work_tool.diagnostics._parse_switch_uptime_seconds(
            "Running Time            : 151 Days 1 Hour 31 Mins 3 Secs"
        )
        self.assertEqual(seconds, 151 * 86400 + 3600 + 31 * 60 + 3)

    def test_netonix_style_always_plural(self):
        seconds = work_tool.diagnostics._parse_switch_uptime_seconds(
            "Uptime: 18 Days 0 Hours 0 Mins 0 Secs"
        )
        self.assertEqual(seconds, 18 * 86400)

    def test_unparseable_text_returns_none(self):
        self.assertIsNone(work_tool.diagnostics._parse_switch_uptime_seconds(""))
        self.assertIsNone(work_tool.diagnostics._parse_switch_uptime_seconds(None))
        self.assertIsNone(work_tool.diagnostics._parse_switch_uptime_seconds("System Name: SC-RD3343-Switch"))


class LatestHighLossWindow(unittest.TestCase):
    def test_finds_the_most_recent_run_not_the_first(self):
        points = [
            {"t": 1000, "v": 100.0},
            {"t": 2000, "v": 100.0},
            {"t": 3000, "v": 5.0},
            {"t": 4000, "v": 95.0},
            {"t": 5000, "v": 95.0},
            {"t": 6000, "v": 3.0},
        ]
        window = work_tool.diagnostics._latest_high_loss_window(points)
        self.assertEqual(window, (4000, 5000, 2))

    def test_no_qualifying_point_returns_none(self):
        points = [{"t": 1000, "v": 10.0}, {"t": 2000, "v": 50.0}]
        self.assertIsNone(work_tool.diagnostics._latest_high_loss_window(points))

    def test_empty_points_returns_none(self):
        self.assertIsNone(work_tool.diagnostics._latest_high_loss_window([]))
        self.assertIsNone(work_tool.diagnostics._latest_high_loss_window(None))

    def test_unordered_input_is_sorted_first(self):
        points = [
            {"t": 3000, "v": 5.0},
            {"t": 2000, "v": 100.0},
            {"t": 1000, "v": 100.0},
        ]
        window = work_tool.diagnostics._latest_high_loss_window(points)
        self.assertEqual(window, (1000, 2000, 2))


class NetworkLatencyHistoryLossAggregate(unittest.TestCase):
    # Reported live (2026-09-14, RD3020): a real ~29-minute 100%-loss
    # window averaged down to ~25-32% per hour once unit_power_vs_cell_
    # outage's 2-week default pushed the lookup into Zabbix's hourly-trend
    # data — well under the 90% detection threshold, silently missing a
    # real outage. loss_aggregate="max" (what that check now asks for)
    # uses each hour's own peak loss instead of its average.
    def _fake_zabbix_call(self, method, params):
        if method == "host.get":
            return [
                {"hostid": "1", "host": "RD9999-Router"},
                {"hostid": "2", "host": "RD9999-Switch"},
            ]
        if method == "item.get":
            return [
                {"itemid": "10", "key_": "icmppingsec", "value_type": 0, "hostid": "1"},
                {"itemid": "11", "key_": "icmppingloss", "value_type": 0, "hostid": "1"},
                {"itemid": "12", "key_": "icmppingsec", "value_type": 0, "hostid": "2"},
                {"itemid": "13", "key_": "icmppingloss", "value_type": 0, "hostid": "2"},
            ]
        if method == "trend.get":
            # Every trend point has a real 25% average alongside a 100%
            # max — the same shape a genuine ~15-minute-per-hour outage
            # produces once bucketed hourly.
            return [{"clock": 1000, "value_avg": "25.0", "value_max": "100.0"}]
        raise AssertionError(f"unexpected Zabbix method: {method}")

    def test_max_aggregate_uses_peak_loss_not_average(self):
        with mock.patch.object(
            work_tool.diagnostics, "_zabbix_call", side_effect=self._fake_zabbix_call,
        ):
            info, error = work_tool.diagnostics.unit_network_latency_history(
                "RD9999", hours=24 * 14, loss_aggregate="max",
            )
        self.assertIsNone(error)
        self.assertEqual(info["resolution"], "hourly average")
        self.assertEqual(info["charts"]["router_loss"]["points"][0]["v"], 100.0)
        self.assertEqual(info["charts"]["switch_loss"]["points"][0]["v"], 100.0)
        # Response-time metrics are unaffected by loss_aggregate — still avg.
        self.assertEqual(info["charts"]["router_response"]["points"][0]["v"], 25.0)

    def test_default_aggregate_still_uses_average(self):
        with mock.patch.object(
            work_tool.diagnostics, "_zabbix_call", side_effect=self._fake_zabbix_call,
        ):
            info, error = work_tool.diagnostics.unit_network_latency_history(
                "RD9999", hours=24 * 14,
            )
        self.assertIsNone(error)
        self.assertEqual(info["charts"]["router_loss"]["points"][0]["v"], 25.0)
        self.assertEqual(info["charts"]["switch_loss"]["points"][0]["v"], 25.0)


class PowerVsCellOutageVerdict(unittest.TestCase):
    # The exact real-world example Andrew described: a unit whose switch
    # has been up 18 days, with a ~100% router-loss window from
    # 2026-09-09 15:31 UTC to 2026-09-10 18:50 UTC — confirmed by hand as
    # a cell outage (the switch never lost power; the outage predates it
    # by weeks). Mocks only the network-backed pieces
    # (get_robofiber_uptime / unit_network_latency_history); the
    # comparison logic itself runs for real.
    def _loss_points(self, start_dt, end_dt):
        points = [{"t": int((start_dt - dt.timedelta(minutes=30)).timestamp() * 1000), "v": 5.0}]
        t = start_dt
        while t <= end_dt:
            points.append({"t": int(t.timestamp() * 1000), "v": 100.0})
            t += dt.timedelta(minutes=3)
        points.append({"t": int((end_dt + dt.timedelta(minutes=30)).timestamp() * 1000), "v": 3.0})
        return points

    def test_cell_outage_when_switch_predates_the_whole_window(self):
        start = dt.datetime(2026, 9, 9, 15, 31, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 9, 10, 18, 50, tzinfo=dt.timezone.utc)
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 18 Days 0 Hours 0 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=(
                    {"charts": {"router_loss": {"points": self._loss_points(start, end)}}}, None,
                ),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "cell_outage")

    def test_power_outage_when_switch_came_up_at_window_end(self):
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
        start = end - dt.timedelta(minutes=40)
        uptime_seconds = int((dt.datetime.now(dt.timezone.utc) - end).total_seconds())
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": f"Uptime: 0 Days 0 Hours 0 Mins {uptime_seconds} Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=(
                    {"charts": {"router_loss": {"points": self._loss_points(start, end)}}}, None,
                ),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "power_outage")

    def test_inconclusive_when_neither_edge_matches(self):
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        start = end - dt.timedelta(minutes=30)
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                # Rebooted 2 hours ago — well inside the window, matching
                # neither its start nor its end.
                return_value=({"uptime": "Uptime: 0 Days 2 Hours 0 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=(
                    {"charts": {"router_loss": {"points": self._loss_points(start, end)}}}, None,
                ),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "inconclusive")

    def test_no_recent_outage_when_no_high_loss_window(self):
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 5 Days 0 Hours 0 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=(
                    {"charts": {"router_loss": {"points": [{"t": 1000, "v": 5.0}]}}}, None,
                ),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "no_recent_outage")

    def test_unparseable_uptime_is_an_error_not_a_wrong_guess(self):
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
        start = end - dt.timedelta(minutes=40)
        with (
            # A real loss window has to exist for SSH to even be reached —
            # see unit_power_vs_cell_outage's cheap-Zabbix-first reorder.
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=(
                    {"charts": {"router_loss": {"points": self._loss_points(start, end)}}}, None,
                ),
            ),
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": ""}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(info)
        self.assertIn("Could not parse", error)

    def test_no_recent_outage_never_calls_ssh_uptime(self):
        # The whole point of checking Zabbix first — a unit with nothing
        # to explain shouldn't cost a switch SSH connection at all.
        with (
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": [{"t": 1000, "v": 5.0}]}}}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                side_effect=AssertionError("SSH should not have been called"),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "no_recent_outage")

    def test_default_window_is_two_weeks_not_three_days(self):
        # Reported live: RD3122's switch had been up 5+ days with nothing
        # to compare against inside the old 72h default — the outage that
        # actually explained it was simply older than the window checked.
        captured = {}

        def fake_latency_history(unit, hours, loss_aggregate="avg"):
            captured["hours"] = hours
            captured["loss_aggregate"] = loss_aggregate
            return {"charts": {"router_loss": {"points": []}}}, None

        with mock.patch.object(
            work_tool.diagnostics, "unit_network_latency_history",
            side_effect=fake_latency_history,
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(captured["hours"], 24 * 14)
        self.assertIn("336h", info["reason"])
        # See NetworkLatencyHistoryLossAggregate — "avg" would dilute a
        # real sustained outage shorter than an hour below the 90%
        # threshold once this pushes into Zabbix's hourly-trend data.
        self.assertEqual(captured["loss_aggregate"], "max")

    def test_coarse_tolerance_applies_to_an_hourly_trend_window(self):
        # Past 7 days, unit_network_latency_history falls back to Zabbix
        # trend (hourly-average) data — the loss window's own start/end
        # then only land on hour boundaries, not individual ~3-minute
        # polls, so a switch that came up 40 minutes after the window
        # "ended" (well outside the native 15-minute tolerance, but inside
        # the widened one for this resolution) should still resolve as a
        # real power-outage match, not inconclusive.
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)
        start = end - dt.timedelta(hours=3)
        uptime_seconds = int(
            (dt.datetime.now(dt.timezone.utc) - (end + dt.timedelta(minutes=40))).total_seconds()
        )
        points = self._loss_points(start, end)
        with (
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=(
                    {
                        "charts": {"router_loss": {"points": points}},
                        "resolution": "hourly average",
                    },
                    None,
                ),
            ),
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": f"Uptime: 0 Days 0 Hours 0 Mins {uptime_seconds} Secs"}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999", hours=24 * 14)
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "power_outage")


if __name__ == "__main__":
    unittest.main()
