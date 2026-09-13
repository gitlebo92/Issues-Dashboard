"""
Pure-function regression tests for work_tool's VRM AC-power inference.

_ac_power_status_from_diagnostics takes a plain list of dicts (a VRM
/diagnostics "records" payload) and returns a verdict — no network, no ERP,
so it belongs here alongside the other parsing/classification tests:

    python -m unittest discover -s tests -v

These specifically guard the freshness fix found by live investigation
(2026-09-13): a real unit (MU8068) had charger fields (cSt/cI/c0V/c0I)
that were still returning an active-looking "Absorption, 1A AC" reading
while those exact fields' own timestamps were ~5 months old. Without a
per-field timestamp check, that reads as a confident "plugged in" — this
is the regression test for the fix.
"""

import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402
import work_tool.weather  # noqa: E402


def _diag(code, formatted_value, age_seconds=0):
    return {
        "code": code,
        "formattedValue": formatted_value,
        "timestamp": time.time() - age_seconds,
    }


class AcPowerStatusFromDiagnostics(unittest.TestCase):
    def test_no_charger_fields_at_all_is_no_charger_hardware(self):
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics([
            _diag("bs", "50 %"),
            _diag("bv", "26.0V"),
        ])
        self.assertEqual(status, "no_charger_hardware")
        self.assertIsNone(age)

    def test_fresh_active_state_with_real_output_is_present_high_confidence(self):
        records = [
            _diag("cSt", "Absorption", age_seconds=60),
            _diag("cI", "1.2A", age_seconds=60),
            _diag("c0V", "28.4V", age_seconds=60),
            _diag("c0I", "3.0A", age_seconds=60),
        ]
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics(records)
        self.assertEqual(status, "present")
        self.assertEqual(confidence, 96)
        self.assertLess(age, 120)

    def test_stale_charger_fields_do_not_report_present(self):
        # The exact real-world case: an active-looking charge state and
        # real-looking DC output, but the fields are ~5 months old. Must
        # NOT come back "present" no matter how convincing the value —
        # this is the whole point of the freshness check.
        five_months_seconds = 5 * 30 * 24 * 3600
        records = [
            _diag("cSt", "Absorption", age_seconds=five_months_seconds),
            _diag("cI", "1A", age_seconds=five_months_seconds),
            _diag("c0V", "28.4V", age_seconds=five_months_seconds),
            _diag("c0I", "2.3A", age_seconds=five_months_seconds),
        ]
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics(records)
        self.assertEqual(status, "stale")
        self.assertIsNone(confidence)
        self.assertGreater(age, 24 * 3600)
        self.assertIn("too old", detail)

    def test_off_state_no_power_evidence_is_not_detected(self):
        records = [
            _diag("cSt", "Off", age_seconds=60),
            _diag("cI", "0.0A", age_seconds=60),
        ]
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics(records)
        self.assertEqual(status, "not_detected")

    def test_off_state_with_power_evidence_is_uncertain(self):
        # A contradiction between state and reading — different from a
        # clean "off with nothing else" read, so it must not collapse to
        # the same near-zero confidence.
        records = [
            _diag("cSt", "Off", age_seconds=60),
            _diag("c0V", "28.4V", age_seconds=60),
            _diag("c0I", "3.0A", age_seconds=60),
        ]
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics(records)
        self.assertEqual(status, "uncertain")
        self.assertEqual(confidence, 50)

    def test_fault_state_with_real_output_is_present_not_not_detected(self):
        # The RD3315 case from this session: charger faulted but still
        # outputting real DC watts — AC is present, the fault is a
        # separate (battery-side) problem.
        records = [
            _diag("cSt", "Fault", age_seconds=60),
            _diag("cI", "1.0A", age_seconds=60),
            _diag("c0V", "23.96V", age_seconds=60),
            _diag("c0I", "3.9A", age_seconds=60),
            _diag("cE", "Err 20: Bulk time limit reached", age_seconds=60),
        ]
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics(records)
        self.assertEqual(status, "present")
        self.assertEqual(confidence, 70)
        self.assertIn("faulted", detail)

    def test_fault_state_with_no_output_is_not_detected(self):
        records = [
            _diag("cSt", "Fault", age_seconds=60),
            _diag("cI", "0.0A", age_seconds=60),
        ]
        status, detail, confidence, age = work_tool._ac_power_status_from_diagnostics(records)
        self.assertEqual(status, "not_detected")


