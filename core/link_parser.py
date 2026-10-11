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
        Creates a clean node base name derived strictly from the server host.
        Example: 'leaseweb4.svrkencang.web.id' -> 'LEASEWEB4'
                 'id-t1.aixxycode.my.id' -> 'ID-T1'
                 'nusa3.aixxycode.my.id' -> 'NUSA3'
        """
        host_sub = host.split(".")[0].upper() if host else "NODE"
        clean = re.sub(r"[^A-Za-z0-9_-]", "", host_sub).strip("-")
        return clean or "NODE"

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
            orig_base = base_name
            counter = 2
            while base_name in seen_names:
                base_name = f"{orig_base}-{counter}"
                counter += 1
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

    @classmethod
    def proxy_to_raw_link(cls, p: Dict[str, Any], bug_hosts: Optional[List[str]] = None) -> str:
        """
        Converts a Clash proxy dict back into a standard 1-line URI link.
        Works for both BOLAK and WILD proxies, resolving the real VPS domain.
        """
        if not bug_hosts:
            bug_hosts = ["support.zoom.us", "v.whatsapp.net", "zoom.us"]

        ptype = (p.get("type") or "trojan").lower()
        server = p.get("server", "")
        port = p.get("port", 443)
        pwd = p.get("password") or p.get("uuid") or ""
        sni = p.get("sni", "")
        ws_opts = p.get("ws-opts") or {}
        path = ws_opts.get("path", "/trojan" if ptype == "trojan" else "/")
        headers = ws_opts.get("headers") or {}
        host_hdr = headers.get("Host", "")
        name = p.get("name", "Proxy")
        clean_name = re.sub(r"-(BOLAK|WILD)$", "", name, flags=re.IGNORECASE)

        # Resolve real VPS host
        real_host = ""
        for bh in bug_hosts:
            if sni.startswith(bh + "."):
                real_host = sni[len(bh) + 1:]
                break
            elif host_hdr.startswith(bh + "."):
                real_host = host_hdr[len(bh) + 1:]
                break

        if not real_host:
            if host_hdr and host_hdr != server:
                real_host = host_hdr
            elif sni and sni != server:
                real_host = sni
            else:
                real_host = server

        encoded_path = urllib.parse.quote(path)
        remark = f"[{clean_name}]"

        if ptype == "trojan":
            return (
                f"trojan://{pwd}@{real_host}:{port}?"
                f"security=tls&type=ws&headerType=&path={encoded_path}&host={real_host}&sni={real_host}&fp=&allowInsecure=1#"
                f"{urllib.parse.quote(remark)}"
            )
        elif ptype == "vless":
            return (
                f"vless://{pwd}@{real_host}:{port}?"
                f"security=tls&type=ws&headerType=&path={encoded_path}&host={real_host}&sni={real_host}&fp=&allowInsecure=1#"
                f"{urllib.parse.quote(remark)}"
            )
        elif ptype == "vmess":
            vmess_obj = {
                "v": "2",
                "ps": remark,
                "add": real_host,
                "port": port,
                "id": pwd,
                "aid": p.get("alterId", 0),
                "scy": "auto",
                "net": "ws",
                "type": "none",
                "host": real_host,
                "path": path,
                "tls": "tls",
                "sni": real_host
            }
            b64 = base64.b64encode(json.dumps(vmess_obj).encode("utf-8")).decode("utf-8")
            return f"vmess://{b64}"

        return ""

