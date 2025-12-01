import asyncio
import ipaddress
import json
import logging
import os
import re
import sys
import tempfile
import time
import traceback
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

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
from geometry.door_geometry import compute_door_geometry
from geometry.prepare_dimensions import prepare_dimensions

# Serve the frontend static files and allow CORS for external UI (optional)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Include auth routes
app.include_router(auth_router, tags=["Authentication"])

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

# Feature flags and configuration
FULL_BODY_LOGGING = str(os.environ.get("FULL_BODY_LOGGING", "true")).lower() in ("1", "true", "yes")
MAX_FULL_BODY_BYTES = int(os.environ.get("MAX_FULL_BODY_BYTES", "5242880"))  # 5MB default

def _is_textual_content_type(ct: str) -> bool:
    if not ct:
        return False
    ct = ct.lower()
    if ct.startswith("text/"):
        return True
    # treat common structured text types as textual
    if "json" in ct or "xml" in ct or "+json" in ct or "javascript" in ct or "yaml" in ct:
        return True
    return False


# IP whitelist configuration (ALLOWED_IPS="127.0.0.1,192.168.1.0/24")
ALLOWED_IPS = os.environ.get("ALLOWED_IPS", "").strip()
ALLOWED_NETWORKS = []
if ALLOWED_IPS:
    for token in ALLOWED_IPS.split(","):
        t = token.strip()
        if not t:
            continue
        try:
            net = ipaddress.ip_network(t, strict=False)
            ALLOWED_NETWORKS.append(net)
        except Exception:
            logger.warning("Ignored invalid ALLOWED_IPS entry: %s", t)

# Authentication configuration
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
PUBLIC_PATHS = {
    "/static", "/register", "/check-auth", 
    "/health", "/healthz", "/docs", "/openapi.json", "/redoc"
}


# IP whitelist middleware: short-circuit requests from non-whitelisted IPs
@app.middleware("http")
async def ip_whitelist_middleware(request: StarletteRequest, call_next):
    # If no networks configured, allow all
    if not ALLOWED_NETWORKS:
        return await call_next(request)

    # determine client IP (prefer X-Forwarded-For)
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        client_ip = xff.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None

    allowed = False
    try:
        if client_ip:
            ipaddr = ipaddress.ip_address(client_ip)
            for net in ALLOWED_NETWORKS:
                if ipaddr in net:
                    allowed = True
                    break
    except Exception:
        allowed = False

    if not allowed:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        logger.warning(json.dumps({
            "event": "request.denied",
            "request_id": request_id,
            "client_ip": client_ip,
            "path": str(request.url),
        }))
        return JSONResponse({"detail": "IP not allowed", "request_id": request_id}, status_code=403, headers={"X-Request-ID": request_id})

    return await call_next(request)


# Authentication middleware: check cookies when REQUIRE_AUTH is enabled
@app.middleware("http")
async def auth_middleware(request: StarletteRequest, call_next):
    """Check authentication cookies when REQUIRE_AUTH=true, except for public paths."""
    if not REQUIRE_AUTH:
        return await call_next(request)
    
    # Check if path is public
    path = request.url.path
    is_public = False
    for public_path in PUBLIC_PATHS:
        if path == public_path or path.startswith(public_path + "/"):
            is_public = True
            break
    
    if is_public:
        return await call_next(request)
    
    # Verify authentication cookie
    try:
        from fastapi_app.services.cookie_service import get_cookie_token, create_cookie_token
        from fastapi_app.services.user_service import USERS_FILE_PATH
        
        cookie_token = get_cookie_token(request)
        if not cookie_token:
            # Return HTML forbidden page
            forbidden_path = Path(__file__).resolve().parents[1] / "frontend" / "forbidden.html"
            if forbidden_path.exists():
                return FileResponse(str(forbidden_path), status_code=401, media_type="text/html")
            return JSONResponse({"detail": "Authentication required", "redirect": "/register"}, status_code=401)
        
        # Validate cookie against registered users
        if not os.path.exists(USERS_FILE_PATH):
            forbidden_path = Path(__file__).resolve().parents[1] / "frontend" / "forbidden.html"
            if forbidden_path.exists():
                return FileResponse(str(forbidden_path), status_code=401, media_type="text/html")
            return JSONResponse({"detail": "Authentication required", "redirect": "/register"}, status_code=401)
        
        authenticated = False
        with open(USERS_FILE_PATH, "r") as file:
            for line in file:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    token = parts[0]
                    status = parts[1]
                    if status == "active":
                        expected_hash = create_cookie_token(token)
                        if cookie_token == expected_hash:
                            authenticated = True
                            break
        
        if not authenticated:
            forbidden_path = Path(__file__).resolve().parents[1] / "frontend" / "forbidden.html"
            if forbidden_path.exists():
                return FileResponse(str(forbidden_path), status_code=401, media_type="text/html")
            return JSONResponse({"detail": "Invalid authentication", "redirect": "/register"}, status_code=401)
        
    except Exception as e:
        logger.error(f"Auth middleware error: {e}")
        return JSONResponse({"detail": "Authentication error"}, status_code=401)
    
    return await call_next(request)


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
async def generate_dxf(
    file: UploadFile = File(...),
    sheet_size: Optional[str] = Form("1250x2500"),
):
    """Accept an uploaded Excel file and an optional sheet_size form field.

    `sheet_size` should be of the form WIDTHxHEIGHT (e.g. 1250x2500). If the
    value is missing or cannot be parsed, defaults of 1250x2500 are used.
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
        zip_path = generate_zip_from_excel(excel_path, sheet_width=width, sheet_height=height)
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


@app.exception_handler(Exception)
async def global_exception_handler(request: StarletteRequest, exc: Exception):
    """Log unhandled exceptions with traceback and return a JSON error including request_id.

    Also write a small per-request error file to fastapi_app/logs/errors/<request_id>.json.
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # determine client IP (prefer X-Forwarded-For)
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        client_ip = xff.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    tb = traceback.format_exc()
    # Log full exception and context
    logger.error(json.dumps({
        "event": "unhandled_exception",
        "request_id": request_id,
        "path": str(request.url),
        "client_ip": client_ip,
        "exception": str(exc),
        "traceback": tb,
    }))

    # write an atomic error file
    try:
        err_dir = logs_dir / "errors"
        err_dir.mkdir(parents=True, exist_ok=True)
        err_file = err_dir / f"{request_id}.json"
        payload = {
            "request_id": request_id,
            "path": str(request.url),
            "client_ip": client_ip,
            "exception": str(exc),
            "traceback": tb,
            "timestamp": time.time(),
        }
        tmp = err_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, err_file)
    except Exception:
        logger.exception("Failed to write error file for request %s", request_id)

    # Return a generic error response with the request id for correlation
    return JSONResponse({"detail": "Internal Server Error", "request_id": request_id}, status_code=500, headers={"X-Request-ID": request_id})


