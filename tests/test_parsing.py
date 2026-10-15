"""
Pure-function regression tests for work_tool.

These cover the parsing and classification helpers that quietly break when
ERP changes a subject format, when a netsheet row comes back short, or when
a new smartctl version reshuffles its output. Nothing here touches the
network, SSH, ERP or the net sheet, so it is safe to run anywhere:

    python -m unittest discover -s tests -v

Importing work_tool loads .env and tries to read net_sheet.csv; both are
optional and fail soft, so these pass on a clean checkout.
"""

import csv
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402


class CameraTargetsFromSubject(unittest.TestCase):
    def test_specific_camera_numbers_and_short_forms(self):
        self.assertEqual(work_tool._camera_targets_from_subject("Camera 2 down"), ["camera2"])
        self.assertEqual(work_tool._camera_targets_from_subject("C3 not working"), ["camera3"])
        self.assertEqual(work_tool._camera_targets_from_subject("Fisheye not working"), ["fisheye"])

    def test_multiple_specific_cameras(self):
        self.assertEqual(
            work_tool._camera_targets_from_subject("Camera 1 and Camera 4 down"),
            ["camera1", "camera4"],
        )

    def test_generic_camera_outage_has_no_specific_target(self):
        # Caught live: ISS-2026-11561's real subject named no specific
        # camera, so this returned [] and the ticket silently fell through
        # to the generic connectivity check instead of Camera Outage — see
        # _is_generic_camera_outage_subject, which is what now catches
        # exactly this case.
        self.assertEqual(
            work_tool._camera_targets_from_subject(
                "PHX-RD3343(MU5044)-Camera Outage-09/14/26-Facebook-OES Mesa"
            ),
            [],
        )


class GenericCameraOutageSubject(unittest.TestCase):
    def test_real_ticket_subject_matches(self):
        self.assertTrue(work_tool._is_generic_camera_outage_subject(
            "PHX-RD3343(MU5044)-Camera Outage-09/14/26-Facebook-OES Mesa"
        ))

    def test_case_insensitive(self):
        self.assertTrue(work_tool._is_generic_camera_outage_subject("camera outage"))

    def test_does_not_match_a_specific_camera_number(self):
        # Already caught by _camera_targets_from_subject on its own — no
        # fallback needed, so this deliberately isn't required to match.
        self.assertFalse(work_tool._is_generic_camera_outage_subject("Camera 2 Outage"))

    def test_unrelated_subject_does_not_match(self):
        self.assertFalse(work_tool._is_generic_camera_outage_subject("Router Down"))

    def test_empty_subject_does_not_match(self):
        self.assertFalse(work_tool._is_generic_camera_outage_subject(""))
        self.assertFalse(work_tool._is_generic_camera_outage_subject(None))

    def test_no_date_field_still_generic(self):
        # Live regression, RD3067(MU9034), 2026-09-22: this subject has no
        # date segment at all — "Camera Outage" goes straight to
        # Customer-Site. The old "must be a bare date" rule treated that as
        # a named camera, so camera_targets stayed empty and the ticket
        # fell through to the generic connectivity check, landing in Up
        # Steady (false_positives) instead of Camera outage.
        self.assertTrue(work_tool._is_generic_camera_outage_subject(
            "LAX - RD3067(MU9034) - Camera Outage - Simplehuman-Simplehuman - Carson"
        ))

    def test_named_device_attached_is_not_generic(self):
        # Live regression, FD1040, 2026-09-16: "Camera Outage
        # MzdUsedBldg-C02-Rear-W down" names one specific camera by its
        # own site-local label, just not in the c1-4/fisheye pattern
        # _camera_targets_from_subject recognizes. Treating this as
        # "generic" (no camera named) expanded one real ticket into 5
        # near-duplicate rows, one per camera target, instead of the one
        # it actually was.
        self.assertFalse(work_tool._is_generic_camera_outage_subject(
            "HOU - FD1040 - Camera Outage MzdUsedBldg-C02-Rear-W down - "
            "Coast Buick GMC Mazda-GMC Cadillac 10133"
        ))


