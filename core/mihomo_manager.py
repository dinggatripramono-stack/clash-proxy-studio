import os
import time
import json
import shutil
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
import yaml

class MihomoManager:
    """
    Manages the isolated Mihomo (Clash.Meta) runtime process for safe,
    non-interfering proxy latency and alive-check testing on Windows PC.
    """

    def __init__(
        self,
        binary_path: str = "bin/mihomo.exe",
        work_dir: str = "core/workdir",
        controller_port: int = 19090,
        mixed_port: int = 17890
    ):
        self.binary_path = binary_path
        self.work_dir = work_dir
        self.controller_port = controller_port
        self.mixed_port = mixed_port
        self.process: Optional[subprocess.Popen] = None
        self.current_config_path: Optional[str] = None
        self.active = False
        os.makedirs(self.work_dir, exist_ok=True)

    def is_binary_available(self) -> bool:
        return os.path.isfile(self.binary_path)

    def generate_isolated_config(self, source_config_path: str) -> str:
        """
        Generates an isolated config that uses safe ports and disables
        system interference (TUN, global hijack, DNS listen conflicts).
        """
        with open(source_config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        if not isinstance(cfg, dict):
            raise ValueError("Invalid source configuration")

        # Force isolated test ports
        cfg["port"] = 0
        cfg["socks-port"] = 0
        cfg["redir-port"] = 0
        cfg["tproxy-port"] = 0
        cfg["mixed-port"] = self.mixed_port
        cfg["external-controller"] = f"127.0.0.1:{self.controller_port}"
        cfg["secret"] = ""
        cfg["log-level"] = "silent"
        cfg["mode"] = "rule"

        # Sanitize DNS to prevent port 53 / 7874 conflict
        if "dns" in cfg and isinstance(cfg["dns"], dict):
            cfg["dns"]["enable"] = True
            cfg["dns"]["listen"] = "127.0.0.1:17874"

        # Remove tun mode if present
        if "tun" in cfg:
            del cfg["tun"]

        dest_path = os.path.join(self.work_dir, "runtime_test_config.yaml")
        with open(dest_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

        return dest_path

    def start_core(self, source_config_path: str) -> bool:
        """Starts the Mihomo process with the given config."""
        if not self.is_binary_available():
            raise FileNotFoundError(f"Mihomo binary not found at '{self.binary_path}'")

        # Stop existing process if running
        self.stop_core()

        test_config = self.generate_isolated_config(source_config_path)
        self.current_config_path = source_config_path

        # Start background subprocess
        creationflags = 0
        if os.name == "nt":
            # CREATE_NO_WINDOW = 0x08000000 to keep it background
            creationflags = 0x08000000

        self.process = subprocess.Popen(
            [self.binary_path, "-d", self.work_dir, "-f", test_config],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags
        )

        # Wait up to 3 seconds for controller to become ready
        start_time = time.time()
        ready = False
        while time.time() - start_time < 3.5:
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                raise RuntimeError(f"Mihomo failed to start: {err}")
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{self.controller_port}/proxies")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.2)

        self.active = ready
        return ready

    def stop_core(self):
        """Stops the Mihomo process cleanly without leaving orphan processes."""
        if self.process:
            pid = self.process.pid
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            
            # Windows extra insurance against zombie processes
            if os.name == "nt" and pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass

            self.process = None
            self.active = False

    def test_single_proxy(
        self,
        proxy_name: str,
        test_url: str = "http://www.gstatic.com/generate_204",
        timeout_ms: int = 4000
    ) -> Dict[str, Any]:
        """
        Tests the delay / alive status of a single proxy node.
        Returns: {"name": str, "alive": bool, "delay": int (ms) or None, "error": str or None}
        """
        if not self.active or not self.process:
            return {
                "name": proxy_name,
                "alive": False,
                "delay": None,
                "error": "Mihomo Core not active"
            }

        encoded_name = urllib.parse.quote(proxy_name)
        api_url = (
            f"http://127.0.0.1:{self.controller_port}/proxies/{encoded_name}/delay"
            f"?url={urllib.parse.quote(test_url)}&timeout={timeout_ms}"
        )

        t_start = time.time()
        try:
            req = urllib.request.Request(api_url)
            with urllib.request.urlopen(req, timeout=(timeout_ms / 1000.0) + 1.5) as resp:
                data = json.loads(resp.read().decode())
                delay = data.get("delay", 0)
                return {
                    "name": proxy_name,
                    "alive": True,
                    "delay": delay,
                    "error": None,
                    "tested_at": time.strftime("%H:%M:%S")
                }
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode())
                err_msg = err_body.get("message", f"HTTP {e.code}")
            except Exception:
                err_msg = f"HTTP {e.code}"
            return {
                "name": proxy_name,
                "alive": False,
                "delay": None,
                "error": err_msg,
                "tested_at": time.strftime("%H:%M:%S")
            }
        except Exception as e:
            return {
                "name": proxy_name,
                "alive": False,
                "delay": None,
                "error": str(e),
                "tested_at": time.strftime("%H:%M:%S")
            }

    def test_all_proxies(
        self,
        proxy_names: List[str],
        test_url: str = "http://www.gstatic.com/generate_204",
        timeout_ms: int = 4000,
        max_workers: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Tests all proxies concurrently and returns detailed latency results.
        """
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(self.test_single_proxy, name, test_url, timeout_ms): name
                for name in proxy_names
            }
            for future in as_completed(future_to_name):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    name = future_to_name[future]
                    results.append({
                        "name": name,
                        "alive": False,
                        "delay": None,
                        "error": str(e),
                        "tested_at": time.strftime("%H:%M:%S")
                    })

        # Sort back to preserve original list order
        order_map = {name: i for i, name in enumerate(proxy_names)}
        results.sort(key=lambda r: order_map.get(r["name"], 999))
        return results

    def get_status(self) -> Dict[str, Any]:
        return {
            "binary_available": self.is_binary_available(),
            "active": self.active and (self.process is not None and self.process.poll() is None),
            "pid": self.process.pid if self.process else None,
            "controller_port": self.controller_port,
            "mixed_port": self.mixed_port,
            "config": self.current_config_path
        }
