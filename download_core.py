import os
import sys
import zipfile
import io
import urllib.request
import json

BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
DEST_EXE = os.path.join(BIN_DIR, "mihomo.exe")
FALLBACK_URL = "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.32/mihomo-windows-amd64-compatible-v1.19.32.zip"

def ensure_mihomo_binary():
    if os.path.exists(DEST_EXE) and os.path.getsize(DEST_EXE) > 1000000:
        print(f"[OK] Mihomo binary verified: {DEST_EXE} ({round(os.path.getsize(DEST_EXE)/(1024*1024), 2)} MB)")
        return True

    os.makedirs(BIN_DIR, exist_ok=True)
    print("[*] Mihomo core not found in bin/. Downloading official Mihomo Meta release...")

    download_url = FALLBACK_URL
    try:
        # Try fetching latest release from GitHub API
        api_req = urllib.request.Request(
            "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(api_req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if "windows-amd64-compatible" in name and name.endswith(".zip"):
                    download_url = asset.get("browser_download_url")
                    print(f"[*] Found latest asset: {name}")
                    break
    except Exception as e:
        print(f"[!] Warning: GitHub API check failed ({e}). Using reliable fallback release.")

    print(f"[*] Downloading from: {download_url}")
    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            zip_bytes = resp.read()

        print(f"[*] Downloaded {len(zip_bytes)} bytes. Extracting...")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            # Locate exe in zip
            exe_names = [f for f in z.namelist() if f.endswith(".exe")]
            if not exe_names:
                raise RuntimeError("No .exe found in downloaded zip file")
            
            exe_name = exe_names[0]
            with z.open(exe_name) as zf, open(DEST_EXE, "wb") as out_f:
                out_f.write(zf.read())

        print(f"[SUCCESS] Mihomo core extracted to {DEST_EXE}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download Mihomo core: {e}")
        return False

if __name__ == "__main__":
    success = ensure_mihomo_binary()
    sys.exit(0 if success else 1)
