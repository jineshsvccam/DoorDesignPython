import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import time
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import Request as StarletteRequest

# Context variable to store request_id throughout the request lifecycle
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

# Configure fontconfig for Linux systems (must be done before font imports)
if os.name == 'posix':
    if 'FONTCONFIG_PATH' not in os.environ:
        os.environ['FONTCONFIG_PATH'] = '/etc/fonts'
    if 'FONTCONFIG_FILE' not in os.environ:
        os.environ['FONTCONFIG_FILE'] = '/etc/fonts/fonts.conf'

# Add parent directory to Python path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv(str(Path(__file__).resolve().parents[1] / ".env"))
except Exception:
    pass

# Project imports
from BatchDoorDXFGenerator import generate_zip_from_excel, process_bins
from DoorDrawingGenerator import DoorDrawingGenerator
from fastapi_app.routes.auth import router as auth_router
from fastapi_app.schemas_input import DoorDXFRequest
from fastapi_app.log_helper import (
    parse_json_log_entry,
    process_request_start,
    process_request_finish,
    process_dxf_generation,
    process_response_log,
    process_pdf_generation,
    build_single_executions,
    associate_bulk_files,
    build_bulk_executions,
)
from geometry.door_geometry import compute_door_geometry
from geometry.prepare_dimensions import prepare_dimensions

from fastapi_app.services.cookie_service import get_cookie_token, create_cookie_token
from fastapi_app.services.jwt_service import JWT_COOKIE_NAME, verify_access_token
from fastapi_app.services.user_service import USERS_FILE_PATH, find_device_by_id

# Serve the frontend static files and allow CORS for external UI (optional)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Process start time for uptime reporting
START_TIME = time.time()

# --- Logging setup -------------------------------------------------
logs_dir = Path(__file__).resolve().parents[1] / "fastapi_app" / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
logfile = logs_dir / "app.log"

