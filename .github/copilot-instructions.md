## Quick orientation for code-writing agents

This repo implements a small web UI + FastAPI backend that generates DXF files (and ZIPs) from door parameter inputs or Excel sheets. Below are the minimal, high-value facts an automated coding assistant needs to be productive here.

1. Architecture (big picture)

   - Backend: `fastapi_app/main.py` — single FastAPI app. Key endpoints:
     - `POST /generate-dxf/` — multipart form upload (Excel file). Calls `BatchDoorDXFGenerator.generate_zip_from_excel` and returns a ZIP.
     - `POST /generate-single-dxf/` — JSON body matching `fastapi_app/schemas_input.DoorDXFRequest`. Calls `DoorDrawingGenerator.generate_door_dxf` and returns a DXF (or PDF when requested).
     - `POST /dxf/geometry` — returns computed geometry JSON using `geometry.door_geometry.compute_door_geometry` (used by the frontend preview).
   - Frontend: static UI under `frontend/` (served at `/` via `app.mount('/static', ...)` and explicit `/` file response). Main behaviour in `frontend/app.js` which posts to the endpoints above.
   - Generation/packing: DXF generation code lives at repository root (`BatchDoorDXFGenerator.py`, `DoorDrawingGenerator.py`) and supporting geometry code in `geometry/` (e.g. `prepare_dimensions`, `door_geometry`, `generate_cutouts`). Packing uses `rectpack` (see `process_bins`).

2. Important files to inspect when changing behaviour

   - `fastapi_app/main.py` — request flow, logging, IP whitelist, env flags, and how endpoints call generator functions.
   - `BatchDoorDXFGenerator.py` — top-level Excel-to-ZIP generator used by `/generate-dxf/`.
   - `DoorDrawingGenerator.py` — low-level DXF/PDF creation.
   - `fastapi_app/schemas_input.py` — Pydantic models expected by `generate-single-dxf` and `/dxf/geometry`.
   - `frontend/app.js` — how the UI builds payloads, field name mappings, and triggers downloads (notably: the UI maps some renamed allowance fields back to legacy backend keys for compatibility).
   - `requirements.txt` — runtime dependencies (FastAPI, uvicorn, pandas/openpyxl, ezdxf, rectpack, etc.).

3. Dev/run/debug workflows (concrete commands)

   - Install deps: `pip install -r requirements.txt` (run from repo root). Use the project's Python venv on Windows PowerShell if present.
   - Run locally (PowerShell):
     python -m uvicorn "fastapi_app.main:app" --reload --host 0.0.0.0 --port 8000
   - Debug attach: set `DEBUG_WAIT=1` in env; the app will try to wait for debugpy on port 5678 when started via `python fastapi_app/main.py` or the uvicorn invocation in `if __name__ == '__main__'`.

4. Runtime and environment flags the agent may need to use or preserve

   - `ALLOWED_IPS` — comma-separated IPs or CIDR ranges; if set, requests are IP-whitelisted by middleware.
   - `FULL_BODY_LOGGING` and `MAX_FULL_BODY_BYTES` — controls per-request logged payload capture (defaults in `fastapi_app/main.py`).
   - `PORT` — used by Replit/containers; `fastapi_app/main.py` reads it when run as script.

5. Conventions and gotchas (project-specific)

   - The backend appends the repo root to `sys.path` so many generators live at repo root (e.g. `BatchDoorDXFGenerator.py`) — imports are not strictly package-scoped.
   - Frontend/backwards compatibility: `frontend/app.js` maps `top_side_allowance_height` -> `left_side_allowance_height` and `bottom_side_allowance_height` -> `right_side_allowance_height` to preserve older backend expectations — don't change these keys in the API without updating the UI mapping and `fastapi_app/schemas_input.py`.
   - Output folder: generated DXFs and ZIPs are placed under `output/` and temporary logs go to `fastapi_app/logs/` (per-request JSON files and `app.log`). Be conservative when changing file IO/cleanup.
   - Large DXF/ZIP creation is CPU and memory intensive (rectpacking + ezdxf): unit tests should avoid heavy full-generation runs and prefer small mocked inputs or the `/dxf/geometry` path which is lightweight.

6. Example code patterns to follow or reference

   - Endpoint payloads: follow `DoorDXFRequest` Pydantic shape in `fastapi_app/schemas_input.py`.
   - Packing call example: `process_bins(rectangles, door_params_list, sheet_width=1250, sheet_height=2500, isannotationRequired=True)` (see `main.py`). Use named args for clarity.
   - Preview flow: frontend calls `/dxf/geometry` and then `drawGeometryToFabric(...)` in `frontend/app.js` to render Fabric.js preview; keep geometry JSON stable.

7. When changing API surface or field names
   - Update `fastapi_app/schemas_input.py`, `frontend/app.js` mappings, and any codepaths in `BatchDoorDXFGenerator.py`/`DoorDrawingGenerator.py`. Preserve backward compatibility where possible (the UI contains explicit compatibility shims).

If anything here is unclear or you want more coverage (unit-test guidelines, recommended small input fixtures, or a short sample request payload), tell me which section to expand and I'll iterate.
