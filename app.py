import os
import glob
import json
import yaml
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.yaml_handler import YamlConfigManager
from core.mihomo_manager import MihomoManager
from core.link_parser import RawLinkParser

app = FastAPI(title="Clash Live Proxy Studio PC", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = os.path.join(BASE_DIR, "bin", "mihomo.exe")
STATIC_DIR = os.path.join(BASE_DIR, "static")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
def get_onedrive_config_dir() -> str:
    """
    Dynamically resolves the active OneDrive CONFIG directory across PCs:
    Home PC, Office PC, or %OneDrive%/CONFIG
    """
    candidates = []
    if os.environ.get("OneDrive"):
        candidates.append(os.path.join(os.environ["OneDrive"], "CONFIG"))
    if os.environ.get("OneDriveConsumer"):
        candidates.append(os.path.join(os.environ["OneDriveConsumer"], "CONFIG"))
    user_home = os.path.expanduser("~")
    candidates.append(os.path.join(user_home, "OneDrive", "CONFIG"))
    candidates.append(r"C:\Users\ZAVIER\OneDrive\CONFIG")
    candidates.append(r"C:\Users\admin\OneDrive\CONFIG")

    for c in candidates:
        if os.path.exists(c):
            return os.path.normpath(c)

    od_root = os.environ.get("OneDrive") or os.path.join(user_home, "OneDrive")
    target = os.path.join(od_root, "CONFIG")
    os.makedirs(target, exist_ok=True)
    return os.path.normpath(target)

DEFAULT_CONFIG_DIRS = list(dict.fromkeys([
    get_onedrive_config_dir(),
    os.path.normpath(os.path.join(os.path.expanduser("~"), "OneDrive", "CONFIG")),
    os.path.normpath(r"C:\Users\ZAVIER\OneDrive\CONFIG"),
    os.path.normpath(r"C:\Users\admin\OneDrive\CONFIG"),
    os.path.normpath(os.path.join(BASE_DIR, "configs")),
]))

def find_default_primary_file() -> str:
    primary_dir = get_onedrive_config_dir()
    target = os.path.join(primary_dir, "Telkomsel_V6_LIVE_ONLY.yaml")
    if os.path.exists(target):
        return os.path.normpath(target)

    yamls = glob.glob(os.path.join(primary_dir, "*.yaml")) + glob.glob(os.path.join(primary_dir, "*.yml"))
    if yamls:
        return os.path.normpath(yamls[0])

    candidates = [
        r"C:\Users\ZAVIER\OneDrive\CONFIG\Telkomsel_V6_LIVE_ONLY.yaml",
        r"C:\Users\admin\OneDrive\CONFIG\Telkomsel_V6_LIVE_ONLY.yaml",
        os.path.join(os.path.expanduser("~"), "OneDrive", "CONFIG", "Telkomsel_V6_LIVE_ONLY.yaml"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.normpath(c)
    return ""

DEFAULT_PRIMARY_FILE = find_default_primary_file()

# Managers
yaml_mgr = YamlConfigManager(backup_dir=BACKUPS_DIR)
mihomo_mgr = MihomoManager(
    binary_path=BIN_PATH,
    work_dir=os.path.join(BASE_DIR, "core", "workdir"),
    controller_port=19090,
    mixed_port=17890
)

# Active state
current_file_path = DEFAULT_PRIMARY_FILE if os.path.exists(DEFAULT_PRIMARY_FILE) else ""

# Ensure static dir exists
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def resolve_active_file() -> str:
    global current_file_path
    if current_file_path and os.path.exists(current_file_path):
        return current_file_path

    # Try default file
    if os.path.exists(DEFAULT_PRIMARY_FILE):
        current_file_path = DEFAULT_PRIMARY_FILE
        return current_file_path

    # Search in default dirs
    for d in DEFAULT_CONFIG_DIRS:
        if os.path.exists(d):
            matches = glob.glob(os.path.join(d, "*.yaml")) + glob.glob(os.path.join(d, "*.yml"))
            if matches:
                current_file_path = matches[0]
                return current_file_path

    return ""


@app.on_event("startup")
async def startup_event():
    active_path = resolve_active_file()
    if active_path and mihomo_mgr.is_binary_available():
        try:
            mihomo_mgr.start_core(active_path)
            print(f"[Clash Studio] Mihomo core started with config: {active_path}")
        except Exception as e:
            print(f"[Clash Studio] Warning: Could not auto-start Mihomo core: {e}")


@app.on_event("shutdown")
def shutdown_event():
    mihomo_mgr.stop_core()
    print("[Clash Studio] Core stopped.")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Clash Live Proxy Studio</h2><p>Static UI loading...</p>")


@app.get("/api/configs/list")
async def list_configs():
    active_path = resolve_active_file()
    configs = []
    seen = set()

    search_dirs = []
    for d in DEFAULT_CONFIG_DIRS:
        if os.path.exists(d) and d not in search_dirs:
            search_dirs.append(d)

    for d in search_dirs:
        pattern = os.path.join(d, "*.y*ml")
        for f in glob.glob(pattern):
            norm = os.path.abspath(f)
            if norm in seen:
                continue
            seen.add(norm)
            try:
                stat = os.stat(norm)
                # Count proxies quickly
                p_count = 0
                try:
                    with open(norm, "r", encoding="utf-8") as fh:
                        content = fh.read()
                        if "proxies:" in content:
                            parsed = yaml.safe_load(content)
                            p_count = len(parsed.get("proxies", [])) if isinstance(parsed, dict) else 0
                except Exception:
                    p_count = 0

                configs.append({
                    "name": os.path.basename(norm),
                    "path": norm,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "mtime": stat.st_mtime,
                    "proxy_count": p_count,
                    "is_active": os.path.normcase(os.path.normpath(norm)) == os.path.normcase(os.path.normpath(active_path))
                })
            except Exception:
                pass

    return {"configs": configs, "active_path": active_path}


class SelectConfigRequest(BaseModel):
    path: str

@app.post("/api/configs/select")
async def select_config(req: SelectConfigRequest):
    global current_file_path
    normalized_path = os.path.normpath(req.path)
    if not os.path.exists(normalized_path):
        raise HTTPException(status_code=404, detail=f"File not found: {normalized_path}")

    current_file_path = normalized_path
    # Reload mihomo core with this config
    success = False
    error_msg = None
    if mihomo_mgr.is_binary_available():
        try:
            success = mihomo_mgr.start_core(current_file_path)
        except Exception as e:
            error_msg = str(e)

    return {
        "status": "ok",
        "active_path": current_file_path,
        "core_restarted": success,
        "core_error": error_msg
    }


@app.get("/api/configs/current")
async def get_current_config():
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file available")

    try:
        data = yaml_mgr.load_config(active_path)
        return {
            "path": active_path,
            "filename": os.path.basename(active_path),
            "proxies": data.get("proxies", []),
            "proxy_groups": [g.get("name") for g in data.get("proxy-groups", []) if isinstance(g, dict)],
            "mode": data.get("mode", "rule"),
            "core_active": mihomo_mgr.active
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse config: {str(e)}")


@app.get("/api/configs/raw")
async def get_raw_yaml():
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")
    content = yaml_mgr.read_raw_yaml(active_path)
    return {"path": active_path, "content": content}


class SaveRawRequest(BaseModel):
    content: str

@app.post("/api/configs/raw")
async def save_raw_yaml(req: SaveRawRequest):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        yaml_mgr.save_raw_yaml(active_path, req.content)
        # Reload core
        reloaded = False
        if mihomo_mgr.is_binary_available():
            try:
                reloaded = mihomo_mgr.start_core(active_path)
            except Exception:
                pass
        return {"status": "ok", "message": "Saved successfully", "core_reloaded": reloaded}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AddProxyRequest(BaseModel):
    proxy: Dict[str, Any]
    target_groups: Optional[List[str]] = None

@app.post("/api/proxies/add")
async def add_proxy(req: AddProxyRequest):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        yaml_mgr.add_proxy(active_path, req.proxy, req.target_groups)
        if mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)
        return {"status": "ok", "message": f"Proxy '{req.proxy.get('name')}' added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateProxyRequest(BaseModel):
    original_name: str
    proxy: Dict[str, Any]

@app.put("/api/proxies/update")
async def update_proxy(req: UpdateProxyRequest):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        yaml_mgr.update_proxy(active_path, req.original_name, req.proxy)
        if mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)
        return {"status": "ok", "message": f"Proxy '{req.original_name}' updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/proxies/{name}")
async def delete_proxy(name: str):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        yaml_mgr.delete_proxy(active_path, name)
        if mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)
        return {"status": "ok", "message": f"Proxy '{name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/proxies/duplicate/{name}")
async def duplicate_proxy(name: str):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        data = yaml_mgr.load_config(active_path)
        proxies = data.get("proxies", [])
        target = next((p for p in proxies if p.get("name") == name), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Proxy '{name}' not found")

        # Create copy
        copy_proxy = json.loads(json.dumps(target))
        copy_proxy["name"] = f"{name}-COPY"
        # Find unique name if exists
        counter = 1
        while any(p.get("name") == copy_proxy["name"] for p in proxies):
            copy_proxy["name"] = f"{name}-COPY-{counter}"
            counter += 1

        yaml_mgr.add_proxy(active_path, copy_proxy)
        if mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)
        return {"status": "ok", "new_name": copy_proxy["name"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class BulkReplaceRequest(BaseModel):
    old_val: str
    new_val: str
    scope: str = "server"  # 'server', 'sni', 'host_header', or 'all'

@app.post("/api/proxies/bulk-replace-bug")
async def bulk_replace_bug(req: BulkReplaceRequest):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        count = yaml_mgr.bulk_replace_bug(active_path, req.old_val, req.new_val, req.scope)
        if count > 0 and mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)
        return {"status": "ok", "replaced_count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class PurgeDeadRequest(BaseModel):
    dead_names: List[str]

@app.post("/api/proxies/purge-dead")
async def purge_dead(req: PurgeDeadRequest):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration file loaded")

    try:
        count = yaml_mgr.purge_dead_proxies(active_path, req.dead_names)
        if count > 0 and mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)
        return {"status": "ok", "purged_count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class TestProxyRequest(BaseModel):
    name: str
    test_url: str = "http://www.gstatic.com/generate_204"
    timeout_ms: int = 4000

@app.post("/api/test/proxy")
async def test_proxy(req: TestProxyRequest):
    if not mihomo_mgr.active:
        active_path = resolve_active_file()
        if active_path:
            mihomo_mgr.start_core(active_path)

    result = mihomo_mgr.test_single_proxy(req.name, req.test_url, req.timeout_ms)
    return result


class TestAllRequest(BaseModel):
    test_url: str = "http://www.gstatic.com/generate_204"
    timeout_ms: int = 4000

@app.post("/api/test/all")
async def test_all_proxies(req: TestAllRequest):
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration loaded")

    if not mihomo_mgr.active:
        mihomo_mgr.start_core(active_path)

    data = yaml_mgr.load_config(active_path)
    proxies = data.get("proxies", [])
    names = [p.get("name") for p in proxies if p.get("name")]

    results = mihomo_mgr.test_all_proxies(names, req.test_url, req.timeout_ms)
    return {"results": results, "total": len(names)}


@app.get("/api/test/stream")
async def stream_test_all(
    test_url: str = "http://www.gstatic.com/generate_204",
    timeout_ms: int = 4000
):
    """Server-Sent Events (SSE) live streaming testing of all nodes."""
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=404, detail="No configuration loaded")

    if not mihomo_mgr.active:
        mihomo_mgr.start_core(active_path)

    data = yaml_mgr.load_config(active_path)
    proxies = data.get("proxies", [])
    names = [p.get("name") for p in proxies if p.get("name")]

    async def event_generator():
        yield f"data: {json.dumps({'type': 'init', 'total': len(names)})}\n\n"
        
        # Test in small batches to preserve live feedback
        for name in names:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, mihomo_mgr.test_single_proxy, name, test_url, timeout_ms)
            yield f"data: {json.dumps({'type': 'result', 'data': res})}\n\n"
            await asyncio.sleep(0.05)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/system/status")
async def get_system_status():
    status = mihomo_mgr.get_status()
    status["current_file"] = current_file_path
    return status


@app.post("/api/system/restart-core")
async def restart_core():
    active_path = resolve_active_file()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active config file")

    success = mihomo_mgr.start_core(active_path)
    return {"status": "ok", "active": success}


@app.get("/api/export/download")
async def download_config():
    active_path = resolve_active_file()
    if not active_path or not os.path.exists(active_path):
        raise HTTPException(status_code=404, detail="Config file not found")
    return FileResponse(
        active_path,
        media_type="application/x-yaml",
        filename=os.path.basename(active_path)
    )


class CreateNewConfigRequest(BaseModel):
    filename: str
    raw_links: str
    bug_host: str = "support.zoom.us"
    dual_mode: bool = True


@app.post("/api/configs/create-new")
async def create_new_config_endpoint(req: CreateNewConfigRequest):
    global current_file_path
    name = req.filename.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    if not name.endswith(".yaml") and not name.endswith(".yml"):
        name += ".yaml"

    # Save to primary config directory
    target_dir = r"C:\Users\ZAVIER\OneDrive\CONFIG"
    if not os.path.exists(target_dir):
        target_dir = os.path.join(os.path.expanduser("~"), "OneDrive", "CONFIG")
    if not os.path.exists(target_dir):
        target_dir = os.path.join(BASE_DIR, "configs")
    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.normpath(os.path.join(target_dir, name))

    # Parse proxies
    proxies = RawLinkParser.convert_to_clash_proxies(
        raw_text=req.raw_links,
        bug_host=req.bug_host.strip() or "support.zoom.us",
        dual_mode=req.dual_mode
    )

    if not proxies:
        raise HTTPException(status_code=400, detail="Tidak ada link akun yang valid ditemukan dalam teks yang dimasukkan")

    try:
        yaml_mgr.create_new_config(target_path, proxies)
        current_file_path = target_path

        # Restart core with new file
        core_restarted = False
        if mihomo_mgr.is_binary_available():
            core_restarted = mihomo_mgr.start_core(current_file_path)

        return {
            "status": "ok",
            "path": current_file_path,
            "filename": name,
            "proxies_count": len(proxies),
            "core_restarted": core_restarted,
            "proxies": proxies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ImportLinksRequest(BaseModel):
    raw_links: str
    bug_host: str = "support.zoom.us"
    dual_mode: bool = True


@app.post("/api/proxies/import-links")
async def import_links_endpoint(req: ImportLinksRequest):
    active_path = resolve_active_file()
    if not active_path or not os.path.exists(active_path):
        raise HTTPException(status_code=404, detail="No active config file found")

    proxies = RawLinkParser.convert_to_clash_proxies(
        raw_text=req.raw_links,
        bug_host=req.bug_host.strip() or "support.zoom.us",
        dual_mode=req.dual_mode
    )

    if not proxies:
        raise HTTPException(status_code=400, detail="Tidak ada link akun yang valid ditemukan")

    try:
        added_count = yaml_mgr.bulk_add_proxies(active_path, proxies)
        if mihomo_mgr.is_binary_available():
            mihomo_mgr.start_core(active_path)

        return {
            "status": "ok",
            "added_count": added_count,
            "proxies": proxies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExportLiveOnlyRequest(BaseModel):
    live_names: List[str]


@app.post("/api/export/live-only")
async def export_live_only(req: ExportLiveOnlyRequest):
    active_path = resolve_active_file()
    if not active_path or not os.path.exists(active_path):
        raise HTTPException(status_code=404, detail="No active config file found")

    live_set = set(req.live_names)
    if not live_set:
        raise HTTPException(status_code=400, detail="Daftar node aktif kosong, lakukan test terlebih dahulu")

    data = yaml_mgr.load_config(active_path)
    all_proxies = data.get("proxies", [])
    data["proxies"] = [p for p in all_proxies if p.get("name") in live_set]

    # Clean groups
    groups = data.get("proxy-groups", [])
    for group in groups:
        # Rename AUTO-SELECT to DINGGA-SELECT if found
        if group.get("name") == "AUTO-SELECT":
            group["name"] = "DINGGA-SELECT"

        if "proxies" in group and isinstance(group["proxies"], list):
            # Keep group names like AUTO-BESTPING, but filter node names
            retained = []
            for item in group["proxies"]:
                item_name = "DINGGA-SELECT" if item == "AUTO-SELECT" else item
                if item_name in ("DINGGA-SELECT", "AUTO-SELECT", "AUTO-BESTPING", "AUTO-FALLBACK", "LOAD-BALANCE", "MANUAL-LIVE") or item_name in live_set:
                    retained.append(item_name)
            group["proxies"] = retained

    # Update rules to DINGGA-SELECT
    rules = data.get("rules", [])
    new_rules = []
    for r in rules:
        if "AUTO-SELECT" in r:
            new_rules.append(r.replace("AUTO-SELECT", "DINGGA-SELECT"))
        else:
            new_rules.append(r)
    data["rules"] = new_rules

    clean_yaml = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    base_name = os.path.splitext(os.path.basename(active_path))[0]
    out_filename = f"{base_name}_LIVE_ONLY.yaml"

    return HTMLResponse(
        content=clean_yaml,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{out_filename}"'}
    )


class ToRawLinksRequest(BaseModel):
    names: Optional[List[str]] = None


@app.post("/api/proxies/to-raw-links")
async def proxies_to_raw_links_endpoint(req: ToRawLinksRequest):
    active_path = resolve_active_file()
    if not active_path or not os.path.exists(active_path):
        raise HTTPException(status_code=404, detail="No active config file found")

    data = yaml_mgr.load_config(active_path)
    all_proxies = data.get("proxies", [])

    if req.names:
        target_set = set(req.names)
        target_proxies = [p for p in all_proxies if p.get("name") in target_set]
    else:
        target_proxies = all_proxies

    links = []
    for p in target_proxies:
        raw = RawLinkParser.proxy_to_raw_link(p)
        if raw and not raw.startswith("#"):
            links.append(raw)

    return {
        "status": "ok",
        "count": len(links),
        "links": links,
        "raw_text": "\n".join(links)
    }


@app.post("/api/configs/upload")
async def upload_config_file(file: UploadFile = File(...)):
    filename = file.filename
    if not filename.endswith(".yaml") and not filename.endswith(".yml"):
        filename += ".yaml"

    target_dir = get_onedrive_config_dir()
    os.makedirs(target_dir, exist_ok=True)
    dest_path = os.path.normpath(os.path.join(target_dir, filename))

    content = await file.read()
    # Validate YAML
    try:
        parsed = yaml.safe_load(content.decode("utf-8"))
        if not isinstance(parsed, dict) or "proxies" not in parsed:
            raise ValueError("File YAML tidak memiliki daftar 'proxies'")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File YAML tidak valid: {e}")

    with open(dest_path, "wb") as f:
        f.write(content)

    global current_file_path
    current_file_path = dest_path

    core_restarted = False
    if mihomo_mgr.is_binary_available():
        core_restarted = mihomo_mgr.start_core(current_file_path)

    return {
        "status": "ok",
        "path": dest_path,
        "filename": filename,
        "proxy_count": len(parsed.get("proxies", [])),
        "core_restarted": core_restarted,
    }


class SaveToOneDriveRequest(BaseModel):
    filename: str
    yaml_content: str


@app.post("/api/configs/save-to-onedrive")
async def save_to_onedrive_endpoint(req: SaveToOneDriveRequest):
    filename = req.filename.strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    if not filename.endswith(".yaml") and not filename.endswith(".yml"):
        filename += ".yaml"

    target_dir = get_onedrive_config_dir()
    os.makedirs(target_dir, exist_ok=True)
    dest_path = os.path.normpath(os.path.join(target_dir, filename))

    try:
        parsed = yaml.safe_load(req.yaml_content)
        if not isinstance(parsed, dict):
            raise ValueError("Konten bukan format YAML dictionary yang valid")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Syntax YAML tidak valid: {e}")

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(req.yaml_content)

    return {
        "status": "ok",
        "path": dest_path,
        "filename": filename,
        "target_dir": target_dir,
    }



