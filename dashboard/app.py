"""
FastAPI Dashboard Backend for Registry Change Tracker.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uvicorn
from contextlib import asynccontextmanager

from regtracker.storage import list_snapshots, get_snapshot_meta, delete_snapshot, load_snapshot_entries
from regtracker.snapshot import take_snapshot
from regtracker.diff import compare_snapshots

import sys

# Setup paths for PyInstaller compatibility
if getattr(sys, 'frozen', False):
    # Running inside PyInstaller bundle
    BASE_DIR = os.path.join(sys._MEIPASS, "dashboard")
else:
    # Running in normal Python environment
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="Registry Tracker API")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/snapshots")
async def api_list_snapshots():
    snaps = list_snapshots()
    return [{
        "id": s.id,
        "label": s.label,
        "hive_path": f"{s.hive}\\{s.root_path}" if s.root_path else s.hive,
        "timestamp": s.timestamp,
        "entries": s.entry_count
    } for s in snaps]

@app.post("/api/snapshots")
async def api_take_snapshot(request: Request):
    data = await request.json()
    hive_path = data.get("hive_path")
    label = data.get("label", "web_snapshot")
    if not hive_path:
        return JSONResponse({"error": "hive_path is required"}, status_code=400)
    
    try:
        from regtracker.storage import save_snapshot
        result = take_snapshot(hive_path)
        sid = save_snapshot(result, label)
        return {"success": True, "id": sid, "entries": len(result.entries)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/api/snapshots/{snapshot_id}")
async def api_delete_snapshot(snapshot_id: str):
    deleted = delete_snapshot(snapshot_id)
    return {"success": deleted}

@app.get("/api/diff/{snap_a}/{snap_b}")
async def api_get_diff(snap_a: str, snap_b: str, apply_filters: bool = True):
    try:
        entries_a = load_snapshot_entries(snap_a)
        entries_b = load_snapshot_entries(snap_b)
        
        diff = compare_snapshots(snap_a, entries_a, snap_b, entries_b, apply_filters=apply_filters)
        
        # Serialize for frontend
        added = [{"path": f"{k[0]}\\{k[1] or '(Default)'}", "value": e.value_data} for k, e in diff.added.items()]
        deleted = [{"path": f"{k[0]}\\{k[1] or '(Default)'}", "value": e.value_data} for k, e in diff.deleted.items()]
        modified = [{"path": f"{k[0]}\\{k[1] or '(Default)'}", "old": oe.value_data, "new": ne.value_data} for k, (oe, ne) in diff.modified.items()]
        
        return {
            "success": True,
            "added": added,
            "deleted": deleted,
            "modified": modified,
            "filtered": diff.filtered_count
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