class IsCameraViewTicket(unittest.TestCase):
    def test_dirty_camera_lens_with_no_erp_subtype(self):
        # Caught live: "OAK-RD3534(MU4058)-Dirty Camera Lens-09/21/26-
        # Cobalt Builders-Prineville Apartments" came through with no
        # issue_subtype set (UNDIAGNOSED), so the CAMERA_VIEW_ISSUE_SUBTYPES
        # ("dirty cameras") check never fired, and the subject-text fallback
        # didn't recognize "Dirty Camera Lens" either — it ran full outage
        # validation instead of routing to Camera View.
        self.assertTrue(work_tool._is_camera_view_ticket(
            "", "",
            "OAK-RD3534(MU4058)-Dirty Camera Lens-09/21/26-Cobalt Builders-"
            "Prineville Apartments",
        ))

    def test_dirty_lens_with_no_erp_subtype(self):
        # Caught live 2026-10-07: UNDIAGNOSED "Dirty Lens" (no "Camera" in
        # it) fell through to connectivity and landed in Offline compute.
        self.assertTrue(work_tool._is_camera_view_ticket(
            "", "",
            "SLC-RD3351(MU9068)-Dirty Lens-10/07/26-S&L Inc-Millcreek Canyon Road Project",
        ))
        self.assertTrue(work_tool._is_camera_view_ticket("", "", "PHX - RD3076 - Blurry Lens C2"))

    def test_blurry_and_dark_subject_fallbacks(self):
        self.assertTrue(work_tool._is_camera_view_ticket("", "", "Blurry Camera on RD3534"))
        self.assertTrue(work_tool._is_camera_view_ticket("", "", "Dark Views - RD3534"))

    def test_known_subtype_still_matches_regardless_of_subject(self):
        self.assertTrue(work_tool._is_camera_view_ticket("", "Dirty Cameras", "Router Down"))

    def test_unrelated_subject_does_not_match(self):
        self.assertFalse(work_tool._is_camera_view_ticket("", "", "Router Down"))


class RegionCodeFromSubject(unittest.TestCase):
    def test_parses_each_supported_region(self):
        for code in ("LAX", "OAK", "HOU", "PHX", "SLC", "DEN"):
            self.assertEqual(
                work_tool.region_code_from_subject(f"{code} - RD3076 - Unit Down"),
                code,
            )

    def test_accepts_hyphen_without_spaces(self):
        self.assertEqual(work_tool.region_code_from_subject("PHX-RD3076 - Down"), "PHX")

    def test_is_case_insensitive(self):
        self.assertEqual(work_tool.region_code_from_subject("phx - rd3076"), "PHX")

    def test_unknown_or_empty_returns_blank(self):
        self.assertEqual(work_tool.region_code_from_subject("ABQ - RD3076"), "")
        self.assertEqual(work_tool.region_code_from_subject(""), "")
        self.assertEqual(work_tool.region_code_from_subject(None), "")

    def test_does_not_match_region_embedded_in_a_word(self):
        self.assertEqual(work_tool.region_code_from_subject("PHXX - RD3076"), "")


class CarrierFromIccid(unittest.TestCase):
    def test_known_prefixes(self):
        self.assertEqual(work_tool.carrier_from_iccid("8914800000123456789"), "Verizon Wireless")
        self.assertEqual(work_tool.carrier_from_iccid("8901240000123456789"), "TMOBILE")
        self.assertEqual(work_tool.carrier_from_iccid("8901030000123456789"), "AT&T")

    def test_strips_separators(self):
        self.assertEqual(work_tool.carrier_from_iccid("8914-8000 0012 3456"), "Verizon Wireless")

    def test_unknown_and_short_values(self):
        self.assertIsNone(work_tool.carrier_from_iccid("8999990000123456789"))
        self.assertIsNone(work_tool.carrier_from_iccid("12345"))
        self.assertIsNone(work_tool.carrier_from_iccid(""))
        self.assertIsNone(work_tool.carrier_from_iccid(None))


