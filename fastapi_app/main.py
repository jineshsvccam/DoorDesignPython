from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import tempfile, os, sys
from pathlib import Path

# --- Add this to ensure imports work correctly ---
# If your main FastAPI app is under /fastapi_app and BatchDoorDXFGenerator.py is in parent folder
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Import your DXF generator helper
from BatchDoorDXFGenerator import generate_zip_from_excel
from pydantic import BaseModel
from typing import Optional
from DoorDrawingGenerator import DoorDrawingGenerator

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


class SingleDoorParams(BaseModel):
    width_measurement: float
    height_measurement: float
    left_side_allowance_width: Optional[float] = 25
    right_side_allowance_width: Optional[float] = 25
    left_side_allowance_height: Optional[float] = 25
    right_side_allowance_height: Optional[float] = 0
    door_minus_measurement_width: Optional[float] = 68
    door_minus_measurement_height: Optional[float] = 70
    bending_width: Optional[float] = 31
    bending_height: Optional[float] = 24
    file_name: Optional[str] = "door_output.dxf"


@app.post("/generate-single-dxf/")
def generate_single_dxf(params: SingleDoorParams):
    """Generate one DXF from JSON parameters and return the DXF file."""
    script_dir = Path(__file__).resolve().parents[1]
    output_dir = Path(script_dir) / "output"
    output_dir.mkdir(exist_ok=True)

    filename = params.file_name or "door_output.dxf"
    out_path = output_dir / filename

    # Prepare kwargs for the generator
    gen_kwargs = params.dict()

    # Ensure save_file=True so DoorDrawingGenerator writes the DXF to disk
    gen_kwargs.update({
        'file_name': str(out_path),
        'isannotationRequired': True,
        'save_file': True,
        # Provide doc/msp if generator supports them; DoorDrawingGenerator will handle defaults
    })

    try:
        DoorDrawingGenerator.generate_door_dxf(**gen_kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DXF generation failed: {e}")

    if not out_path.exists():
        raise HTTPException(status_code=500, detail="DXF file was not created")

    return FileResponse(path=str(out_path), filename=out_path.name, media_type="application/dxf")


if __name__ == "__main__":
    # When running locally or on Replit this will use the PORT env var if present.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("fastapi_app.main:app", host="0.0.0.0", port=port, log_level="info")
