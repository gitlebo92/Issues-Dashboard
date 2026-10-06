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

    def test_flap_summary_timeline_is_chronological_and_matches_checks(self):
        # The Flap Report's per-unit status bar renders this directly — it
        # has to be in the same chronological order flap_summary itself
        # counts transitions in, and line up 1:1 with "checks".
        for category in ("truly_down", "truly_down", "false_positives", "truly_down", "false_positives"):
            unit_history.record("RD2TIMELINE", "validate_quick", category=category)
        summary = unit_history.flap_summary("RD2TIMELINE")
        self.assertEqual(len(summary["timeline"]), summary["checks"])
        healthy_sequence = [point["healthy"] for point in summary["timeline"]]
        self.assertEqual(healthy_sequence, [False, False, True, False, True])
        timestamps = [point["ts"] for point in summary["timeline"]]
        self.assertEqual(timestamps, sorted(timestamps))

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
    def setUp(self):
        # unit_power_vs_cell_outage caches a confirmed switch_up_since per
        # unit (work_tool.diagnostics._SWITCH_UPTIME_CACHE) so a repeat
        # sweep with nothing new to explain skips the SSH round trip. Every
        # test here reuses the same unit ("RD9999"), so without clearing
        # this between tests, a later test's mocked get_robofiber_uptime
        # would never even get called — it'd silently reuse an earlier
        # test's cached value instead.
        work_tool.diagnostics._SWITCH_UPTIME_CACHE.clear()

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
        # Switch rebooted INSIDE the window itself — genuinely ambiguous
        # (could be power loss mid-outage, could be an unrelated
        # coincidental reboot). Distinct from the switch rebooting well
        # AFTER the window already ended, which now gets its own hedged
        # cell_outage read — see test_hedged_cell_outage_when_switch_
        # rebooted_after_an_older_window below.
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)
        start = end - dt.timedelta(minutes=40)
        reboot_time = start + dt.timedelta(minutes=15)
        uptime_seconds = int((dt.datetime.now(dt.timezone.utc) - reboot_time).total_seconds())
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
        self.assertEqual(info["verdict"], "inconclusive")

    def test_hedged_cell_outage_when_switch_rebooted_after_an_older_window(self):
        # Reported live (RD3020, 2026-09-14): the switch's current uptime
        # traced back only a few hours, entirely unrelated to a real
        # outage from the day before. Per Andrew's own read, a window the
        # current uptime doesn't reach back to at all — the switch has
        # SINCE rebooted again for some other reason — still points to
        # cellular, just hedged rather than certain.
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        start = end - dt.timedelta(minutes=30)
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                # Rebooted 2 hours ago — the window ended a full day ago.
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
        self.assertEqual(info["verdict"], "cell_outage")
        self.assertIn("since rebooted again", info["reason"])

    def test_longer_window_wins_when_windows_disagree(self):
        # Two qualifying windows that read DIFFERENTLY: an old, 2-day cell
        # outage (switch was still up minutes ago, long after this window
        # ended, so it reads as cell_after_reboot) and a short, 20-minute
        # window that lines up exactly with the switch's own recent
        # reboot (power_outage). The most recent window alone would say
        # "power outage" — Andrew's rule says the longer one (cell) is the
        # relevant verdict instead.
        now = dt.datetime.now(dt.timezone.utc)
        switch_up_since = now - dt.timedelta(minutes=10)

        cell_start = now - dt.timedelta(days=10)
        cell_end = cell_start + dt.timedelta(days=2)
        power_end = switch_up_since
        power_start = power_end - dt.timedelta(minutes=20)

        points = self._loss_points(cell_start, cell_end) + self._loss_points(power_start, power_end)
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 0 Days 0 Hours 10 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": points}}}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "cell_outage")
        self.assertIn("power outage", info["reason"])
        self.assertIn("relevant one", info["reason"])
        # The chosen window is the long-ago cell outage, not the recent
        # power-shaped one.
        self.assertAlmostEqual(info["loss_window_start"], cell_start.timestamp(), delta=200)

    def test_ticket_creation_time_overrides_duration(self):
        # Same two disagreeing windows as the duration test above, but this
        # time the ticket was opened right in the middle of the SHORT
        # power window. Andrew's rule: the ticket's own creation time is
        # the real signal for which outage it's about, and outranks the
        # longer-duration fallback.
        now = dt.datetime.now(dt.timezone.utc)
        switch_up_since = now - dt.timedelta(minutes=10)

        cell_start = now - dt.timedelta(days=10)
        cell_end = cell_start + dt.timedelta(days=2)
        power_end = switch_up_since
        power_start = power_end - dt.timedelta(minutes=20)

        points = self._loss_points(cell_start, cell_end) + self._loss_points(power_start, power_end)
        ticket_opened = power_start + (power_end - power_start) / 2
        creation_text = ticket_opened.astimezone(work_tool.diagnostics._ARIZONA_TZ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 0 Days 0 Hours 10 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": points}}}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "_fetch_erp_issue_doc",
                return_value=({"creation": creation_text}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999", issue_id="ISS-1")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "power_outage")
        self.assertEqual(info["window_picked_by"], "ticket_creation")
        self.assertAlmostEqual(info["loss_window_start"], power_start.timestamp(), delta=200)
        self.assertIn("matching the ticket's own creation time", info["reason"])

    def test_ticket_lookup_failure_falls_back_to_duration(self):
        # Same setup, but the ERP Issue lookup itself fails — should
        # degrade to the duration fallback (cell outage, the longer
        # window) rather than erroring the whole diagnostic out.
        now = dt.datetime.now(dt.timezone.utc)
        switch_up_since = now - dt.timedelta(minutes=10)

        cell_start = now - dt.timedelta(days=10)
        cell_end = cell_start + dt.timedelta(days=2)
        power_end = switch_up_since
        power_start = power_end - dt.timedelta(minutes=20)

        points = self._loss_points(cell_start, cell_end) + self._loss_points(power_start, power_end)

        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 0 Days 0 Hours 10 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": points}}}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "_fetch_erp_issue_doc",
                return_value=(None, "ISS-1 was not found in ERP"),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999", issue_id="ISS-1")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "cell_outage")
        self.assertEqual(info["window_picked_by"], "duration")
        self.assertIn("could not check the ticket's creation time", info["reason"])

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

    def test_repeat_sweep_with_same_window_skips_ssh_uptime(self):
        # The redundant-check case this cache exists for: a scheduled
        # sweep re-runs against the same already-explained loss window
        # (still inside the 14-day lookback) and shouldn't SSH again for
        # an answer it already has.
        start = dt.datetime(2026, 9, 9, 15, 31, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 9, 10, 18, 50, tzinfo=dt.timezone.utc)
        points = self._loss_points(start, end)
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 18 Days 0 Hours 0 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": points}}}, None),
            ),
        ):
            first, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)

        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                side_effect=AssertionError("SSH should not have been called again"),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": points}}}, None),
            ),
        ):
            second, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(second["verdict"], first["verdict"])
        self.assertEqual(second["switch_up_since"], first["switch_up_since"])

    def test_new_window_after_cached_check_still_ssh_uptime(self):
        # A cached answer only covers windows it already scored — a
        # genuinely new loss window (possibly from a fresh reboot) must
        # still trigger a real SSH check, not reuse the stale cache.
        old_start = dt.datetime(2026, 9, 9, 15, 31, tzinfo=dt.timezone.utc)
        old_end = dt.datetime(2026, 9, 10, 18, 50, tzinfo=dt.timezone.utc)
        with (
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": "Uptime: 18 Days 0 Hours 0 Mins 0 Secs"}, None),
            ),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": self._loss_points(old_start, old_end)}}}, None),
            ),
        ):
            work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")

        # Back-date the cached checked_at, as if that first check happened
        # right after the old window — anything after that point is a
        # window the cache hasn't seen yet.
        cached = work_tool.diagnostics._SWITCH_UPTIME_CACHE["RD9999"]
        cached["checked_at"] = old_end.timestamp() + 3600

        new_start = old_end + dt.timedelta(hours=2)
        new_end = old_end + dt.timedelta(hours=3)
        combined_points = self._loss_points(old_start, old_end) + self._loss_points(new_start, new_end)
        calls = []

        def fake_uptime(unit):
            calls.append(unit)
            return {"uptime": "Uptime: 0 Days 0 Hours 45 Mins 0 Secs"}, None

        with (
            mock.patch.object(work_tool.diagnostics, "get_robofiber_uptime", side_effect=fake_uptime),
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                return_value=({"charts": {"router_loss": {"points": combined_points}}}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(calls, ["RD9999"])

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
        # real power-outage match, not inconclusive. The window here is
        # 10 days old — outside the native (7-day) phase's own range, so
        # unit_power_vs_cell_outage's two-phase lookup only finds it on
        # the older, hourly-trend fallback (see NetworkLatencyHistoryLossAggregate
        # and unit_power_vs_cell_outage's own native-then-older design).
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)
        start = end - dt.timedelta(hours=3)
        uptime_seconds = int(
            (dt.datetime.now(dt.timezone.utc) - (end + dt.timedelta(minutes=40))).total_seconds()
        )
        points = self._loss_points(start, end)

        def fake_latency_history(unit, hours, loss_aggregate="avg"):
            if hours >= 24 * 14:
                return (
                    {"charts": {"router_loss": {"points": points}}, "resolution": "hourly average"},
                    None,
                )
            # Native (7-day) phase — the real window is 10 days old, well
            # outside this range, so it genuinely finds nothing.
            return {"charts": {"router_loss": {"points": []}}, "resolution": "native (~3min)"}, None

        with (
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                side_effect=fake_latency_history,
            ),
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": f"Uptime: 0 Days 0 Hours 0 Mins {uptime_seconds} Secs"}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999", hours=24 * 14)
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "power_outage")

    def test_native_window_preferred_over_older_trend_data(self):
        # Reported live (RD3124, 2026-09-14): a real, precise ~101-minute
        # outage 3 days old — well within native range — was getting
        # coarsened to a meaningless single-hour window because the
        # 2-week DEFAULT lookback alone pushed the whole query into
        # hourly-trend mode, regardless of how recent the event actually
        # was. The native (7-day) phase must be tried FIRST and, once it
        # finds a window, used as-is — the older/trend phase must not run
        # at all in that case (asserted here via a side_effect that raises
        # if it's ever asked for a >7-day window).
        end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)
        start = end - dt.timedelta(minutes=101)
        uptime_seconds = int((dt.datetime.now(dt.timezone.utc) - end).total_seconds())
        native_points = self._loss_points(start, end)

        def fake_latency_history(unit, hours, loss_aggregate="avg"):
            if hours > 24 * 7:
                raise AssertionError("older/trend phase should not run when native already found a window")
            return {"charts": {"router_loss": {"points": native_points}}, "resolution": "native (~3min)"}, None

        with (
            mock.patch.object(
                work_tool.diagnostics, "unit_network_latency_history",
                side_effect=fake_latency_history,
            ),
            mock.patch.object(
                work_tool.diagnostics, "get_robofiber_uptime",
                return_value=({"uptime": f"Uptime: 0 Days 0 Hours 0 Mins {uptime_seconds} Secs"}, None),
            ),
        ):
            info, error = work_tool.diagnostics.unit_power_vs_cell_outage("RD9999")
        self.assertIsNone(error)
        self.assertEqual(info["verdict"], "power_outage")
        # The precise native window (within one ~3-min poll step), not a
        # coarsened, hour-bucket-collapsed one.
        self.assertAlmostEqual(info["loss_window_end"], end.timestamp(), delta=200)