class NetsheetRowShape(unittest.TestCase):
    def test_pad_extends_short_rows(self):
        padded = work_tool._pad_netsheet_row(["RD3076", "10.1.1.1"])
        self.assertEqual(len(padded), work_tool.NETSHEET_COL_COUNT)
        self.assertEqual(padded[0], "RD3076")
        self.assertEqual(padded[2], "")

    def test_pad_truncates_long_rows(self):
        padded = work_tool._pad_netsheet_row(["x"] * (work_tool.NETSHEET_COL_COUNT + 5))
        self.assertEqual(len(padded), work_tool.NETSHEET_COL_COUNT)

    def test_pad_stringifies_none(self):
        self.assertEqual(work_tool._pad_netsheet_row(["RD3076", None])[1], "")

    def test_sparse_detects_missing_requested_column(self):
        row = work_tool._pad_netsheet_row(["RD3076"])
        row[11] = "10.1.1.11"
        self.assertFalse(work_tool._netsheet_row_is_sparse(row, needed_indexes=(11,)))
        self.assertTrue(work_tool._netsheet_row_is_sparse(row, needed_indexes=(12,)))

    def test_empty_row_is_sparse(self):
        self.assertTrue(work_tool._netsheet_row_is_sparse([]))
        self.assertTrue(work_tool._netsheet_row_is_sparse(None))


class UnitHelpers(unittest.TestCase):
    def test_unit_number(self):
        self.assertEqual(work_tool.unit_number("RD3076"), 3076)
        self.assertEqual(work_tool.unit_number("MU1001"), 1001)
        self.assertIsNone(work_tool.unit_number("RDABCD"))

    def test_uses_pve_boundary(self):
        self.assertTrue(work_tool.uses_pve("RD3300"))
        self.assertTrue(work_tool.uses_pve("RD3400"))
        self.assertFalse(work_tool.uses_pve("RD3299"))
        self.assertFalse(work_tool.uses_pve("RDABCD"))

    def test_is_fd_unit(self):
        self.assertTrue(work_tool.is_fd_unit("FD1234"))
        self.assertFalse(work_tool.is_fd_unit("RD1234"))

    def test_host_only_strips_scheme_and_port(self):
        self.assertEqual(work_tool._host_only("https://10.1.1.1:8006/x"), "10.1.1.1")
        self.assertEqual(work_tool._host_only("10.1.1.1"), "10.1.1.1")
        self.assertEqual(work_tool._host_only(""), "")


class PatchVersionParsing(unittest.TestCase):
    def test_extracts_package_date_and_time(self):
        raw = "Version: sentracam-watch-20260728-141500.tar.gz installed"
        info = work_tool._parse_patch_version(raw)
        self.assertEqual(info["date"], "20260728")
        self.assertEqual(info["time"], "141500")
        self.assertEqual(info["package"], "sentracam-watch-20260728-141500.tar.gz")

    def test_unparseable_input_yields_blank_date_not_none(self):
        # Documented current behavior: the caller checks `date`, so an
        # unrecognised line comes back as a dict with an empty date rather
        # than None. get_unit_patch_version relies on this.
        info = work_tool._parse_patch_version("no version here")
        self.assertEqual(info["date"], "")
        self.assertEqual(info["raw"], "no version here")
        self.assertEqual(work_tool._parse_patch_version("")["date"], "")


class WeatherIcons(unittest.TestCase):
    def test_clear_and_cloud_codes(self):
        self.assertEqual(work_tool._wmo_icon_class(0), "sun")
        self.assertEqual(work_tool._wmo_icon_class(2), "sun-cloud")
        self.assertEqual(work_tool._wmo_icon_class(3), "cloud")
        self.assertEqual(work_tool._wmo_icon_class(45), "fog")
        self.assertEqual(work_tool._wmo_icon_class(75), "cloud-snow")
        self.assertEqual(work_tool._wmo_icon_class(95), "cloud-lightning")
        self.assertEqual(work_tool._wmo_icon_class(61), "cloud-rain")

    def test_cloud_cover_downgrades_sun(self):
        self.assertEqual(work_tool._wmo_icon_class(0, cloud_cover=60), "sun-cloud")
        self.assertEqual(work_tool._wmo_icon_class(0, cloud_cover=90), "cloud-mostly")

    def test_bad_code_falls_back_to_cloud(self):
        self.assertEqual(work_tool._wmo_icon_class(None), "cloud")
        self.assertEqual(work_tool._wmo_icon_class("nonsense"), "cloud")


