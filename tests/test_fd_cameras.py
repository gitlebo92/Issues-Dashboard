"""
Tests for work_tool/fd_cameras.py's lease parsing — real MikroTik
`/ip dhcp-server lease print terse` lines, no network:

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool.fd_cameras as fdc  # noqa: E402

FD1034_LEASES = """
 2 comment=SC-FD1034-CBRE-EW-S-Bldg-Spkr1-N-(Connected-SBldg-NetonixSwitch-P2) address=10.20.60.18 mac-address=00:66:6A:00:0B:E2 status=bound
 1 comment=SC-FD1034-CBRE-EW-S-Bldg-NetonixSwitch(Connected-SBldgCubeChild-NBldgCubeParent) address=10.20.60.9 mac-address=EC:13:B2:D2:99:90 status=bound host-name=FD1034-CBRE-EW-SBldgSwitch
11 comment=SC-FD1034-CBRE-EW-S-Bldg-C02-Ent-E-(Connected-SBldg-NetonixSwitch-P5) address=10.20.60.32 mac-address=3C:E3:6B:43:A5:10 status=bound active-address=10.20.60.32 host-name=FD1034-CBRE-EW-S-Bldg-C02-Ent-
 7 comment=SC-FD1034-CBRE-EW-N-Bldg-C01-Ent-E-(Connected-NBldg-NetonixSwitch-P7) address=10.20.60.23 mac-address=FC:B6:9D:DE:18:7C status=bound active-address=10.20.60.23 host-name=FD1034-CBRE-EW-N-Bldg-C01-Ent-
15 comment=SC-FD1034-CBRE-EW-N-Bldg-iLO-(Connected-MikrotikRouter-P3) address=10.20.60.4 mac-address=5C:ED:8C:E8:1E:2E status=bound
16 comment=SC-FD1034-CBRE-EW-N-Bldg-Microserver-(Connected-SoutBldg-NetonixSwitch-P2) address=10.20.60.3 mac-address=5C:ED:8C:E8:1E:2A status=bound
"""

FD2001_LEASES = """
 0 comment=inseego address=192.168.0.1 mac-address=00:00:00:00:00:00
 4 comment=SC-FD2001-Speaker address=10.40.0.2 mac-address=00:67:75:00:00:01
 5 comment=SC-FD2001-Camera1 address=10.40.0.4 mac-address=FC:5F:49:00:00:01 host-name=SC-FD2001-C1
 6 address=10.40.0.6 mac-address=FC:5F:49:00:00:02 host-name=SC-FD2001-C2