class FleetPowerVsCellOutageIssueIds(unittest.TestCase):
    # Up Steady rows are real ERP tickets too — fleet_power_vs_cell_outage_status
    # takes an optional {unit: issue_id} map and must pass each unit's own
    # issue_id straight through to unit_power_vs_cell_outage, not mix them
    # up or drop the ones with no mapping.
    def test_each_unit_gets_its_own_mapped_issue_id(self):
        seen = {}

        def fake_check(unit, issue_id=None):
            seen[unit] = issue_id
            return {"unit": unit, "verdict": "no_recent_outage"}, None

        with mock.patch.object(
            work_tool.diagnostics, "unit_power_vs_cell_outage", side_effect=fake_check
        ):
            rows, error = work_tool.diagnostics.fleet_power_vs_cell_outage_status(
                ["RD3076", "RD3132"],
                unit_issue_ids={"RD3076": "ISS-1"},
            )
        self.assertIsNone(error)
        self.assertEqual(seen, {"RD3076": "ISS-1", "RD3132": None})
        self.assertEqual({row["unit"] for row in rows}, {"RD3076", "RD3132"})

    def test_missing_unit_issue_ids_defaults_to_none_for_everyone(self):
        seen = {}

        def fake_check(unit, issue_id=None):
            seen[unit] = issue_id
            return {"unit": unit, "verdict": "no_recent_outage"}, None

        with mock.patch.object(
            work_tool.diagnostics, "unit_power_vs_cell_outage", side_effect=fake_check
        ):
            rows, error = work_tool.diagnostics.fleet_power_vs_cell_outage_status(["RD3076"])
        self.assertIsNone(error)
        self.assertEqual(seen, {"RD3076": None})