SAMPLE_NVME_SMART = """smartctl 7.2 2020-12-30 r5155 [x86_64-linux-6.8.12-4-pve] (local build)

=== START OF INFORMATION SECTION ===
Model Number:                       SAMSUNG MZVL2512HCJQ-00BL7
Serial Number:                      S67ANF0T123456
Firmware Version:                   GXA7601Q

=== START OF SMART DATA SECTION ===
SMART overall-health self-assessment test result: PASSED

SMART/Health Information (NVMe Log 0x02)
Critical Warning:                   0x00
Temperature:                        41 Celsius
Available Spare:                    100%
Available Spare Threshold:          10%
Percentage Used:                    3%
Data Units Written:                 24,551,238 [12.5 TB]
Power Cycles:                       184
Power On Hours:                     15,203
Unsafe Shutdowns:                   37
Media and Data Integrity Errors:    0
Error Information Log Entries:      0
"""


class NvmeSmartParsing(unittest.TestCase):
    def setUp(self):
        self.info = work_tool._parse_nvme_smart(SAMPLE_NVME_SMART)

    def test_reads_identity_fields(self):
        self.assertEqual(self.info["model"], "SAMSUNG MZVL2512HCJQ-00BL7")
        self.assertEqual(self.info["serial"], "S67ANF0T123456")
        self.assertEqual(self.info["overall_health"], "PASSED")

    def test_numeric_fields_are_ints_with_commas_stripped(self):
        self.assertEqual(self.info["temperature_c"], 41)
        self.assertEqual(self.info["percentage_used"], 3)
        self.assertEqual(self.info["available_spare"], 100)
        self.assertEqual(self.info["available_spare_threshold"], 10)
        self.assertEqual(self.info["power_on_hours"], 15203)
        self.assertEqual(self.info["unsafe_shutdowns"], 37)
        self.assertEqual(self.info["media_errors"], 0)

    def test_healthy_drive_verdict(self):
        status, reasons = work_tool._nvme_health_verdict(self.info)
        self.assertEqual(status, "ok")
        self.assertEqual(reasons, [])

    def test_unparseable_output_does_not_raise(self):
        info = work_tool._parse_nvme_smart("totally unrelated text")
        self.assertEqual(info, {})
        status, reasons = work_tool._nvme_health_verdict(info)
        self.assertEqual(status, "ok")
        self.assertEqual(reasons, [])


class NvmeHealthVerdict(unittest.TestCase):
    def test_failed_self_assessment(self):
        status, reasons = work_tool._nvme_health_verdict({"overall_health": "FAILED!"})
        self.assertEqual(status, "fail")
        self.assertTrue(any("overall-health" in r for r in reasons))

    def test_critical_warning_bit_set(self):
        status, _ = work_tool._nvme_health_verdict({"critical_warning": "0x04"})
        self.assertEqual(status, "fail")

    def test_media_errors_fail(self):
        status, _ = work_tool._nvme_health_verdict({"media_errors": 12})
        self.assertEqual(status, "fail")

    def test_spare_at_threshold_fails(self):
        status, _ = work_tool._nvme_health_verdict(
            {"available_spare": 10, "available_spare_threshold": 10}
        )
        self.assertEqual(status, "fail")

    def test_high_wear_warns_but_does_not_fail(self):
        status, reasons = work_tool._nvme_health_verdict({"percentage_used": 92})
        self.assertEqual(status, "warn")
        self.assertTrue(any("endurance" in r for r in reasons))

    def test_hot_drive_warns(self):
        status, _ = work_tool._nvme_health_verdict({"temperature_c": 74})
        self.assertEqual(status, "warn")

    def test_fail_outranks_warn(self):
        status, _ = work_tool._nvme_health_verdict(
            {"media_errors": 1, "percentage_used": 95}
        )
        self.assertEqual(status, "fail")


