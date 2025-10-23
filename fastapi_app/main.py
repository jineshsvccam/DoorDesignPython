from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse
import asyncio
import tempfile, os, sys
from pathlib import Path

# --- Add this to ensure imports work correctly ---
# If your main FastAPI app is under /fastapi_app and BatchDoorDXFGenerator.py is in parent folder
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Import your DXF generator helper
from BatchDoorDXFGenerator import generate_zip_from_excel
from typing import Optional
from DoorDrawingGenerator import DoorDrawingGenerator
from fastapi_app.schemas_input import DoorDXFRequest
from door_geometry import compute_door_geometry

# Serve the frontend static files and allow CORS for external UI (optional)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Mount the frontend directory under /static and serve index.html at root
frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
if frontend_dir.exists():
    # Mounting at '/' causes StaticFiles to take precedence for all paths and
    # will return 405 for POST requests (StaticFiles only allows GET/HEAD).
    # Mount under '/static' and serve index.html explicitly at '/'.
    app.mount("/static", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(
                str(index_path), 
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        return {"detail": "Frontend index.html not found"}

# Allow CORS from anywhere (change to specific origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-dxf/")
async def generate_dxf(file: UploadFile = File(...)):
    # Save uploaded Excel temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(await file.read())
        excel_path = tmp.name

    try:
        # Call your existing helper that generates the ZIP
        zip_path = generate_zip_from_excel(excel_path)
        if not zip_path or not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail="Failed to generate DXF ZIP archive")

        return FileResponse(
            path=zip_path,
            filename=os.path.basename(zip_path),
            media_type="application/zip"
        )
    finally:
        # Clean up temp Excel file
        try:
            os.remove(excel_path)
        except Exception:
            pass


@app.post("/generate-single-dxf/")
async def generate_single_dxf(params: DoorDXFRequest = Body(...)):
    """Generate one DXF from JSON parameters and return the DXF file.

    The generator is synchronous/blocking, so we run it in a thread to avoid
    blocking the event loop. The generator now accepts the Pydantic model.
    """
    script_dir = Path(__file__).resolve().parents[1]
    output_dir = Path(script_dir) / "output"
    output_dir.mkdir(exist_ok=True)

    # Sanitize filename to avoid path traversal and ensure a basename
    filename = os.path.basename(params.metadata.file_name or "door_output.dxf")
    out_path = output_dir / filename

    try:
        # run the potentially blocking generation in a thread
        await asyncio.to_thread(DoorDrawingGenerator.generate_door_dxf, params, file_name=str(out_path), isannotationRequired=True, save_file=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DXF generation failed: {e}")

    if not out_path.exists():
        raise HTTPException(status_code=500, detail="DXF file was not created")

    # Return the file and force download via Content-Disposition header
    return FileResponse(
        path=str(out_path),
        filename=out_path.name,
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{out_path.name}"'}
    )


@app.post("/dxf/geometry")
async def get_dxf_geometry(params: DoorDXFRequest = Body(...)):
    """Return computed geometry JSON (no DXF writing) for preview or frontend use."""
    try:
        schema = compute_door_geometry(params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return schema.dict()


if __name__ == "__main__":
    # When running locally or on Replit this will use the PORT env var if present.
    port = int(os.environ.get("PORT", 8000))
    # Optional debug attach: set DEBUG_WAIT=1 in env to wait for debugger attach
    if os.environ.get("DEBUG_WAIT") == "1":
        try:
            import debugpy
            print("Waiting for debugger to attach on 5678...")
            debugpy.listen(5678)
            debugpy.wait_for_client()
            print("Debugger attached, continuing...")
        except Exception:
            print("debugpy not available or failed to start; continuing without debugger")

    uvicorn.run("fastapi_app.main:app", host="0.0.0.0", port=port, log_level="info")
