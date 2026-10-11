import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app
from core.yaml_handler import YamlConfigManager

class TestClashProxyStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_index(self):
        """Verify frontend HTML is served"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("CLASH LIVE PROXY STUDIO", resp.text)

    def test_configs_list(self):
        """Verify configs discovery endpoint"""
        resp = self.client.get("/api/configs/list")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("configs", data)
        self.assertIsInstance(data["configs"], list)
        self.assertTrue(len(data["configs"]) > 0)

    def test_configs_current(self):
        """Verify current loaded config endpoint"""
        resp = self.client.get("/api/configs/current")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("proxies", data)
        self.assertIn("proxy_groups", data)
        self.assertIn("filename", data)
        self.assertTrue(len(data["proxies"]) > 0)

    def test_system_status(self):
        """Verify system status endpoint"""
        resp = self.client.get("/api/system/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("binary_available", data)
        self.assertIn("controller_port", data)

    def test_yaml_manager_memory_operations(self):
        """Test YAML CRUD logic in memory / temp file"""
        dummy_yaml = (
            "port: 7890\n"
            "proxies:\n"
            "  - name: TEST-NODE-1\n"
            "    type: trojan\n"
            "    server: support.zoom.us\n"
            "    port: 443\n"
            "    password: pass123\n"
            "proxy-groups:\n"
            "  - name: PROXIES\n"
            "    type: select\n"
            "    proxies:\n"
            "      - TEST-NODE-1\n"
            "rules:\n"
            "  - MATCH,DIRECT\n"
        )
        temp_path = os.path.join(BASE_DIR, "tests", "temp_test_config.yaml")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(dummy_yaml)

        try:
            mgr = YamlConfigManager(backup_dir=os.path.join(BASE_DIR, "backups"))
            data = mgr.load_config(temp_path)
            self.assertEqual(len(data.get("proxies", [])), 1)
            self.assertEqual(data["proxies"][0]["name"], "TEST-NODE-1")

            # Test add proxy
            new_node = {
                "name": "TEST-NODE-2",
                "type": "trojan",
                "server": "support.zoom.us",
                "port": 443,
                "password": "pass456"
            }
            res_add = mgr.add_proxy(temp_path, new_node)
            self.assertTrue(res_add)

            # Verify proxy count is now 2
            data2 = mgr.load_config(temp_path)
            self.assertEqual(len(data2.get("proxies", [])), 2)

            # Test update proxy
            updated_node = dict(new_node)
            updated_node["server"] = "v.whatsapp.net"
            res_upd = mgr.update_proxy(temp_path, "TEST-NODE-2", updated_node)
            self.assertTrue(res_upd)

            # Verify update
            data_upd = mgr.load_config(temp_path)
            node2 = next(p for p in data_upd["proxies"] if p["name"] == "TEST-NODE-2")
            self.assertEqual(node2["server"], "v.whatsapp.net")

            # Test delete
            res_del = mgr.delete_proxy(temp_path, "TEST-NODE-2")
            self.assertTrue(res_del)

            # Verify back to 1
            data3 = mgr.load_config(temp_path)
            self.assertEqual(len(data3.get("proxies", [])), 1)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_link_parser_dual_mode(self):
        """Test RawLinkParser parsing and bolak/wild expansion"""
        from core.link_parser import RawLinkParser
        raw_text = (
            "trojan://pass1@leaseweb4.svrkencang.web.id:443?security=tls&type=ws&path=%2Ftrojan&host=leaseweb4.svrkencang.web.id&sni=leaseweb4.svrkencang.web.id#(dingga) [Trojan - ws] TLS\n"
            "trojan://pass2@nusa3.aixxycode.my.id:443?security=tls&type=ws&path=%2Ftrojan&host=nusa3.aixxycode.my.id&sni=nusa3.aixxycode.my.id#(dingga) [Trojan - ws] TLS"
        )
        proxies = RawLinkParser.convert_to_clash_proxies(raw_text, bug_host="support.zoom.us", dual_mode=True)
        self.assertEqual(len(proxies), 4)
        names = [p["name"] for p in proxies]
        self.assertIn("DINGGA-LEASEWEB4-BOLAK", names)
        self.assertIn("DINGGA-LEASEWEB4-WILD", names)
        self.assertIn("DINGGA-NUSA3-BOLAK", names)
        self.assertIn("DINGGA-NUSA3-WILD", names)

    def test_export_live_only_endpoint(self):
        """Test POST /api/export/live-only returns filtered YAML with live nodes only"""
        resp = self.client.post("/api/export/live-only", json={
            "live_names": ["ID-NUSA3-BOLAK", "ID-T1-BOLAK"]
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ID-NUSA3-BOLAK", resp.text)
        self.assertIn("ID-T1-BOLAK", resp.text)
        self.assertIn("AUTO-BESTPING", resp.text)
        self.assertIn("DINGGA-SELECT", resp.text)

    def test_proxies_to_raw_links_endpoint(self):
        """Test POST /api/proxies/to-raw-links reconstructs raw 1-line URIs"""
        resp = self.client.post("/api/proxies/to-raw-links", json={
            "names": ["ID-NUSA3-BOLAK"]
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertTrue(data["links"][0].startswith("trojan://"))
        self.assertIn("nusa3.aixxycode.my.id", data["links"][0])

    def test_save_to_onedrive_endpoint(self):
        """Test POST /api/configs/save-to-onedrive saves clean YAML"""
        sample_yaml = (
            "port: 7890\n"
            "proxies:\n"
            "- name: TEST-SAVE-NODE\n"
            "  type: trojan\n"
            "  server: support.zoom.us\n"
            "  port: 443\n"
            "  password: pass\n"
        )
        resp = self.client.post("/api/configs/save-to-onedrive", json={
            "filename": "TEMP_TEST_ONEDRIVE.yaml",
            "yaml_content": sample_yaml
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        saved_path = data["path"]
        self.assertTrue(os.path.exists(saved_path))
        # Cleanup temp file
        if os.path.exists(saved_path):
            os.remove(saved_path)

if __name__ == "__main__":
    unittest.main()