class NvmeDevicePathGuard(unittest.TestCase):
    def test_rejects_shell_metacharacters_before_connecting(self):
        info, error = work_tool.pve_nvme_health("RD3400", device="/dev/nvme0n1; rm -rf /")
        self.assertIsNone(info)
        self.assertIn("Refusing unexpected device path", error)

    def test_rejects_non_dev_paths(self):
        info, error = work_tool.pve_nvme_health("RD3400", device="/etc/passwd")
        self.assertIsNone(info)
        self.assertIn("Refusing unexpected device path", error)

    def test_missing_unit_is_rejected(self):
        info, error = work_tool.pve_nvme_health("")
        self.assertIsNone(info)
        self.assertEqual(error, "Missing unit")


class NetArrayBootstrap(unittest.TestCase):
    def test_ensure_net_array_never_raises(self):
        # Whether or not net_sheet.csv exists in this checkout, this must
        # return a bool rather than propagating a file error into import.
        self.assertIn(work_tool.ensure_net_array(), (True, False))

    def test_net_row_for_unit_handles_empty_input(self):
        self.assertIsNone(work_tool._net_row_for_unit(""))
        self.assertIsNone(work_tool._net_row_for_unit(None))


class IssuesReportMiscellaneousDiscards(unittest.TestCase):
    # "Site Arm Change" and "Welcome Packet" subjects aren't real outages —
    # they belong in Miscellaneous (discarded_tickets) the same way Suspend/
    # RainDance/Site Note/etc. already do. See validate_issues_report.
    def _run(self, rows):
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8-sig", suffix=".csv", delete=False,
        ) as f:
            path = f.name
            writer = csv.writer(f)
            writer.writerow(["ID", "Subject", "Issue Type", "Issue Subtype", "Status"])
            for row_id, subject in rows:
                writer.writerow([row_id, subject, "", "", "Open"])
        try:
            return work_tool.validate_issues_report(path)
        finally:
            os.remove(path)

    def test_site_arm_change_is_discarded_as_miscellaneous(self):
        result = self._run([("ISS-1", "PHX - RD3076 - Site Arm Change")])
        discarded = result[-1]
        self.assertEqual(len(discarded), 1)
        self.assertEqual(discarded[0]["issue_id"], "ISS-1")
        self.assertIn("Site Arm Change", discarded[0]["reason"])

    def test_welcome_packet_is_discarded_as_miscellaneous(self):
        result = self._run([("ISS-2", "PHX - RD3076 - Welcome Packet")])
        discarded = result[-1]
        self.assertEqual(len(discarded), 1)
        self.assertEqual(discarded[0]["issue_id"], "ISS-2")
        self.assertIn("Welcome Packet", discarded[0]["reason"])

    def test_match_is_case_insensitive(self):
        result = self._run([("ISS-3", "PHX - RD3076 - site arm change request")])
        discarded = result[-1]
        self.assertEqual(len(discarded), 1)
        self.assertEqual(discarded[0]["issue_id"], "ISS-3")

    def test_rd_head_is_loose_is_discarded_as_miscellaneous(self):
        # Reported live: 2 "RD head is loose" tickets sitting in Up Steady
        # instead of Miscellaneous — the old pattern only allowed "RD head
        # loose" or "RD loose," nothing in between "head" and "loose."
        result = self._run([("ISS-4", "PHX - RD3076 - RD head is loose")])
        discarded = result[-1]
        self.assertEqual(len(discarded), 1)
        self.assertEqual(discarded[0]["issue_id"], "ISS-4")
        self.assertIn("loose", discarded[0]["reason"])

    def test_rd_head_loose_without_is_still_discarded(self):
        # The original phrasing this rule was built for — must keep
        # working alongside the "is" variant above.
        result = self._run([("ISS-5", "PHX - RD3076 - RD head loose")])
        discarded = result[-1]
        self.assertEqual(len(discarded), 1)
        self.assertEqual(discarded[0]["issue_id"], "ISS-5")