class VrmFreshnessTier(unittest.TestCase):
    def test_none_is_unknown(self):
        self.assertEqual(work_tool._vrm_freshness_tier(None), "unknown")

    def test_within_ten_minutes_is_fresh(self):
        self.assertEqual(work_tool._vrm_freshness_tier(5 * 60), "fresh")

    def test_between_ten_minutes_and_two_hours_is_aging(self):
        self.assertEqual(work_tool._vrm_freshness_tier(30 * 60), "aging")

    def test_between_two_and_twenty_four_hours_is_stale(self):
        self.assertEqual(work_tool._vrm_freshness_tier(6 * 3600), "stale")

    def test_beyond_a_day_is_disconnected(self):
        self.assertEqual(work_tool._vrm_freshness_tier(2 * 86400), "disconnected")

    def test_boundaries_are_inclusive_on_the_fresher_side(self):
        self.assertEqual(work_tool._vrm_freshness_tier(600), "fresh")
        self.assertEqual(work_tool._vrm_freshness_tier(601), "aging")
        self.assertEqual(work_tool._vrm_freshness_tier(7200), "aging")
        self.assertEqual(work_tool._vrm_freshness_tier(7201), "stale")


def _pv_point(hours_from_epoch, watts):
    """A (timestamp_ms, watts) point at an exact UTC hour boundary, for
    building synthetic day-shaped test series without real epoch math."""
    return (hours_from_epoch * 3600 * 1000, watts)


