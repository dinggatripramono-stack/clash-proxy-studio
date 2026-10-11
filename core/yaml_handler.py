import os
import shutil
import time
from typing import Dict, List, Any, Optional
import yaml

class YamlConfigManager:
    """
    Zero-defect YAML configuration manager for Clash / Mihomo configs.
    Supports safe loading, updating, backing up, and atomic writes.
    """

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def load_config(self, file_path: str) -> Dict[str, Any]:
        """Loads and parses a Clash YAML configuration file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError("Invalid YAML structure: Root must be a dictionary")

        if "proxies" not in data or not isinstance(data["proxies"], list):
            data["proxies"] = []

        return data

    def read_raw_yaml(self, file_path: str) -> str:
        """Reads raw YAML content as string."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def backup_config(self, file_path: str) -> str:
        """Creates a timestamped backup before any write operation."""
        if not os.path.exists(file_path):
            return ""

        filename = os.path.basename(file_path)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}_{timestamp}.bak"
        dest_path = os.path.join(self.backup_dir, backup_name)

        shutil.copy2(file_path, dest_path)
        return dest_path

    def save_config(self, file_path: str, data: Dict[str, Any], create_backup: bool = True) -> str:
        """Saves configuration dictionary to file atomically."""
        if create_backup and os.path.exists(file_path):
            self.backup_config(file_path)

        # Atomic write to temporary file first
        temp_file = f"{file_path}.tmp_{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        shutil.move(temp_file, file_path)
        return file_path

    def save_raw_yaml(self, file_path: str, raw_content: str, create_backup: bool = True) -> None:
        """Validates and saves raw YAML string atomically."""
        # Validate first
        try:
            parsed = yaml.safe_load(raw_content)
            if not isinstance(parsed, dict):
                raise ValueError("YAML root must be a mapping/dictionary")
        except Exception as e:
            raise ValueError(f"YAML Syntax Error: {str(e)}")

        if create_backup and os.path.exists(file_path):
            self.backup_config(file_path)

        temp_file = f"{file_path}.tmp_{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(raw_content)

        shutil.move(temp_file, file_path)

    def update_proxy(self, file_path: str, original_name: str, proxy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Updates an existing proxy and syncs references in proxy groups."""
        data = self.load_config(file_path)
        proxies = data.get("proxies", [])

        idx = -1
        for i, p in enumerate(proxies):
            if p.get("name") == original_name:
                idx = i
                break

        if idx == -1:
            raise KeyError(f"Proxy '{original_name}' not found")

        new_name = proxy_data.get("name", original_name)
        proxies[idx] = proxy_data
        data["proxies"] = proxies

        # If name changed, rename reference in all proxy-groups
        if original_name != new_name:
            groups = data.get("proxy-groups", [])
            for group in groups:
                if "proxies" in group and isinstance(group["proxies"], list):
                    group["proxies"] = [
                        new_name if item == original_name else item
                        for item in group["proxies"]
                    ]

        self.save_config(file_path, data)
        return data

    def add_proxy(self, file_path: str, proxy_data: Dict[str, Any], target_groups: Optional[List[str]] = None) -> Dict[str, Any]:
        """Adds a new proxy node and adds it to designated proxy-groups."""
        data = self.load_config(file_path)
        proxies = data.get("proxies", [])

        name = proxy_data.get("name")
        if not name:
            raise ValueError("Proxy must have a 'name' field")

        # Check duplicate
        if any(p.get("name") == name for p in proxies):
            raise ValueError(f"Proxy with name '{name}' already exists")

        proxies.append(proxy_data)
        data["proxies"] = proxies

        # Add to proxy groups
        groups = data.get("proxy-groups", [])
        for group in groups:
            group_name = group.get("name")
            if target_groups is None or group_name in target_groups:
                if "proxies" in group and isinstance(group["proxies"], list):
                    if name not in group["proxies"]:
                        group["proxies"].append(name)

        self.save_config(file_path, data)
        return data

    def delete_proxy(self, file_path: str, name: str) -> Dict[str, Any]:
        """Deletes a proxy node and purges all references from proxy groups."""
        data = self.load_config(file_path)
        proxies = data.get("proxies", [])

        data["proxies"] = [p for p in proxies if p.get("name") != name]

        # Purge from proxy groups
        groups = data.get("proxy-groups", [])
        for group in groups:
            if "proxies" in group and isinstance(group["proxies"], list):
                group["proxies"] = [item for item in group["proxies"] if item != name]

        self.save_config(file_path, data)
        return data

    def bulk_replace_bug(self, file_path: str, old_val: str, new_val: str, scope: str = "server") -> int:
        """
        Replaces bug host / SNI across all proxies.
        scope: 'server', 'sni', 'host_header', or 'all'
        """
        data = self.load_config(file_path)
        proxies = data.get("proxies", [])
        count = 0

        for p in proxies:
            changed = False
            if scope in ("server", "all") and p.get("server") == old_val:
                p["server"] = new_val
                changed = True

            if scope in ("sni", "all") and p.get("sni") == old_val:
                p["sni"] = new_val
                changed = True

            ws_opts = p.get("ws-opts")
            if isinstance(ws_opts, dict):
                headers = ws_opts.get("headers")
                if isinstance(headers, dict):
                    if scope in ("host_header", "all") and headers.get("Host") == old_val:
                        headers["Host"] = new_val
                        changed = True

            if changed:
                count += 1

        if count > 0:
            self.save_config(file_path, data)

        return count

    def purge_dead_proxies(self, file_path: str, dead_names: List[str]) -> int:
        """Purges a list of dead proxy names from the configuration."""
        data = self.load_config(file_path)
        proxies = data.get("proxies", [])
        dead_set = set(dead_names)

        initial_count = len(proxies)
        data["proxies"] = [p for p in proxies if p.get("name") not in dead_set]
        removed_count = initial_count - len(data["proxies"])

        groups = data.get("proxy-groups", [])
        for group in groups:
            if "proxies" in group and isinstance(group["proxies"], list):
                group["proxies"] = [item for item in group["proxies"] if item not in dead_set]

        if removed_count > 0:
            self.save_config(file_path, data)

        return removed_count

    def bulk_add_proxies(self, file_path: str, new_proxies: List[Dict[str, Any]]) -> int:
        """
        Adds multiple proxy nodes and updates all relevant proxy groups.
        """
        data = self.load_config(file_path)
        existing_proxies = data.get("proxies", [])
        existing_names = {p.get("name") for p in existing_proxies}

        added = []
        for p in new_proxies:
            name = p.get("name")
            if not name:
                continue
            # If duplicate name, append counter
            final_name = name
            counter = 2
            while final_name in existing_names:
                final_name = f"{name}-{counter}"
                counter += 1
            p["name"] = final_name
            existing_names.add(final_name)
            existing_proxies.append(p)
            added.append(final_name)

        data["proxies"] = existing_proxies

        # Update proxy groups
        groups = data.get("proxy-groups", [])
        group_names = {g.get("name") for g in groups}
        
        # Ensure LOAD-BALANCE group exists if missing
        if "LOAD-BALANCE" not in group_names and len(groups) > 0:
            lb_group = {
                "name": "LOAD-BALANCE",
                "type": "load-balance",
                "strategy": "round-robin",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [p.get("name") for p in existing_proxies]
            }
            groups.append(lb_group)
            # Add LOAD-BALANCE to DINGGA-SELECT or AUTO-SELECT if present
            main_select = next((g for g in groups if g.get("name") in ("DINGGA-SELECT", "AUTO-SELECT")), None)
            if main_select and "proxies" in main_select:
                if "LOAD-BALANCE" not in main_select["proxies"]:
                    main_select["proxies"].insert(2, "LOAD-BALANCE")

        for group in groups:
            if "proxies" in group and isinstance(group["proxies"], list):
                for name in added:
                    if name not in group["proxies"]:
                        group["proxies"].append(name)

        self.save_config(file_path, data)
        return len(added)

    def create_new_config(self, file_path: str, proxies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a brand new Clash YAML configuration with complete groups:
        DINGGA-SELECT (Default: AUTO-BESTPING), AUTO-BESTPING, AUTO-FALLBACK, LOAD-BALANCE, MANUAL-LIVE.
        """
        proxy_names = [p.get("name") for p in proxies if p.get("name")]

        new_cfg = {
            "port": 7890,
            "socks-port": 7891,
            "redir-port": 7892,
            "mixed-port": 7893,
            "tproxy-port": 7895,
            "ipv6": False,
            "mode": "rule",
            "log-level": "silent",
            "allow-lan": True,
            "bind-address": "*",
            "external-controller": "0.0.0.0:9090",
            "secret": "",
            "unified-delay": True,
            "tcp-concurrent": True,
            "profile": {
                "store-selected": True,
                "store-fake-ip": True
            },
            "dns": {
                "enable": True,
                "ipv6": False,
                "enhanced-mode": "fake-ip",
                "listen": "0.0.0.0:7874",
                "default-nameserver": [
                    "1.1.1.1",
                    "8.8.8.8",
                    "203.130.196.6",
                    "202.134.0.62"
                ],
                "nameserver": [
                    "https://cloudflare-dns.com/dns-query",
                    "https://dns.google/dns-query",
                    "1.1.1.1",
                    "8.8.8.8"
                ],
                "fallback": [
                    "https://cloudflare-dns.com/dns-query",
                    "https://dns.google/dns-query",
                    "1.0.0.1",
                    "8.8.4.4"
                ],
                "fake-ip-range": "198.18.0.1/16",
                "fake-ip-filter": [
                    "*.lan",
                    "*.local",
                    "*.localhost",
                    "*.msftconnecttest.com",
                    "*.msftncsi.com"
                ]
            },
            "proxies": proxies,
            "proxy-groups": [
                {
                    "name": "DINGGA-SELECT",
                    "type": "select",
                    "proxies": ["AUTO-BESTPING", "AUTO-FALLBACK", "LOAD-BALANCE", "MANUAL-LIVE"] + proxy_names
                },
                {
                    "name": "AUTO-BESTPING",
                    "type": "url-test",
                    "proxies": list(proxy_names),
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 120,
                    "tolerance": 30
                },
                {
                    "name": "AUTO-FALLBACK",
                    "type": "fallback",
                    "proxies": list(proxy_names),
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 120
                },
                {
                    "name": "LOAD-BALANCE",
                    "type": "load-balance",
                    "strategy": "round-robin",
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 300,
                    "proxies": list(proxy_names)
                },
                {
                    "name": "MANUAL-LIVE",
                    "type": "select",
                    "proxies": list(proxy_names)
                }
            ],
            "rules": [
                "MATCH,DINGGA-SELECT"
            ]
        }

        # Write directly
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(new_cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        return new_cfg