class SiteSearchFallbacks(unittest.TestCase):
    """
    _find_erp_site_by_subject_fallbacks with ERP's Site search faked by an
    in-memory list. Regression for RD3248(MU9030) (2026-10-05): its Site is
    named by an EA code, and the company in the title is the Site's customer.
    """

    SITES = [
        {"site_id": "66979", "site_name": "EA-240479 - Houston, Tx (Westheimer)", "status": "Inactive",
         "region": "HOU", "customer": "Prodiconn Solutions, Inc"},
        {"site_id": "60001", "site_name": "Fresno Switch Yard", "status": "Active",
         "region": "OAK", "customer": "City of Fresno"},
        {"site_id": "60002", "site_name": "Big Co - Dallas", "status": "Active", "region": "DAL", "customer": "Big Co Holdings"},
        {"site_id": "60003", "site_name": "Big Co - Houston", "status": "Active", "region": "HOU", "customer": "Big Co Holdings"},
    ]

    def _fake_search(self, filters, limit=20):
        field, op, value = filters[0]
        needle = value.strip("%").lower()
        rows = [
            s for s in self.SITES
            if (s.get(field, "").lower() == needle if op == "=" else needle in s.get(field, "").lower())
        ]
        return rows[:limit], None

    def _find(self, subject):
        from unittest import mock
        with mock.patch.object(work_tool._core, "_search_erp_sites", side_effect=self._fake_search):
            return work_tool._core._find_erp_site_by_subject_fallbacks(subject)

    def test_site_code_in_title(self):
        site, _ = self._find("HOU: Deployment Prep - RD3248(MU9030) - 10/5 Prodiconn Solutions, Inc - "
                             "EA-240479 - (Prodiconn Parking Lot)")
        self.assertEqual(site["site_id"], "66979")

    def test_customer_name_in_title(self):
        site, _ = self._find("HOU: Deployment Prep - RD3248(MU9030) - 10/5 Prodiconn Solutions, Inc - "
                             "(Prodiconn Parking Lot)")
        self.assertEqual(site["site_id"], "66979")

    def test_region_breaks_a_customer_tie(self):
        site, _ = self._find("HOU - RD3001(MU1001) - Unit Outage Full - Big Co Holdings")
        self.assertEqual(site["site_id"], "60003")

    def test_lone_generic_word_never_partial_matches(self):
        # "Switch" is a partial of "Fresno Switch Yard" — must not resolve.
        site, error = self._find("OAK - RD9999(MU9999) - Unit Outage Partial - Switch")
        self.assertIsNone(site)
        self.assertIn('site name = "Switch"', error)


class NoSiteMessage(unittest.TestCase):
    def test_refurb_status_reads_as_warehoused(self):
        message = work_tool._no_site_message(
            "SC-RD3565",
            {"component_status": "Refurb - Physical", "warehouse": "DEN - SC"},
        )
        self.assertIn("SC-RD3565 is warehoused in DEN - SC", message)
        self.assertIn("Refurb - Physical", message)

    def test_other_status_keeps_plain_message(self):
        self.assertEqual(
            work_tool._no_site_message("SC-MU9008", {"component_status": "Deployed"}),
            "Component SC-MU9008 has no Site",
        )
        self.assertEqual(
            work_tool._no_site_message("SC-MU9008", None),
            "Component SC-MU9008 has no Site",
        )