"""


class ParseDhcpLeases(unittest.TestCase):
    def test_terse_lines_become_key_value_dicts(self):
        leases = fdc.parse_dhcp_leases(FD1034_LEASES)
        self.assertEqual(len(leases), 6)
        self.assertEqual(leases[2]["address"], "10.20.60.32")
        self.assertEqual(leases[2]["mac-address"], "3C:E3:6B:43:A5:10")
        self.assertTrue(leases[2]["comment"].startswith("SC-FD1034-CBRE-EW-S-Bldg-C02"))


class CamerasFromLeases(unittest.TestCase):
    def test_multi_building_site_keeps_only_cameras_sorted_by_ip(self):
        cams = fdc.cameras_from_leases(fdc.parse_dhcp_leases(FD1034_LEASES), "FD1034")
        self.assertEqual(
            [(c["ip"], c["number"], c["name"]) for c in cams],
            [
                ("10.20.60.23", 1, "CBRE-EW-N-Bldg-C01-Ent-E"),
                ("10.20.60.32", 2, "CBRE-EW-S-Bldg-C02-Ent-E"),
            ],
        )

    def test_camera_word_and_host_name_fallback(self):
        cams = fdc.cameras_from_leases(fdc.parse_dhcp_leases(FD2001_LEASES), "FD2001")
        self.assertEqual([(c["ip"], c["number"], c["name"]) for c in cams], [
            ("10.40.0.4", 1, "Camera1"),
            ("10.40.0.6", 2, "C2"),
        ])


class FdRouterCameras(unittest.TestCase):
    def setUp(self):
        fdc._fd_camera_cache.clear()

    def test_non_fd_unit_is_refused_without_touching_the_router(self):
        with mock.patch.object(fdc, "_read_router_leases") as read:
            cams, error = fdc.fd_router_cameras("RD3073")
        self.assertIsNone(cams)
        self.assertIn("not an FD unit", error)
        read.assert_not_called()

    def test_found_list_is_cached(self):
        with mock.patch.object(fdc, "router_ip_for_unit", return_value="10.20.60.1"), \
                mock.patch.object(fdc, "_read_router_leases", return_value=(FD1034_LEASES, None)) as read:
            first, _ = fdc.fd_router_cameras("FD1034")
            second, _ = fdc.fd_router_cameras("FD1034")
        self.assertEqual(first, second)
        self.assertEqual(read.call_count, 1)

    def test_unreachable_router_is_cached_briefly_too(self):
        with mock.patch.object(fdc, "router_ip_for_unit", return_value="10.20.51.225"), \
                mock.patch.object(fdc, "_read_router_leases", return_value=("", "timed out")) as read:
            fdc.fd_router_cameras("FD1015")
            cams, error = fdc.fd_router_cameras("FD1015")
        self.assertIsNone(cams)
        self.assertEqual(error, "timed out")
        self.assertEqual(read.call_count, 1)
        with mock.patch.object(fdc, "router_ip_for_unit", return_value="10.20.51.225"), \
                mock.patch.object(fdc, "_read_router_leases", return_value=("", "timed out")) as read:
            fdc.fd_router_cameras("FD1015", refresh=True)
        self.assertEqual(read.call_count, 1)

    def test_router_with_no_camera_leases_says_so(self):
        with mock.patch.object(fdc, "router_ip_for_unit", return_value="10.20.56.97"), \
                mock.patch.object(fdc, "_read_router_leases", return_value=("", None)):
            cams, error = fdc.fd_router_cameras("FD1020")
        self.assertIsNone(cams)
        self.assertIn("no camera leases", error)


FD1040_CAMERAS = [
    {"name": "CoastDlrshp-FL-MzdBldg-C01-RearLot-NW", "number": 1, "ip": "10.20.61.146", "mac": "", "status": "bound"},
    {"name": "CoastDlrshp-FL-MzdUsedBldg-C01-Front-E", "number": 1, "ip": "10.20.61.155", "mac": "", "status": "bound"},
    {"name": "CoastDlrshp-FL-MzdUsedBldg-C02-Rear-W", "number": 2, "ip": "10.20.61.156", "mac": "", "status": "bound"},
    {"name": "CoastDlrshp-FL-BuickBldg-C01-UsedLot-N", "number": 1, "ip": "10.20.61.159", "mac": "", "status": "bound"},
]


class FdCamerasForTicket(unittest.TestCase):
    def _router(self, cameras, error=None):
        return mock.patch.object(fdc, "fd_router_cameras", return_value=(cameras, error))

    def test_subject_naming_a_site_camera_picks_exactly_that_camera(self):
        # Caught live, 2026-09-16: this ticket used to fall through to the
        # router/compute check and never ping the camera.
        with self._router(FD1040_CAMERAS):
            cams = fdc.fd_cameras_for_ticket(
                "FD1040",
                "HOU - FD1040 - Camera Outage MzdUsedBldg-C02-Rear-W down - Coast Buick GMC Mazda",
            )
        self.assertEqual([c["ip"] for c in cams], ["10.20.61.156"])
        self.assertEqual(fdc.fd_camera_label(cams[0]), "MzdUsedBldg-C02")
        self.assertEqual(fdc.fd_camera_target(cams[0]), "fd:coastdlrshp-fl-mzdusedbldg-c02-rear-w")

    def test_generic_outage_pings_every_router_camera(self):
        with self._router(FD1040_CAMERAS):
            cams = fdc.fd_cameras_for_ticket("FD1040", "SLC-FD1040-Camera Outage-10/07/26", generic=True)
        self.assertEqual(len(cams), 4)

    def test_bare_camera_number_only_when_unique_on_the_site(self):
        with self._router(FD1040_CAMERAS):
            self.assertIsNone(fdc.fd_cameras_for_ticket("FD1040", "FD1040 C1 down", ["camera1"]))
            self.assertEqual(
                [c["ip"] for c in fdc.fd_cameras_for_ticket("FD1040", "FD1040 C2 down", ["camera2"])],
                ["10.20.61.156"],
            )

    def test_no_change_when_not_fd_unreachable_or_unrelated(self):
        with self._router(FD1040_CAMERAS) as router:
            self.assertIsNone(fdc.fd_cameras_for_ticket("RD3073", "Camera Outage C02 down", ["camera2"]))
            self.assertIsNone(fdc.fd_cameras_for_ticket("FD1040", "FD1040 - Unit Outage Full - Coast"))
            router.assert_not_called()  # no camera named: never asks the router
        with self._router(None, "timed out"):
            self.assertIsNone(fdc.fd_cameras_for_ticket("FD1040", "Camera Outage MzdUsedBldg-C02-Rear-W down"))

    def test_ping_camera_resolves_fd_targets_through_the_router_list(self):
        import work_tool._core as core
        with self._router(FD1040_CAMERAS), \
                mock.patch.object(core, "_ping_host", return_value=(0, "Reply from 10.20.61.156: TTL=60")) as ping:
            up, _output, error = core.ping_camera_status("FD1040", "fd:CoastDlrshp-FL-MzdUsedBldg-C02-Rear-W")
        ping.assert_called_once_with("10.20.61.156")
        self.assertTrue(up)
        self.assertIsNone(error)
        with self._router(FD1040_CAMERAS):
            up, _output, error = core.ping_camera_status("FD1040", "fd:Renamed-C09")
        self.assertIsNone(up)
        self.assertIn("no longer in FD1040's router camera list", error)


if __name__ == "__main__":
    unittest.main()
