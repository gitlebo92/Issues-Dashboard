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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402


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
        self.assertEqual(len(run), 2)
        self.assertEqual({8, 9}, {t // 3600000 % 24 for t, _, _ in run})

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
        # 13h's ceiling (86W) is below the minimum-productive cutoff, so
        # that hour is excluded regardless of ratio; 21-23h all clear the
        # cutoff and all fall under the deficit ratio, making that the
        # longest (and correct) run to surface.
        dip_hours = {t // 3600000 % 24 for t, _, _ in run}
        self.assertEqual(dip_hours, {21, 22, 23})

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


if __name__ == "__main__":
    unittest.main()