class TicketSiteFallsBackToProject(unittest.TestCase):
    """RD3557's RainDance ticket: no Site anywhere but its project's title."""

    TICKET = "SC-RD3557-RainDance-20261014-17"
    PROJECT = "PHX: NOC Deployment - RD3557 - RainDance Farms"

    def setUp(self):
        import work_tool._core as core
        self.core = core
        self._saved = {k: dict(v) for k, v in core._RECENT_PROJECT_SUBJECTS.items()}
        for source in ("noc", "prep"):
            core._remember_project_subjects(source, [])
        core._SITE_ID_CACHE.clear()

    def tearDown(self):
        for source, saved in self._saved.items():
            self.core._RECENT_PROJECT_SUBJECTS[source].clear()
            self.core._RECENT_PROJECT_SUBJECTS[source].update(saved)
        self.core._SITE_ID_CACHE.clear()

    def _resolve(self, by_title):
        def search(subject, prefer_status=None):
            site_id = by_title.get(subject)
            return ({"site_id": site_id}, None) if site_id else (None, "No Site found")
        with mock.patch.object(self.core, "resolve_shield_site_id",
                               return_value=("", "Component SC-RD3557 has no Site")), \
             mock.patch.object(self.core, "find_erp_site_by_project_subject", side_effect=search):
            return self.core.resolve_dashboard_site_id("RD3557", self.TICKET)

    def test_project_title_names_the_site(self):
        self.core._remember_project_subjects("noc", [{"subject": self.PROJECT}])
        self.assertEqual(self._resolve({self.PROJECT: "70001"}), ("70001", None))

    def test_prep_project_counts_too(self):
        self.core._remember_project_subjects("prep", [{"subject": self.PROJECT}])
        self.assertEqual(self._resolve({self.PROJECT: "70001"}), ("70001", None))

    def test_other_units_projects_are_ignored(self):
        other = "PHX: NOC Deployment - RD3558 - Elsewhere"
        self.core._remember_project_subjects("noc", [{"subject": other}])
        site_id, error = self._resolve({other: "70002"})
        self.assertEqual(site_id, "")
        self.assertIn("no open NOC/Prep project names RD3557", error)

    def test_a_new_pull_replaces_the_old_one(self):
        self.core._remember_project_subjects("noc", [{"subject": self.PROJECT}])
        self.core._remember_project_subjects("noc", [])
        self.assertEqual(self.core._recent_project_subjects_for_unit("rd3557"), [])


class FuzedUnit(unittest.TestCase):
    """Fuzed = MU with no RD/FD head paired to it (e.g. MU1034): no fisheye."""

    def setUp(self):
        import work_tool._core as core
        self.core = core
        core._MU_HAS_HEAD_CACHE.clear()

    def _heads(self, by_mu, error=None):
        return mock.patch.object(self.core, "_erp_heads_for_mu_trailers", return_value=(by_mu, error))

    def test_mu_without_head_is_fuzed_and_skips_fisheye(self):
        with self._heads({}):
            self.assertTrue(work_tool.is_fuzed_unit("MU1034"))
            self.assertEqual(
                work_tool.open_camera_targets_for_unit("MU1034"),
                {"camera1", "camera2", "camera3", "camera4"},
            )

    def test_mu_paired_with_rd_is_not_fuzed(self):
        with self._heads({"MU6007": ["RD3231"]}):
            self.assertFalse(work_tool.is_fuzed_unit("MU6007"))

    def test_high_numbered_fuzed_mu_is_not_caught_by_3300_rule(self):
        with self._heads({}):
            self.assertNotIn("fisheye", work_tool.open_camera_targets_for_unit("MU8067"))

    def test_heads_are_never_fuzed(self):
        with self._heads({}) as lookup:
            self.assertFalse(work_tool.is_fuzed_unit("RD3076"))
            lookup.assert_not_called()

    def test_erp_failure_falls_back_to_blank_fisheye_column(self):
        blank = ["MU1034", "r", "s", "n", "", "", "c1", "c2", "c3", "c4", "", "", ""]
        with self._heads({}, error="ERP down"),                 mock.patch.object(self.core, "_net_row_for_unit", return_value=blank):
            self.assertTrue(work_tool.is_fuzed_unit("MU1034"))
        fisheye = list(blank)
        fisheye[5] = "10.0.0.5"
        with self._heads({}, error="ERP down"),                 mock.patch.object(self.core, "_net_row_for_unit", return_value=fisheye):
            self.assertFalse(work_tool.is_fuzed_unit("MU1035"))


