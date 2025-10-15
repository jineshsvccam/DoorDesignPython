Deploying DoorDesignPython (FastAPI + frontend) to Replit

Overview

- This project contains a FastAPI backend in `fastapi_app/main.py` and a simple static UI in the `frontend/` folder.
- The FastAPI app exposes two endpoints used by the UI:
  - POST /generate-dxf/ (accepts an Excel file, returns a ZIP)
  - POST /generate-single-dxf/ (accepts JSON, returns a single DXF)

Files added for Replit

- `requirements.txt` — Python dependencies required by the app.
- `.replit` — Replit run command that starts uvicorn on $PORT.
- `fastapi_app/main.py` — updated to mount `frontend/` as static files and respect $PORT.

Quick deploy steps

1. Create a new Replit using "Import from GitHub" and provide this repository.
2. Replit will detect Python. In the left sidebar, ensure Packages are installed (or run `pip install -r requirements.txt`).
3. Open the Replit Secrets (Environment) and add any secrets if needed. The app reads $PORT automatically.
4. Run the Repl. The `.replit` run command starts uvicorn. The Replit web preview should serve the `index.html` UI at `/`.

Notes & Troubleshooting

- Large DXF/ZIP generation can take time and CPU: Replit free plans may time out or limit CPU. Consider upgrading if you plan to generate many files.
- If you see import errors for local modules, ensure files like `BatchDoorDXFGenerator.py` and `DoorDrawingGenerator.py` are at the repository root (they are). The app adds the repo root to sys.path.
- If Excel reading fails, confirm `openpyxl` (used by pandas) is installed.
- For production, restrict CORS origins in `fastapi_app/main.py` instead of using allow_origins=["*"]

Optional improvements

- Add a service worker or build step to compress frontend assets.
- Add size limits and request timeouts to the upload endpoint.
- Stream ZIP generation back to the client instead of saving to disk to reduce storage usage.
