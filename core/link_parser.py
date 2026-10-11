import re
import json
import base64
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional

class RawLinkParser:
    """
    Parser for V2Ray / Clash raw account links:
    - trojan://
    - vless://
    - vmess://
    - ss://
    Expands each account into dual methods:
    1. BOLAK (Bolak-Balik: Bug Host as server, Real Host as SNI & WS Host)
    2. WILD (Wildcard: Bug Host as server, Bug.Real as SNI & WS Host)
    """

    DEFAULT_BUG_HOST = "support.zoom.us"

    @staticmethod
    def clean_name(raw_remark: str, host: str) -> str:
        """
        Creates an intuitive, elegant node base name.
        Example: '(dingga) [Trojan - ws] TLS' on 'leaseweb4.svrkencang.web.id' -> 'DINGGA-LEASEWEB4'
        """
        host_sub = host.split(".")[0].upper() if host else "NODE"
        
        if not raw_remark:
            return host_sub

        remark = urllib.parse.unquote(raw_remark).strip()
        
        # Check if remark has user tag like (dingga) or (zavier)
        user_match = re.search(r"\((.*?)\)", remark)
        user_tag = ""
        if user_match:
            candidate = user_match.group(1).strip()
            # Ignore protocol names in parentheses
            if candidate.lower() not in ("trojan", "vless", "vmess", "ws", "tls", "ss"):
                user_tag = re.sub(r"[^A-Za-z0-9_-]", "", candidate).upper()

        if user_tag:
            return f"{user_tag}-{host_sub}"

        return host_sub

    @classmethod
    def parse_trojan_or_vless(cls, url: str) -> Optional[Dict[str, Any]]:
        try:
            parsed = urllib.parse.urlparse(url)
            proto = parsed.scheme.lower()
            if proto not in ("trojan", "vless"):
                return None

            user_pass = parsed.username or ""
            if not user_pass and ":" in parsed.netloc:
                user_pass = parsed.netloc.split("@")[0]

            host = parsed.hostname or ""
            port = parsed.port or 443

            query = urllib.parse.parse_qs(parsed.query)
            path = query.get("path", ["/trojan" if proto == "trojan" else "/"])[0]
            if not path.startswith("/"):
                path = "/" + path

            ws_host = query.get("host", [host])[0]
            sni = query.get("sni", [host])[0]
            network = query.get("type", ["ws"])[0]
            remark = urllib.parse.unquote(parsed.fragment or "")

            return {
                "type": proto,
                "password": user_pass,
                "real_host": host,
                "port": port,
                "path": path,
                "ws_host": ws_host,
                "sni": sni,
                "network": network,
                "remark": remark,
            }
        except Exception:
            return None

    @classmethod
    def parse_vmess(cls, url: str) -> Optional[Dict[str, Any]]:
        try:
            raw_b64 = url[8:].strip()
            # Fix padding
            raw_b64 += "=" * ((4 - len(raw_b64) % 4) % 4)
            decoded = base64.b64decode(raw_b64).decode("utf-8", errors="ignore")
            data = json.loads(decoded)

            host = data.get("add", "")
            port = int(data.get("port", 443))
            uuid = data.get("id", "")
            alter_id = int(data.get("aid", 0))
            network = data.get("net", "ws")
            path = data.get("path", "/")
            if not path.startswith("/"):
                path = "/" + path

            ws_host = data.get("host", host)
            sni = data.get("sni", host)
            remark = data.get("ps", "")

            return {
                "type": "vmess",
                "uuid": uuid,
                "alterId": alter_id,
                "real_host": host,
                "port": port,
                "path": path,
                "ws_host": ws_host,
                "sni": sni,
                "network": network,
                "remark": remark,
            }
        except Exception:
            return None

    @classmethod
    def parse_single_link(cls, link: str) -> Optional[Dict[str, Any]]:
        link = link.strip()
        if not link:
            return None
        if link.startswith("trojan://") or link.startswith("vless://"):
            return cls.parse_trojan_or_vless(link)
        elif link.startswith("vmess://"):
            return cls.parse_vmess(link)
        return None

    @classmethod
    def convert_to_clash_proxies(
        cls,
        raw_text: str,
        bug_host: str = DEFAULT_BUG_HOST,
        dual_mode: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Parses multi-line text (1 link per line) and converts to Clash proxy dictionaries.
        If dual_mode is True, generates both BOLAK and WILD nodes.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        result = []
        seen_names = set()

        for idx, line in enumerate(lines, 1):
            parsed = cls.parse_single_link(line)
            if not parsed:
                continue

            proto = parsed["type"]
            real_host = parsed["real_host"]
            base_name = cls.clean_name(parsed.get("remark", ""), real_host)
            
            # Ensure base name uniqueness if multiple accounts share host
            if base_name in seen_names:
                base_name = f"{base_name}-{idx}"
            seen_names.add(base_name)

            path = parsed.get("path", "/trojan" if proto == "trojan" else "/")
            port = parsed.get("port", 443)
            network = parsed.get("network", "ws")

            # 1. BOLAK (Bolak-Balik) Node
            bolak_name = f"{base_name}-BOLAK"
            bolak_node: Dict[str, Any] = {
                "name": bolak_name,
                "type": proto,
                "server": bug_host,
                "port": port,
                "skip-cert-verify": True,
                "sni": real_host,
                "network": network,
                "udp": True,
            }
            if proto in ("trojan",):
                bolak_node["password"] = parsed["password"]
            elif proto in ("vless",):
                bolak_node["uuid"] = parsed["password"]
            elif proto in ("vmess",):
                bolak_node["uuid"] = parsed["uuid"]
                bolak_node["alterId"] = parsed.get("alterId", 0)
                bolak_node["cipher"] = "auto"

            if network == "ws":
                bolak_node["ws-opts"] = {
                    "path": path,
                    "headers": {
                        "Host": real_host
                    }
                }

            result.append(bolak_node)

            # 2. WILD (Wildcard) Node
            if dual_mode:
                wild_name = f"{base_name}-WILD"
                wild_host = f"{bug_host}.{real_host}"
                wild_node: Dict[str, Any] = {
                    "name": wild_name,
                    "type": proto,
                    "server": bug_host,
                    "port": port,
                    "skip-cert-verify": True,
                    "sni": wild_host,
                    "network": network,
                    "udp": True,
                }
                if proto in ("trojan",):
                    wild_node["password"] = parsed["password"]
                elif proto in ("vless",):
                    wild_node["uuid"] = parsed["password"]
                elif proto in ("vmess",):
                    wild_node["uuid"] = parsed["uuid"]
                    wild_node["alterId"] = parsed.get("alterId", 0)
                    wild_node["cipher"] = "auto"

                if network == "ws":
                    wild_node["ws-opts"] = {
                        "path": path,
                        "headers": {
                            "Host": wild_host
                        }
                    }

                result.append(wild_node)

        return result