class CameraVendorProbe(unittest.TestCase):
    """A Fuzed MU is only probably Hikvision — MU1041's cameras are Dahua."""

    def setUp(self):
        import work_tool._core as core
        self.core = core

    def test_login_pages(self):
        hik = '<script>window.location.href = "./doc/page/login.asp?_" + 1;</script>'
        dahua = '<script src="jsBase/lib/jquery.js?version=@WebVersion@"></script>'
        self.assertEqual(work_tool.camera_vendor_from_login_page(hik), "hikvision")
        self.assertEqual(work_tool.camera_vendor_from_login_page("", "/doc/page/login.asp"), "hikvision")
        self.assertEqual(work_tool.camera_vendor_from_login_page(dahua), "dahua")
        self.assertIsNone(work_tool.camera_vendor_from_login_page("<html>404</html>"))

    def test_probe_overrides_mu_rule(self):
        cameras = [{"target": "camera1", "host": "10.0.0.2", "port": 80}]
        with mock.patch.object(self.core, "_probe_camera_vendor", return_value="dahua"):
            self.assertFalse(work_tool.is_hikvision_unit("MU1041", cameras))
            self.assertEqual(work_tool._camera_vendor("MU1041", cameras[0], cameras), "dahua")
        with mock.patch.object(self.core, "_probe_camera_vendor", return_value=None):
            self.assertTrue(work_tool.is_hikvision_unit("MU1034", cameras))
            self.assertEqual(work_tool._camera_vendor("MU1034", cameras[0], cameras), "hikvision")

    def test_heads_never_probe(self):
        with mock.patch.object(self.core, "_probe_camera_vendor") as probe:
            self.assertEqual(work_tool._camera_vendor("RD3076", {"host": "10.0.0.2"}, []), "dahua")
            probe.assert_not_called()


class PlaceholderEmails(unittest.TestCase):
    def test_flags_dummy_addresses(self):
        for email in ("jdoe@placeholderemail.com", "X@PlaceholderEmail.com",
                      "a@fakeemail.com", "fakeemail123@gmail.com"):
            self.assertTrue(work_tool._is_placeholder_email(email), email)

    def test_keeps_real_addresses_and_non_emails(self):
        for value in ("ops@customer.com", "", "Fakeemail Jones"):
            self.assertFalse(work_tool._is_placeholder_email(value), value)

    def test_strips_from_comma_list_cell(self):
        self.assertEqual(
            work_tool._strip_placeholder_emails(
                "a@real.com, b@placeholderemail.com,c@fakeemail.com , d@real.org"
            ),
            "a@real.com, d@real.org",
        )
        self.assertEqual(work_tool._strip_placeholder_emails("x@fakeemail.com"), "")
        self.assertEqual(work_tool._strip_placeholder_emails("602-555-0100"), "602-555-0100")


class GetArtContacts(unittest.TestCase):
    def test_returns_to_and_cc_lists(self):
        info = {"to_emails": ["a@real.com"], "cc_emails": ["b@real.com", "c@real.org"]}
        with mock.patch.object(work_tool._core, "get_art_site_contacts", return_value=(info, None)):
            to, cc = work_tool.get_art_contacts("RD3401")
        self.assertEqual(to, ["a@real.com"])
        self.assertEqual(cc, ["b@real.com", "c@real.org"])

    def test_lookup_failure_raises_instead_of_returning_empty(self):
        with mock.patch.object(work_tool._core, "get_art_site_contacts",
                               return_value=(None, "ART login failed — check myemail/mypass")):
            with self.assertRaisesRegex(RuntimeError, "ART login failed"):
                work_tool.get_art_contacts("RD3401")


if __name__ == "__main__":
    unittest.main()