@app.middleware("http")
async def request_logging_middleware(request: StarletteRequest, call_next):
    """Log request start/finish, client IP, request id, body preview (skip multipart), and small response preview."""
    # correlation id
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    
    # Store request_id in context variable for use throughout the request
    request_id_ctx.set(request_id)

    # client IP: prefer X-Forwarded-For
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        client_ip = xff.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # user-ident (optional header)
    user_ident = request.headers.get("x-user-id") or "anonymous"

    # detect file upload by content-type
    content_type = request.headers.get("content-type", "")
    is_file_upload = content_type.startswith("multipart/form-data")

    start_time = time.time()

    # read body safely
    try:
        raw_body = await request.body()
    except Exception:
        raw_body = b""

    if is_file_upload:
        body_preview = "<file-upload>"
    else:
        try:
            body_text = raw_body.decode("utf-8", errors="replace")
            body_preview = body_text[:1024]
        except Exception:
            body_preview = "<binary>"

    # Decide whether to capture full bodies for request/response
    should_log_full_request = False
    ct = content_type or ""
    try:
        if FULL_BODY_LOGGING and not is_file_upload and _is_textual_content_type(ct) and len(raw_body) <= MAX_FULL_BODY_BYTES:
            should_log_full_request = True
    except Exception:
        should_log_full_request = False

    logger.info(json.dumps({
        "event": "request.start",
        "request_id": request_id,
        "method": request.method,
        "path": str(request.url),
        "client_ip": client_ip,
        "user": user_ident,
        "body_preview": body_preview,
    }))

    # recreate request for downstream since body was consumed
    async def receive():
        return {"type": "http.request", "body": raw_body}

    new_request = StarletteRequest(request.scope, receive)

    try:
        response = await call_next(new_request)
    except Exception as exc:
        # log the exception with traceback and re-raise
        logger.exception("Unhandled exception during request", exc_info=exc)
        raise

    process_time = time.time() - start_time

    # capture small response preview (be careful with streaming/binary)
    try:
        resp_body = b""
        async for chunk in response.body_iterator:
            resp_body += chunk
        # response content-type may be in headers
        resp_ct = response.headers.get("content-type", "")
        
        # Only create preview for text content types, not binary
        if _is_textual_content_type(resp_ct):
            resp_text = resp_body.decode("utf-8", errors="replace")[:1024]
        else:
            resp_text = f"<binary content: {resp_ct}, {len(resp_body)} bytes>"

        # Decide whether to capture full response body
        should_log_full_response = False
        try:
            if FULL_BODY_LOGGING and _is_textual_content_type(resp_ct) and len(resp_body) <= MAX_FULL_BODY_BYTES:
                should_log_full_response = True
        except Exception:
            should_log_full_response = False

        # rebuild response so the client receives body
        new_resp = StarletteResponse(content=resp_body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
        new_resp.headers["X-Request-ID"] = request_id

        logger.info(json.dumps({
            "event": "request.finish",
            "request_id": request_id,
            "status_code": response.status_code,
            "process_time_s": round(process_time, 4),
            "response_preview": resp_text,
        }))

        return new_resp
    except Exception:
        # fallback: cannot capture body (streaming). attach request id header and log status
        try:
            response.headers["X-Request-ID"] = request_id
        except Exception:
            pass
        logger.info(json.dumps({
            "event": "request.finish",
            "request_id": request_id,
            "status_code": getattr(response, "status_code", "unknown"),
            "process_time_s": round(process_time, 4),
            "response_preview": "<not-captured>",
        }))
        return response


@app.post("/generate-single-dxf/")
async def generate_single_dxf(params: DoorDXFRequest = Body(...), save_pdf: bool = Query(False, description="If true, also export and return a PDF instead of DXF")):
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
            bool(save_pdf),  # save_pdf
            current_request_id,  # request_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DXF generation failed: {e}")

    if not out_path.exists():
        # If DXF wasn't created, but PDF was requested maybe PDF exists — check that too
        pdf_path = out_path.with_suffix('.pdf')
        if save_pdf and pdf_path.exists():
            return FileResponse(
                path=str(pdf_path),
                filename=pdf_path.name,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'}
            )
        raise HTTPException(status_code=500, detail="DXF file was not created")

    # If PDF requested, prefer returning the PDF when available
    if save_pdf:
        pdf_path = out_path.with_suffix('.pdf')
        if pdf_path.exists():
            return FileResponse(
                path=str(pdf_path),
                filename=pdf_path.name,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'}
            )

    # Fallback: return DXF file
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