class SolarShadingDetection(unittest.TestCase):
    def test_no_dip_on_a_normal_rise_then_fall_day(self):
        # A clean bell-shaped day: rises to a midday peak, falls back to
        # zero. Ceiling built from an identical "yesterday."
        watts_by_hour = {6: 5, 7: 80, 8: 185, 9: 366, 10: 431, 11: 466,
                         12: 465, 13: 199, 14: 163, 15: 57, 16: 37, 17: 11}
        ceiling_by_hour = dict(watts_by_hour)
        points = [_pv_point(24 + h, w) for h, w in watts_by_hour.items()]
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        self.assertEqual(run, [])

    def test_dip_during_morning_ramp_is_detected(self):
        # Same healthy ceiling as above, but today's morning hours (8-9)
        # read far below what this same trailer normally produces then —
        # the literal "dips when it should be increasing" pattern.
        ceiling_by_hour = {6: 5, 7: 80, 8: 185, 9: 366, 10: 431, 11: 466,
                           12: 465, 13: 199, 14: 163, 15: 57, 16: 37, 17: 11}
        today = {6: 5, 7: 80, 8: 20, 9: 40, 10: 431, 11: 466,
                 12: 465, 13: 199, 14: 163, 15: 57, 16: 37, 17: 11}
        points = [_pv_point(24 + h, w) for h, w in today.items()]
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        # SHADED_V2: hour 10 reads exactly at its own ceiling (431W, ratio
        # 1.0 — not remotely a dip), but earns one grace point as the
        # reading right after the two real dips (8, 9) and gets folded
        # into the same run; hour 11 (also not a dip) then correctly ends
        # it, since the grace point is spent.
        self.assertEqual(len(run), 3)
        self.assertEqual({8, 9, 10}, {t // 3600000 % 24 for t, _, _ in run})

    def test_real_shaded_ticket_data_is_detected(self):
        # RD3421/MU8064, ERP issue_subtype "shaded" (ISS-2026-10642, opened
        # 2026-08-26) — actual VRM PVP readings from that day (UTC) against
        # this same trailer's ceiling from its own later, unshaded days.
        # This is the regression fixture for the whole feature: it must
        # keep flagging the exact data that motivated building it.
        ceiling_by_hour = {
            12: 4, 13: 86, 14: 186, 15: 373, 16: 457, 17: 466,
            18: 466, 19: 465, 20: 464, 21: 260, 22: 163, 23: 129,
        }
        shaded_day = {
            13: 5, 14: 26, 15: 109, 16: 169, 17: 198, 18: 216,
            19: 221, 20: 202, 21: 84, 22: 36, 23: 26,
        }
        points = [_pv_point(24 + h, w) for h, w in shaded_day.items()]
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        self.assertGreaterEqual(len(run), work_tool._SHADE_MIN_CONSECUTIVE_POINTS)
        # 13h (86W) and 23h (129W) are both below the minimum-productive
        # cutoff (150W — raised from the original max-based 100W once the
        # baseline switched to a median; see _vrm_pv_typical_by_hour), so
        # both are excluded regardless of ratio. That leaves two separate
        # qualifying dip pairs — 14-15h and 21-22h — each of which now (per
        # SHADED_V2's flicker tolerance) earns one more hour on its tail:
        # 16h folds into the first run (17h then correctly ends it), 23h
        # folds into the second. The two runs tie at 3 points apiece, and
        # the function deterministically keeps the first one found.
        dip_hours = {t // 3600000 % 24 for t, _, _ in run}
        self.assertEqual(dip_hours, {14, 15, 16})

    def test_typical_by_hour_is_not_fooled_by_one_outlier_day(self):
        # The false-positive this session found live: a max-based ceiling
        # at a twilight hour was set by a single outlier day (one day
        # happened to have light slightly earlier than the other 20),
        # making every normal day look "way below ceiling" by comparison —
        # a fleet-wide ~58% false-shaded rate at dawn/dusk hours (live
        # example: MU1002's hour-0 UTC ceiling was a 117W max built from one
        # outlier reading, while the other 20 days in the same 21-day
        # window never broke 100W in that hour). Reconstructed here as 20
        # ordinary low readings plus one high outlier, all in UTC hour 0.
        hour0_readings = [2, 3, 4, 5, 6, 8, 9, 10, 12, 15,
                           18, 20, 25, 30, 40, 55, 63, 70, 80, 95, 117]
        points = [_pv_point(0, w) for w in hour0_readings]
        typical_by_hour = work_tool._vrm_pv_typical_by_hour(points, hour_tolerance=0)
        # The median sits with the other 20 ordinary readings, nowhere near
        # the single 117W outlier.
        self.assertEqual(typical_by_hour[0], 18)
        self.assertLess(typical_by_hour[0], 117 * work_tool._SHADE_DEFICIT_RATIO * 2)

        # A perfectly normal ~18W reading at this hour must NOT be flagged
        # as a dip against its own typical value — it's ceiling>=150W that
        # would have to hold for this hour to be judged at all, and a
        # median this low correctly keeps the hour out of judgment.
        normal_reading = [_pv_point(24, 18)]
        run = work_tool._find_shading_dip_run(normal_reading, typical_by_hour)
        self.assertEqual(run, [])

    def test_single_flicker_point_does_not_split_a_shading_run(self):
        # SHADED_V2: a lone recovery reading in the middle of an otherwise
        # continuous dip (moving shade — cloud edge, branch in wind) is
        # tolerated and folds into the SAME run rather than splitting it
        # into two separate, individually-too-short runs.
        ceiling_by_hour = {10: 400, 11: 400, 12: 400, 13: 400}
        points = [
            _pv_point(24 + 10, 40),   # dip
            _pv_point(24 + 11, 380),  # flicker recovery — tolerated
            _pv_point(24 + 12, 40),   # dip
        ]
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        self.assertEqual(len(run), 3)
        self.assertEqual({10, 11, 12}, {t // 3600000 % 24 for t, _, _ in run})

    def test_two_consecutive_recoveries_still_end_the_run(self):
        # The tolerance is bounded to one point — real, sustained recovery
        # (shade has actually passed) still ends the run rather than
        # letting it drift forward indefinitely.
        ceiling_by_hour = {10: 400, 11: 400, 12: 400, 13: 400, 14: 400}
        points = [
            _pv_point(24 + 10, 40),   # dip
            _pv_point(24 + 11, 380),  # tolerated flicker
            _pv_point(24 + 12, 390),  # second consecutive non-dip — ends it
            _pv_point(24 + 13, 40),   # a new dip, but alone (only 1 point)
        ]
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        self.assertEqual(len(run), 2)
        self.assertEqual({10, 11}, {t // 3600000 % 24 for t, _, _ in run})

    def test_low_ceiling_hours_are_never_flagged(self):
        # A near-zero ceiling (dawn/dusk/night) makes any ratio meaningless
        # noise — must not flag regardless of how low the actual reading is.
        ceiling_by_hour = {2: 10, 3: 0}
        points = [_pv_point(24 + 2, 0), _pv_point(24 + 3, 0)]
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        self.assertEqual(run, [])

    def test_single_sample_dip_is_not_enough(self):
        ceiling_by_hour = {10: 400}
        points = [_pv_point(24 + 10, 20)]  # one point, 5% of ceiling
        run = work_tool._find_shading_dip_run(points, ceiling_by_hour)
        # A single qualifying point IS returned by the pure run-finder (it
        # doesn't know about the length gate) — the length gate lives in
        # detect_solar_shading, which is what actually decides "found."
        # Assert the length here so that gate's own threshold stays honest.
        self.assertEqual(len(run), 1)
        self.assertLess(len(run), work_tool._SHADE_MIN_CONSECUTIVE_POINTS)


class DeadPanelSeriesWiring(unittest.TestCase):
    def test_four_panel_unit_counts_shortfall_in_series_pair_units(self):
        # 4-panel units are wired as two series pairs (2S2P) — one dead
        # panel drags its whole pair down (~600W lost), not just its own
        # ~300W. A single dead panel here must read as "1 pair down"
        # (1 physically dead panel), never "2 panels missing".
        now = time.time()
        historical = [
            (int((now - days_ago * 86400) * 1000), 1180)
            for days_ago in (45, 40, 35)  # 3 distinct days at the true peak
        ]
        # 5 distinct days inside the trailing 7-day window, all short — the
        # DEAD_PANEL_V2 persistence guard requires the shortfall to hold
        # on nearly every day, not just the single best-of-window reading.
        recent = [
            (int((now - days_ago * 86400) * 1000), watts)
            for days_ago, watts in ((1, 560), (2, 600), (3, 540), (4, 580), (5, 570))
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", history_days=60, recent_days=14,
            )
        self.assertTrue(found)
        self.assertEqual(info["inferred_panels"], 4)
        self.assertTrue(info["wired_in_series_pairs"])
        self.assertEqual(info["missing_panels"], 1)
        self.assertIn("1 physically dead panel", detail)
        self.assertNotIn("2 physically dead panel", detail)

    def test_two_panel_unit_still_counts_shortfall_per_panel(self):
        # 2-panel units aren't known to have the series-pair complication —
        # a single missing panel there should still read as 1 panel, using
        # plain per-panel accounting (the pre-existing behavior).
        now = time.time()
        historical = [
            (int((now - days_ago * 86400) * 1000), 590)
            for days_ago in (45, 40, 35)
        ]
        recent = [
            (int((now - days_ago * 86400) * 1000), watts)
            for days_ago, watts in ((1, 260), (2, 280), (3, 240), (4, 270), (5, 250))
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", history_days=60, recent_days=14,
            )
        self.assertTrue(found)
        self.assertEqual(info["inferred_panels"], 2)
        self.assertFalse(info["wired_in_series_pairs"])
        self.assertEqual(info["missing_panels"], 1)


class DeadPanelV2Guards(unittest.TestCase):
    def test_historical_peak_seen_on_too_few_days_is_insufficient_data(self):
        # Guard 1: a hard gate — only 2 distinct days ever reached the
        # peak, below _DEAD_PANEL_MIN_HISTORICAL_PEAK_DAYS (3), so there's
        # nothing trustworthy to compare a shortfall against.
        now = time.time()
        historical = [
            (int((now - d * 86400) * 1000), 1180) for d in (45, 40)
        ]
        recent = [
            (int((now - d * 86400) * 1000), w)
            for d, w in ((1, 560), (2, 600), (3, 540), (4, 580), (5, 570))
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel("site123", "tok")
        self.assertIsNone(found)
        self.assertIn("day(s)", detail)

    def test_historical_peak_too_close_to_recent_window_is_insufficient_separation(self):
        # Guard 2: the historical peak's last day and the recent window's
        # start need real daylight between them (>= 5 days) — here the
        # peak was seen just 2 days before the recent window starts.
        now = time.time()
        historical = [
            (int((now - d * 86400) * 1000), 1180) for d in (16, 15, 14)
        ]
        recent = [
            (int((now - d * 86400) * 1000), w)
            for d, w in ((1, 560), (2, 600), (3, 540), (4, 580), (5, 570))
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", recent_days=14,
            )
        self.assertIsNone(found)
        self.assertIn("separation", detail)

    def test_single_day_recovery_does_not_override_persistent_shortfall(self):
        # Guard 3: a lone glitchy high reading on ONE day of the trailing
        # week shouldn't get to clear an otherwise-persistent shortfall —
        # recent_peak is the SECOND-highest trailing day, not the single
        # best one, so this one spike (1000W, still short of the 1180W
        # historical peak) is correctly outranked by nothing and ignored.
        now = time.time()
        historical = [
            (int((now - d * 86400) * 1000), 1180) for d in (45, 40, 35)
        ]
        recent = [
            (int((now - d * 86400) * 1000), w)
            for d, w in (
                (1, 560), (2, 600), (3, 540), (4, 580), (5, 570), (6, 590), (7, 1000),
            )
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", recent_days=14,
            )
        self.assertTrue(found)
        self.assertEqual(info["recent_peak_watts"], 600)

    def test_recovery_on_more_than_one_trailing_day_defeats_the_shortfall(self):
        # Contrast with the above: TWO days recovering near full capacity
        # is real, repeated evidence — the second-highest trailing peak is
        # now also high, so the shortfall genuinely doesn't hold.
        now = time.time()
        historical = [
            (int((now - d * 86400) * 1000), 1180) for d in (45, 40, 35)
        ]
        recent = [
            (int((now - d * 86400) * 1000), w)
            for d, w in (
                (1, 560), (2, 600), (3, 540), (4, 580), (5, 570), (6, 1000), (7, 1000),
            )
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", recent_days=14,
            )
        self.assertFalse(found)
        self.assertIn("within normal range", detail)

    def test_hour_specific_loss_routes_to_shading_not_dead_panel(self):
        # Guard 4 / new signal: a real bell-shaped day (low shoulders, a
        # tall midday peak) where only the PEAK hour collapses while
        # every other hour stays near its own typical. The naive
        # best-day-vs-best-day shortfall still looks big enough to call
        # "dead panel" (the day's peak crashed), but per-hour comparison
        # shows just one hour is actually depressed — angle-dependent,
        # i.e. shading, not a hardware fault that caps output all day.
        now = time.time()
        base_day = int(now // 86400) * 86400
        historical_by_hour = {
            12: 100, 13: 250, 14: 460, 15: 480, 16: 900, 17: 490, 18: 470, 19: 250, 20: 100,
        }
        historical = []
        for d in (45, 40, 35):
            day_start = base_day - d * 86400
            for hour, watts in historical_by_hour.items():
                historical.append((int((day_start + hour * 3600) * 1000), watts))
        recent = []
        for d in (1, 2, 3, 4, 5):
            day_start = base_day - d * 86400
            for hour, watts in historical_by_hour.items():
                # Every hour holds ~95% of typical except the midday peak,
                # which craters to ~30% — the day's own best reading drops
                # hard even though only one hour is actually affected.
                ratio = 0.30 if hour == 16 else 0.95
                recent.append((int((day_start + hour * 3600) * 1000), watts * ratio))
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", recent_days=14, hour_tolerance=0,
            )
        self.assertFalse(found)
        self.assertIn("shading", detail)
        self.assertGreaterEqual(info["hour_ratio_stdev"], 0.10)

    def test_proportional_loss_across_hours_confirms_hardware(self):
        # The real case this signal was built from (RD3439/MU8024,
        # 2026-09-13): recent output held ~68% of typical across every
        # productive hour, +/- ~3pp — flat enough to read as hardware,
        # not shading. Reconstructed at a smaller scale with the same
        # ~68% +/- ~3pp shape across 5 real hours.
        now = time.time()
        base_day = int(now // 86400) * 86400
        historical_by_hour = {14: 460, 15: 480, 16: 500, 17: 490, 18: 470}
        ratio_by_hour = {14: 0.65, 15: 0.70, 16: 0.68, 17: 0.71, 18: 0.66}
        historical = []
        for d in (45, 40, 35):
            day_start = base_day - d * 86400
            for hour, watts in historical_by_hour.items():
                historical.append((int((day_start + hour * 3600) * 1000), watts))
        recent = []
        for d in (1, 2, 3, 4, 5):
            day_start = base_day - d * 86400
            for hour, watts in historical_by_hour.items():
                recent.append((int((day_start + hour * 3600) * 1000), watts * ratio_by_hour[hour]))
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            return_value=historical + recent,
        ):
            found, detail, confidence, info = work_tool.detect_dead_panel(
                "site123", "tok", recent_days=14, hour_tolerance=0,
            )
        self.assertTrue(found)
        self.assertLess(info["hour_ratio_stdev"], 0.10)
        self.assertIn("proportional", detail)


class ShadedV2PersistentExclusion(unittest.TestCase):
    # SHADED_V2: detect_solar_shading declines to call a chronically-low
    # hour "shaded" when the SAME hour reads low across most of its own
    # 21-day baseline too — that's PERSISTENT_OBSTRUCTION_V1's territory,
    # not a new transient dip.
    def _fake_history(self, ceiling_points, recent_points):
        def fake(site_id, victron_token, days, end=None):
            return ceiling_points if days >= 21 else ceiling_points + recent_points
        return fake

    def test_hour_persistently_below_its_own_ceiling_is_excluded(self):
        now = time.time()
        base_day = int(now // 86400) * 86400
        ceiling = []
        for d in range(1, 22):
            day_start = base_day - d * 86400
            # hour15 reads a chronically-low 150W on 17/21 days and only
            # clears to 460W (its real capability) on the other 4 —
            # median stays a productive 150W, but the hour is obstructed
            # on 17/21 (81%) of its own history.
            hour15 = 150 if d % 5 else 460
            for hour, watts in ((14, 460), (15, hour15), (16, 460)):
                ceiling.append((int((day_start + hour * 3600) * 1000), watts))
        recent = [
            (int((base_day + 14 * 3600) * 1000), 450),
            (int((base_day + 15 * 3600) * 1000), 30),  # a fresh, deeper dip today
            (int((base_day + 16 * 3600) * 1000), 460),
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            side_effect=self._fake_history(ceiling, recent),
        ):
            found, detail, confidence, window = work_tool.detect_solar_shading(
                "site1", "tok", ceiling_days=21, recent_hours=30, hour_tolerance=0,
            )
        self.assertFalse(found)
        self.assertIn("predates", detail)

    def test_genuinely_new_dip_is_not_excluded(self):
        # Contrast case: the SAME hour is consistently near its own
        # ceiling across the whole baseline — nothing persistent about
        # it — so a real recent dip is still reported normally.
        now = time.time()
        base_day = int(now // 86400) * 86400
        ceiling = []
        for d in range(1, 22):
            day_start = base_day - d * 86400
            for hour, watts in ((14, 460), (15, 460), (16, 460)):
                ceiling.append((int((day_start + hour * 3600) * 1000), watts))
        recent = [
            (int((base_day + 14 * 3600) * 1000), 450),
            (int((base_day + 15 * 3600) * 1000), 30),
            (int((base_day + 16 * 3600) * 1000), 460),
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            side_effect=self._fake_history(ceiling, recent),
        ):
            found, detail, confidence, window = work_tool.detect_solar_shading(
                "site1", "tok", ceiling_days=21, recent_hours=30, hour_tolerance=0,
            )
        self.assertTrue(found)


class ShadedV2AngleDependence(unittest.TestCase):
    # SHADED_V2: neighboring hours holding near-normal while the worst hour
    # craters is angle-dependent (shading); neighbors ALSO running low
    # softens confidence toward "check for hardware instead."
    def _fake_history(self, ceiling_points, recent_points):
        def fake(site_id, victron_token, days, end=None):
            return ceiling_points if days >= 21 else ceiling_points + recent_points
        return fake

    def _flat_ceiling(self, hours_watts):
        ceiling = []
        now = time.time()
        base_day = int(now // 86400) * 86400
        for d in range(1, 22):
            day_start = base_day - d * 86400
            for hour, watts in hours_watts.items():
                ceiling.append((int((day_start + hour * 3600) * 1000), watts))
        return ceiling, base_day

    def test_normal_neighbors_boost_confidence_as_angle_dependent(self):
        ceiling, base_day = self._flat_ceiling({14: 460, 15: 460, 16: 460})
        recent = [
            (int((base_day + 14 * 3600) * 1000), 440),  # neighbor near-normal
            (int((base_day + 15 * 3600) * 1000), 30),   # the dip
            (int((base_day + 16 * 3600) * 1000), 450),  # neighbor near-normal
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            side_effect=self._fake_history(ceiling, recent),
        ):
            found, detail, confidence, window = work_tool.detect_solar_shading(
                "site1", "tok", ceiling_days=21, recent_hours=30, hour_tolerance=0,
            )
        self.assertTrue(found)
        self.assertIn("angle-dependent", detail)

    def test_depressed_neighbors_soften_confidence_toward_hardware(self):
        ceiling, base_day = self._flat_ceiling({14: 460, 15: 460, 16: 460})
        recent = [
            (int((base_day + 14 * 3600) * 1000), 90),   # neighbor also low
            (int((base_day + 15 * 3600) * 1000), 30),   # the dip
            (int((base_day + 16 * 3600) * 1000), 100),  # neighbor also low
        ]
        with mock.patch.object(
            work_tool.weather, "_vrm_pv_history_points",
            side_effect=self._fake_history(ceiling, recent),
        ):
            found, detail, confidence, window = work_tool.detect_solar_shading(
                "site1", "tok", ceiling_days=21, recent_hours=30, hour_tolerance=0,
            )
        self.assertTrue(found)
        self.assertIn("hardware-wide cause", detail)


class PersistentObstructionV1(unittest.TestCase):
    # PERSISTENT_OBSTRUCTION_V1: an hour that reads low against its own
    # immediate neighbors on the SAME day, across most of the window —
    # the case detect_solar_shading structurally can't see (its baseline
    # is the obstructed hour's own history, already suppressed by the
    # obstruction itself).
    def test_hour_persistently_low_against_neighbors_is_detected(self):
        now = time.time()
        base_day = int(now // 86400) * 86400
        points = []
        for d in range(1, 22):
            day_start = base_day - d * 86400
            # 18 of 21 days: hour14 is obstructed (100W) while its
            # neighbors (13, 15) hold a normal 400W. 3 days: hour14
            # recovers to 380W (e.g. an angle where the obstruction
            # doesn't fall — real obstructions aren't always 100%).
            hour14 = 100 if d <= 18 else 380
            for hour, watts in ((13, 400), (14, hour14), (15, 400)):
                points.append((int((day_start + hour * 3600) * 1000), watts))
        with mock.patch.object(work_tool.weather, "_vrm_pv_history_points", return_value=points):
            found, detail, confidence, info = work_tool.detect_persistent_obstruction(
                "site1", "tok", days=21, hour_tolerance=0,
            )
        self.assertTrue(found)
        self.assertEqual(info["hour_utc"], 14)
        self.assertEqual(info["obstructed_days"], 18)
        self.assertIn("14:00", detail)

    def test_normal_bell_curve_day_is_not_flagged(self):
        # No obstruction anywhere — every hour holds close to its
        # neighbors every day. Must not manufacture a finding.
        now = time.time()
        base_day = int(now // 86400) * 86400
        points = []
        for d in range(1, 22):
            day_start = base_day - d * 86400
            for hour, watts in ((13, 380), (14, 400), (15, 390)):
                points.append((int((day_start + hour * 3600) * 1000), watts))
        with mock.patch.object(work_tool.weather, "_vrm_pv_history_points", return_value=points):
            found, detail, confidence, info = work_tool.detect_persistent_obstruction(
                "site1", "tok", days=21, hour_tolerance=0,
            )
        self.assertFalse(found)

    def test_globally_cloudy_days_are_not_mistaken_for_obstruction(self):
        # Some days are simply dimmer overall (cloud cover) — hour14 AND
        # its neighbors all drop together, proportionally. Because the
        # check compares hour14 to its neighbors on the SAME day (not to
        # a fixed number), a day-wide brightness swing never reads as an
        # hour-specific obstruction, cloudy or clear.
        now = time.time()
        base_day = int(now // 86400) * 86400
        points = []
        for d in range(1, 22):
            day_start = base_day - d * 86400
            watts = 200 if d <= 18 else 400
            for hour in (13, 14, 15):
                points.append((int((day_start + hour * 3600) * 1000), watts))
        with mock.patch.object(work_tool.weather, "_vrm_pv_history_points", return_value=points):
            found, detail, confidence, info = work_tool.detect_persistent_obstruction(
                "site1", "tok", days=21, hour_tolerance=0,
            )
        self.assertFalse(found)


class VerifyShadingDipNow(unittest.TestCase):
    # The shading-snapshot scheduler's pre-capture re-check (see
    # shading_snapshots.py): is the dip this task was scheduled around
    # actually happening again right now, before spending a camera fetch.
    def _patched(self, ceiling_points, recent_points):
        return (
            mock.patch.object(
                work_tool.weather, "_vrm_credentials", return_value=("user1", "tok", None)
            ),
            mock.patch.object(
                work_tool.weather, "_resolve_vrm_site",
                return_value=("site1", "MU8024", 60, "America/Phoenix", None),
            ),
            mock.patch.object(
                work_tool.weather, "_vrm_pv_history_points",
                side_effect=lambda site_id, token, days=None, **kw: (
                    ceiling_points if (days or kw.get("days") or 0) >= 21 else recent_points
                ),
            ),
        )

    def test_confirms_a_real_dip(self):
        now = time.time()
        base_day = int(now // 86400) * 86400
        ceiling = [
            (int((base_day - d * 86400 + 15 * 3600) * 1000), 460) for d in range(1, 22)
        ]
        recent = [(int((base_day + 15 * 3600) * 1000), 30)]
        p1, p2, p3 = self._patched(ceiling, recent)
        with p1, p2, p3:
            is_dip, detail, current_watts, typical_watts = work_tool.verify_shading_dip_now(
                "MU8024", "", 15,
            )
        self.assertTrue(is_dip)
        self.assertEqual(current_watts, 30)
        self.assertEqual(typical_watts, 460)

    def test_does_not_confirm_when_reading_is_normal(self):
        now = time.time()
        base_day = int(now // 86400) * 86400
        ceiling = [
            (int((base_day - d * 86400 + 15 * 3600) * 1000), 460) for d in range(1, 22)
        ]
        recent = [(int((base_day + 15 * 3600) * 1000), 440)]
        p1, p2, p3 = self._patched(ceiling, recent)
        with p1, p2, p3:
            is_dip, detail, current_watts, typical_watts = work_tool.verify_shading_dip_now(
                "MU8024", "", 15,
            )
        self.assertFalse(is_dip)

    def test_unproductive_hour_returns_none_not_a_guess(self):
        now = time.time()
        base_day = int(now // 86400) * 86400
        ceiling = [
            (int((base_day - d * 86400 + 3 * 3600) * 1000), 5) for d in range(1, 22)
        ]
        p1, p2, p3 = self._patched(ceiling, [])
        with p1, p2, p3:
            is_dip, detail, current_watts, typical_watts = work_tool.verify_shading_dip_now(
                "MU8024", "", 3,
            )
        self.assertIsNone(is_dip)


class SocTrendCrossCheck(unittest.TestCase):
    # UNPLUGGED_V2: SOC now vs. SOC _SOC_TREND_LOOKBACK_HOURS ago,
    # distinguishing "charging is real and working" from "battery not
    # accepting charge despite real output" for the Fault-with-output case.
    def test_rising_soc_confirms_real_charge(self):
        label, delta = work_tool._soc_trend_verdict(soc_now=62, soc_earlier=54)
        self.assertEqual(label, "rising")
        self.assertEqual(delta, 8)

    def test_falling_soc_flags_not_accepting_charge(self):
        label, delta = work_tool._soc_trend_verdict(soc_now=50, soc_earlier=55)
        self.assertEqual(label, "falling")
        self.assertEqual(delta, -5)

    def test_flat_soc_is_inconclusive_not_a_verdict(self):
        label, delta = work_tool._soc_trend_verdict(soc_now=80, soc_earlier=79.5)
        self.assertEqual(label, "flat")

    def test_missing_reading_returns_none_not_a_guess(self):
        label, delta = work_tool._soc_trend_verdict(soc_now=None, soc_earlier=70)
        self.assertIsNone(label)
        self.assertIsNone(delta)


if __name__ == "__main__":
    unittest.main()
