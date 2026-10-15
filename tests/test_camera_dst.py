"""
Camera DST Fix (work_tool/camera_dst.py) — the edge cases, with every
camera, SSH and Zabbix call mocked. Nothing here touches the network.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import work_tool  # noqa: E402
from work_tool import camera_dst  # noqa: E402

FISHEYE = {"target": "fisheye", "label": "Fisheye", "host": "10.0.0.5", "port": 10080}
CAM1 = {"target": "camera1", "label": "Camera 1", "host": "10.0.0.6", "port": 80}


def _ram(*folders):
    return {"cameras": [{"name": name, "ok": ok} for name, ok in folders]}, None


class _Response:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text


class CameraDstFix(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.dst = {"10.0.0.5": "true", "10.0.0.6": "true"}
        self.writes = []
        self.reboot = (True, "qm reboot 101 finished")
        self.ram = _ram(("Fisheye", False), ("C1-180", True))
        patches = [
            mock.patch.object(camera_dst, "uses_pve", return_value=True),
            mock.patch.object(camera_dst, "_fish_credentials", return_value=("u", "p")),
            mock.patch.object(camera_dst, "_pve_ssh_target", return_value=("10.0.0.11", "root", "x", None)),
            mock.patch.object(camera_dst, "_scrypted_ssh_target", return_value=(None, "10.0.0.12", None)),
            mock.patch.object(camera_dst, "scrypted_ram_folder_status", side_effect=lambda u: self.ram),
            mock.patch.object(camera_dst, "list_unit_cameras", return_value=([CAM1, FISHEYE], None)),
            mock.patch.object(camera_dst, "_camera_vendor", return_value="dahua"),
            mock.patch.object(camera_dst, "_camera_cgi", side_effect=self._cgi),
            mock.patch.object(camera_dst, "_reboot_scrypted_vm", side_effect=lambda u: self.reboot),
            mock.patch.object(camera_dst, "_wait_for_port", return_value=True),
            mock.patch.object(camera_dst.time, "sleep"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(lambda: work_tool.unit_busy_force_clear("RD3417"))

    def _cgi(self, host, port, auth, query):
        if query == "action=getConfig&name=Locales":
            return _Response(200, f"table.Locales.DSTEnable={self.dst[host]}\r\ntable.Locales.TimeFormat=x\r\n")
        value = query.rsplit("=", 1)[1]
        self.writes.append((host, value))
        self.dst[host] = value
        return _Response(200, "OK\r\n")

    def run_fix(self, unit="RD3417"):
        return camera_dst._dst_fix_unit(unit, self.lines.append)

    def test_fixes_only_the_not_populating_camera_and_restores_it(self):
        status, _ = self.run_fix()
        self.assertEqual(status, "fixed")
        self.assertEqual(self.writes, [("10.0.0.5", "false"), ("10.0.0.5", "true")])

    def test_any_camera_not_just_fisheye(self):
        self.ram = _ram(("Fisheye", True), ("C1-180", False), ("C1-PTZ", False))
        status, _ = self.run_fix()
        self.assertEqual(status, "fixed")
        # C1-180 and C1-PTZ are one camera: one off, one back on.
        self.assertEqual(self.writes, [("10.0.0.6", "false"), ("10.0.0.6", "true")])

    def test_dst_restored_even_when_reboot_fails(self):
        self.reboot = (False, "qm reboot 101 failed")
        status, _ = self.run_fix()
        self.assertEqual(status, "failed")
        self.assertEqual(self.dst["10.0.0.5"], "true")

    def test_dst_already_off_is_left_off(self):
        self.dst["10.0.0.5"] = "false"
        status, _ = self.run_fix()
        self.assertEqual(status, "fixed")
        self.assertEqual(self.writes, [])

    def test_all_populating_does_nothing(self):
        self.ram = _ram(("Fisheye", True), ("C1-180", True))
        with mock.patch.object(camera_dst, "_reboot_scrypted_vm") as reboot:
            status, _ = self.run_fix()
        self.assertEqual(status, "nothing")
        reboot.assert_not_called()
        self.assertEqual(self.writes, [])

    def test_unlabelled_folder_is_not_guessed(self):
        self.ram = _ram(("a1b2c3", False))
        with mock.patch.object(camera_dst, "_reboot_scrypted_vm") as reboot:
            status, _ = self.run_fix()
        self.assertEqual(status, "skipped")
        reboot.assert_not_called()

    def test_hikvision_camera_is_skipped(self):
        with mock.patch.object(camera_dst, "_camera_vendor", return_value="hikvision"), \
             mock.patch.object(camera_dst, "_reboot_scrypted_vm") as reboot:
            status, _ = self.run_fix()
        self.assertEqual(status, "skipped")
        reboot.assert_not_called()

    def test_rejected_login_stops_without_retrying_or_rebooting(self):
        calls = []

        def cgi(host, port, auth, query):
            calls.append(port)
            return _Response(401, "")
        with mock.patch.object(camera_dst, "_camera_cgi", side_effect=cgi), \
             mock.patch.object(camera_dst, "_reboot_scrypted_vm") as reboot:
            status, message = self.run_fix()
        self.assertEqual(status, "failed")
        self.assertEqual(calls, [10080])  # no second login attempt on another port
        reboot.assert_not_called()

    def test_wrong_port_falls_back_to_the_other(self):
        def cgi(host, port, auth, query):
            if port == 10080:
                return _Response(404, "")
            return self._cgi(host, port, auth, query)
        with mock.patch.object(camera_dst, "_camera_cgi", side_effect=cgi):
            status, _ = self.run_fix()
        self.assertEqual(status, "fixed")
        self.assertEqual(self.dst["10.0.0.5"], "true")

    def test_nuc_unit_is_skipped(self):
        with mock.patch.object(camera_dst, "uses_pve", return_value=False):
            status, _ = self.run_fix("RD3071")
        self.assertEqual(status, "skipped")

    def test_busy_unit_is_skipped(self):
        started, token, _ = work_tool.unit_busy_start("RD3417", "Reboot Scrypted")
        self.assertTrue(started)
        status, message = self.run_fix()
        self.assertEqual(status, "skipped")
        self.assertIn("busy", message)

    def test_lock_released_after_run(self):
        self.run_fix()
        self.assertIsNone(work_tool.unit_busy_status("RD3417"))

    def test_fleet_runs_each_unit_and_counts(self):
        rows = [{"unit": "RD3417"}, {"unit": "RD3071"}]
        with mock.patch.object(camera_dst, "fleet_camera_outage_report", return_value=(rows, None)), \
             mock.patch.object(camera_dst, "uses_pve", side_effect=lambda u: u == "RD3417"):
            summary, error = camera_dst.camera_dst_fix_all(self.lines.append)
        self.assertIsNone(error)
        self.assertEqual(len(summary["fixed"]), 1)
        self.assertEqual(len(summary["skipped"]), 1)

    def test_parse_locales(self):
        values = camera_dst._parse_locales("table.Locales.DSTEnable=false\r\ntable.Locales.DSTStart.Month=3\n")
        self.assertEqual(values, {"DSTEnable": "false", "DSTStart.Month": "3"})


class RamLabelToCamera(unittest.TestCase):
    def test_labels(self):
        name = work_tool._camera_target_for_ram_camera_name
        self.assertEqual(name("Fisheye"), "fisheye")
        self.assertEqual(name("C2-PTZ"), "camera2")
        self.assertEqual(name("Camera 3"), "camera3")
        self.assertIsNone(name("a1b2c3"))


if __name__ == "__main__":
    unittest.main()