handler = RotatingFileHandler(str(logfile), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
handler.setFormatter(formatter)

logger = logging.getLogger("doorapp")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(handler)

# Attach to uvicorn loggers so access/error show in same file
logging.getLogger("uvicorn.access").addHandler(handler)
logging.getLogger("uvicorn.error").addHandler(handler)

# Attach handler to DoorDrawingGenerator logger so its messages appear in app.log
dxf_logger = logging.getLogger("DoorDrawingGenerator")
dxf_logger.setLevel(logging.DEBUG)  # Capture debug messages too
if not dxf_logger.handlers:
    dxf_logger.addHandler(handler)

# Include auth routes
app.include_router(auth_router, tags=["Authentication"])

# Register middleware and exception handlers
from fastapi_app import middleware

# Initialize middleware with app context
middleware.init_middleware(logger, logs_dir, request_id_ctx)

app.middleware("http")(middleware.ip_whitelist_middleware)
app.middleware("http")(middleware.auth_middleware)
app.middleware("http")(middleware.request_logging_middleware)
app.exception_handler(Exception)(middleware.global_exception_handler)


# Mount the frontend directory under /static and serve index.html at root
frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
if frontend_dir.exists():
    # Mounting at '/' causes StaticFiles to take precedence for all paths and
    # will return 405 for POST requests (StaticFiles only allows GET/HEAD).
    # Mount under '/static' and serve index.html explicitly at '/'.
    app.mount("/static", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    async def serve_index(request: StarletteRequest):
        auth_token = None
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header:
            scheme, _, token = auth_header.partition(" ")
            if scheme.lower() == "bearer" and token:
                auth_token = token.strip()

        if not auth_token:
            auth_token = request.cookies.get(JWT_COOKIE_NAME)

        authenticated = False
        if auth_token:
            payload = verify_access_token(auth_token)
            if payload:
                device = find_device_by_id(payload.get("sub", ""))
                authenticated = bool(device and device.get("status") == "active")

        if not authenticated:
            cookie_token = get_cookie_token(request)
            if cookie_token and os.path.exists(USERS_FILE_PATH):
                try:
                    with open(USERS_FILE_PATH, "r", encoding="utf-8") as file:
                        for line in file:
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 2 and parts[1] == "active":
                                if cookie_token == create_cookie_token(parts[0]):
                                    authenticated = True
                                    break
                except Exception:
                    authenticated = False

        if not authenticated:
            forbidden_path = frontend_dir / "forbidden.html"
            if forbidden_path.exists():
                return FileResponse(
                    str(forbidden_path),
                    media_type="text/html",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
            return {"detail": "Access forbidden"}

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

    @app.get("/logs", include_in_schema=False)
    async def serve_log_summary():
        log_summary_path = frontend_dir / "summary.html"
        if log_summary_path.exists():
            return FileResponse(
                str(log_summary_path), 
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        return {"detail": "Log summary page not found"}

# Allow CORS from anywhere (change to specific origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.post("/generate-dxf/")
async def generate_dxf(
    file: UploadFile = File(...),
    sheet_size: Optional[str] = Form("1250x2500"),
    annotation_required: Optional[bool] = Form(True, description="Include annotations in DXF output"),
    pdf_required: Optional[bool] = Form(True, description="Generate merged PDF of all bins"),
):
    """Accept an uploaded Excel file and optional parameters.

    Args:
        file: Excel file containing door specifications
        sheet_size: Sheet dimensions as WIDTHxHEIGHT (e.g. 1250x2500). Defaults to 1250x2500
        annotation_required: Whether to include annotations in generated DXF files. Defaults to True
        pdf_required: Whether to generate a merged PDF of all bins. Defaults to True
    """
    # Save uploaded Excel temporarily. Use the uploaded filename's suffix when available
    suffix = Path(file.filename).suffix if file.filename else ".xlsx"
    if not suffix or not suffix.startswith("."):
        suffix = ".xlsx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        excel_path = tmp.name

    try:
        # parse sheet_size into width & height (allow separators like x, X, *, ×)
        width = 1250
        height = 2500
        if sheet_size:
            nums = re.findall(r"(\d+)", sheet_size)
            if len(nums) >= 2:
                try:
                    width = int(nums[0])
                    height = int(nums[1])
                except ValueError:
                    # keep defaults if parsing fails
                    pass

        # Call your existing helper that generates the ZIP
        zip_path = generate_zip_from_excel(
            excel_path, 
            sheet_width=width, 
            sheet_height=height, 
            isannotationRequired=annotation_required if annotation_required is not None else True,
            ispdfrequired=pdf_required if pdf_required is not None else True
        )
        if not zip_path or not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail="Failed to generate DXF ZIP archive")

        return FileResponse(
            path=zip_path,
            filename=os.path.basename(zip_path),
            media_type="application/zip",
        )
    finally:
        # Clean up temp Excel file
        try:
            os.remove(excel_path)
        except Exception:
            pass


@app.post("/generate-dxf-from-requests/")
async def generate_dxf_from_requests(
    requests: List[DoorDXFRequest] = Body(...),
    sheet_size: Optional[str] = Query("1250x2500", description="Sheet size as WIDTHxHEIGHT, e.g. 1250x2500"),
):
    """Accept a JSON array of DoorDXFRequest and produce a ZIP of packed DXFs.

    This builds the rectangles and door parameter list from the provided
    requests, then calls the existing packing/generation path with explicit
    named parameters `sheet_width=` and `sheet_height=`.
    """
    # default sheet
    width = 1250
    height = 2500
    if sheet_size:
        nums = re.findall(r"(\d+)", sheet_size)
        if len(nums) >= 2:
            try:
                width = int(nums[0])
                height = int(nums[1])
            except ValueError:
                pass

    # Build rectangles and door_params_list similar to door_utils.get_door_rectangles
    rectangles = []
    door_params_list = []
    for idx, req in enumerate(requests):
        try:
            params = prepare_dimensions(req)
        except Exception:
            # skip invalid requests
            continue

        is_double = bool(params.get("is_double", False))
        defaults = req.defaults

        # choose bending width depending on double/single — avoid passing None into float()
        bw_raw = params.get("bending_width_double_door") if is_double else params.get("bending_width")
        bending_w = float(defaults.bending_width if bw_raw is None else bw_raw)

        bh_raw = params.get("bending_height")
        bending_h = float(defaults.bending_height if bh_raw is None else bh_raw)

        inner_w = float(params.get("inner_width", 0.0))
        inner_h = float(params.get("inner_height", 0.0))

        outer_width = inner_w + bending_w
        outer_height = inner_h + bending_h

        file_name = req.metadata.file_name or f"door_{idx+1}.dxf"

        rectangles.append((outer_width, outer_height, file_name))
        door_params_list.append({
            "request": req,
            "width_measurement": req.dimensions.width_measurement,
            "height_measurement": req.dimensions.height_measurement,
            "left_side_allowance_width": req.dimensions.left_side_allowance_width,
            "right_side_allowance_width": req.dimensions.right_side_allowance_width,
            "left_side_allowance_height": req.dimensions.top_side_allowance_height,
            "right_side_allowance_height": req.dimensions.bottom_side_allowance_height,
            "door_minus_measurement_width": defaults.door_minus_measurement_width,
            "door_minus_measurement_height": defaults.door_minus_measurement_height,
            "bending_width": bending_w,
            "bending_height": bending_h,
            "outer_width": outer_width,
            "outer_height": outer_height,
            "file_name": file_name,
            "door_name": req.metadata.label or file_name,
        })

    # Call existing pack/generate path with named sheet args
    bins, zip_path = process_bins(rectangles, door_params_list, sheet_width=width, sheet_height=height, isannotationRequired=True)

    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=500, detail="Failed to generate DXF ZIP archive from requests")

    return FileResponse(
        path=zip_path,
        filename=os.path.basename(zip_path),
        media_type="application/zip",
    )


@app.get("/health", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
async def healthcheck():
    """Simple healthcheck returning service status and uptime in seconds."""
    uptime = time.time() - START_TIME
    return JSONResponse({"status": "ok", "uptime_s": round(uptime, 3)})


@app.post("/generate-single-dxf/")
async def generate_single_dxf(
    params: DoorDXFRequest = Body(...),
    output_format: str = Query("dxf", description="Output format: dxf, pdf, svg, or png")
):
    """Generate one DXF from JSON parameters and return the DXF file.

    The generator is synchronous/blocking, so we run it in a thread to avoid
    blocking the event loop. The generator now accepts the Pydantic model.
    """
    script_dir = Path(__file__).resolve().parents[1]
    output_dir = Path(script_dir) / "output"
    output_dir.mkdir(exist_ok=True)



    # Sanitize filename to avoid path traversal and ensure a basename
    base_filename = os.path.basename(params.metadata.file_name or "door_output.dxf")
    base, _ = os.path.splitext(base_filename)
    ext = ".dxf"
    if output_format == "pdf":
        ext = ".pdf"
    elif output_format == "svg":
        ext = ".svg"
    elif output_format == "png":
        ext = ".png"
    filename = base + ".dxf"  # Always generate DXF first
    out_path = output_dir / filename
    result_path = output_dir / (base + ext)


    # Get the request_id from context to pass explicitly
    current_request_id = request_id_ctx.get()



    try:
        # run the potentially blocking generation in a thread, passing request_id explicitly
        await asyncio.to_thread(
            DoorDrawingGenerator.generate_door_dxf,
            params,
            None,  # schema
            str(out_path),  # file_name
            None,  # label_name
            True,  # isannotationRequired
            (0.0, 0.0),  # offset
            None,  # doc
            None,  # msp
            True,  # save_file
            False,  # rotated
            current_request_id,  # request_id
            output_format,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File generation failed: {e}")



    # Check for output file existence and return the correct file
    if not result_path.exists():
        raise HTTPException(status_code=500, detail=f"{output_format.upper()} file was not created")

    # Set correct media type
    media_types = {
        "dxf": "application/dxf",
        "pdf": "application/pdf",
        "svg": "image/svg+xml",
        "png": "image/png",
    }
    media_type = media_types.get(output_format, "application/octet-stream")

    return FileResponse(
        path=str(result_path),
        filename=result_path.name,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{result_path.name}"'}
    )


@app.post("/dxf/geometry")
async def get_dxf_geometry(params: DoorDXFRequest = Body(...)):
    """Return computed geometry JSON (no DXF writing) for preview or frontend use."""
    try:
        schema = compute_door_geometry(params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return schema.dict()


@app.get("/api/logs/summary")
async def get_log_summary():
    """Parse app.log and return a structured summary of operations."""
    try:
        logfile = logs_dir / "app.log"
        if not logfile.exists():
            return JSONResponse({
                "summary": {
                    "total_requests": 0,
                    "dxf_files": 0,
                    "pdf_files": 0,
                    "bulk_executions": 0,
                    "server_restarts": 0,
                    "errors": 0
                },
                "file_generations": [],
                "single_dxf_executions": [],
                "bulk_executions": []
            })
        
        # Read log file
        with open(logfile, 'r', encoding='utf-8', errors='ignore') as f:
            log_lines = f.readlines()
        
        # Initialize tracking structures
        counters = {
            "total_requests": 0,
            "dxf_files": 0,
            "pdf_files": 0,
            "bulk_executions": 0,
            "server_restarts": 0,
            "errors": 0
        }
        
        single_dxf_sessions = {}
        bulk_sessions = {}
        all_dxf_files = []
        
        # Parse log lines
        for line in log_lines:
            try:
                # Count server restarts and errors
                if "Started server process" in line:
                    counters["server_restarts"] += 1
                
                if " ERROR " in line and "uvicorn.error" not in line:
                    counters["errors"] += 1
                
                # Parse JSON log entries
                log_entry = parse_json_log_entry(line)
                if log_entry:
                    event = log_entry.get("event")
                    
                    if event == "request.start":
                        process_request_start(log_entry, line, single_dxf_sessions, 
                                            bulk_sessions, counters)
                    elif event == "request.finish":
                        process_request_finish(log_entry, line, single_dxf_sessions, 
                                             bulk_sessions)
                
                # Parse file generation messages
                if "DXF file" in line and "created successfully" in line:
                    process_dxf_generation(line, single_dxf_sessions, all_dxf_files, counters)
                
                if "Response logged to:" in line and ".dxf_response.json" in line:
                    process_response_log(line, all_dxf_files)
                
                if "PDF file" in line and "created successfully" in line:
                    process_pdf_generation(line, single_dxf_sessions, counters)
                
            except Exception:
                continue
        
        # Build execution lists
        single_executions, single_files_set = build_single_executions(single_dxf_sessions)
        
        associate_bulk_files(all_dxf_files, single_files_set, bulk_sessions)
        
        bulk_executions = build_bulk_executions(bulk_sessions)
        
        # Combine and sort executions
        all_executions = single_executions + bulk_executions
        all_executions.sort(key=lambda x: x["time"], reverse=True)
        
        return JSONResponse({
            "summary": {
                "total_requests": counters["total_requests"],
                "dxf_files": counters["dxf_files"],
                "pdf_files": counters["pdf_files"],
                "bulk_executions": counters["bulk_executions"],
                "server_restarts": max(0, counters["server_restarts"] - 1),
                "errors": counters["errors"]
            },
            "file_generations": [],  # Deprecated, kept for backwards compatibility
            "single_dxf_executions": all_executions[:50],
            "bulk_executions": []  # Deprecated, kept for backwards compatibility
        })
        
    except Exception as e:
        logger.error(f"Error parsing log file: {e}")
        raise HTTPException(status_code=500, detail=f"Error parsing log file: {str(e)}")



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    # Optional debugger attachment (set DEBUG_WAIT=1)
    if os.environ.get("DEBUG_WAIT") == "1":
        try:
            import debugpy
            logger.info("Waiting for debugger to attach on port 5678...")
            debugpy.listen(5678)
            debugpy.wait_for_client()
            logger.info("Debugger attached, continuing...")
        except Exception as e:
            logger.warning(f"debugpy not available or failed to start: {e}")

    import uvicorn
    uvicorn.run("fastapi_app.main:app", host="0.0.0.0", port=port, log_level="info")