class RebootBounceNote(unittest.TestCase):
    def test_no_note_when_no_data_near_reboot(self):
        # No Zabbix points at all near the reboot — a data gap, not
        # evidence of a clean bounce; stays silent rather than asserting one.
        note = work_tool.diagnostics._reboot_bounce_note(1000.0, [], 900)
        self.assertIsNone(note)

    def test_no_note_when_elevated_loss_nearby(self):
        loss_points = [{"t": 1000_000, "v": 45.0}]  # 45% loss at t=1000s
        note = work_tool.diagnostics._reboot_bounce_note(1000.0, loss_points, 900)
        self.assertIsNone(note)

    def test_note_when_flat_near_reboot(self):
        loss_points = [{"t": 1000_000, "v": 0.0}, {"t": 1100_000, "v": 5.0}]
        note = work_tool.diagnostics._reboot_bounce_note(1000.0, loss_points, 900)
        self.assertIsNotNone(note)
        self.assertIn("bounce", note)


class NucDiskHealthSummary(unittest.TestCase):
    """
    _summarize_nuc_disk_health turns the NUC's PowerShell JSON into a verdict.
    Base case is RD1009's real output (2026-10-05): three healthy drives and
    the RAM drive's routine "write cache disabled" warning.
    """

    NOW = dt.datetime(2026, 10, 5, 18, 0, tzinfo=dt.timezone.utc)

    def _rd1009(self):
        return {
            "Disks": [
                {"DeviceId": "2", "Name": "Miray RAM Drive", "Media": "Unspecified", "Bus": "SCSI",
                 "Health": "Healthy", "Operational": "OK", "SizeGB": 1},
                {"DeviceId": "1", "Name": "HP SSD EX900 250GB", "Media": "SSD", "Bus": "NVMe",
                 "Health": "Healthy", "Operational": "OK", "SizeGB": 233},
                {"DeviceId": "0", "Name": "ST2000LM015-2E8174", "Media": "HDD", "Bus": "SATA",
                 "Health": "Healthy", "Operational": "OK", "SizeGB": 1863},
            ],
            "Reliability": [
                {"DeviceId": "1", "Temperature": 51, "TemperatureMax": 70, "Wear": 0},
                {"DeviceId": "0", "Temperature": 44, "Wear": 0, "ReadErrorsTotal": 52,
                 "ReadErrorsUncorrected": 0, "PowerOnHours": 53537},
            ],
            "Predict": {"Instance": "SCSI\\Disk&Ven_&Prod_ST2000LM015-2E81\\4&31bbc50&0&020000_0",
                        "PredictFailure": False, "Reason": 0},
            "Events": {"Provider": "disk", "Id": 34, "Level": 3, "Time": "2026-10-05T17:14:34Z",
                       "Message": "The driver disabled the write cache on device \\Device\\Harddisk2\\DR2."},
        }

    def _summarize(self, parsed):
        return work_tool.diagnostics._summarize_nuc_disk_health("RD1009", parsed, now=self.NOW)

    def test_rd1009_is_healthy_and_single_objects_are_handled(self):
        # Predict and Events come back as bare objects (one item each).
        info = self._summarize(self._rd1009())
        self.assertEqual(info["status"], "ok")
        seagate = next(d for d in info["disks"] if d["name"].startswith("ST2000"))
        self.assertIs(seagate["predict_failure"], False)
        self.assertEqual(seagate["read_errors_total"], 52)
        self.assertEqual(info["events"][0]["disk"], "Miray RAM Drive")
        self.assertEqual(info["events"][0]["tier"], "other")

    def test_recent_bad_block_fails(self):
        parsed = self._rd1009()
        parsed["Events"] = [
            {"Provider": "disk", "Id": 7, "Level": 2, "Time": "2026-10-04T09:00:00Z",
             "Message": "The device, \\Device\\Harddisk0\\DR0, has a bad block."},
            {"Provider": "disk", "Id": 7, "Level": 2, "Time": "2026-10-03T09:00:00Z",
             "Message": "The device, \\Device\\Harddisk0\\DR0, has a bad block."},
        ]
        info = self._summarize(parsed)
        self.assertEqual(info["status"], "fail")
        self.assertIn("2x bad block", info["reasons"][0])
        self.assertEqual(info["events"][0]["disk"], "ST2000LM015-2E8174")

    def test_old_critical_event_only_warns(self):
        parsed = self._rd1009()
        parsed["Events"] = [{"Provider": "Microsoft-Windows-Ntfs", "Id": 55, "Level": 2,
                             "Time": "2026-08-01T00:00:00Z", "Message": "A corruption was discovered."}]
        info = self._summarize(parsed)
        self.assertEqual(info["status"], "warn")

    def test_storage_reset_is_a_warning(self):
        parsed = self._rd1009()
        parsed["Events"] = [{"Provider": "stornvme", "Id": 129, "Level": 3,
                             "Time": "2026-10-05T10:00:00Z", "Message": "Reset to device was issued."}]
        info = self._summarize(parsed)
        self.assertEqual(info["status"], "warn")
        self.assertEqual(info["events"][0]["meaning"], "drive stopped responding and was reset")

    def test_unhealthy_drive_predict_fail_or_uncorrected_errors_fail(self):
        for mutate in (
            lambda p: p["Disks"][2].update(Health="Warning"),
            lambda p: p["Predict"].update(PredictFailure=True),
            lambda p: p["Reliability"][1].update(ReadErrorsUncorrected=3),
        ):
            parsed = self._rd1009()
            mutate(parsed)
            self.assertEqual(self._summarize(parsed)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
