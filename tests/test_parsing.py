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

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
