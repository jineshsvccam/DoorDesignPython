"""
FastAPI middleware for IP whitelisting, authentication, and request logging.
"""

import ipaddress
import json
import logging
import os
import time
import traceback
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

# These will be initialized by init_middleware()
logger: logging.Logger
logs_dir: Path
request_id_ctx: ContextVar[Optional[str]]

# IP whitelist configuration (ALLOWED_IPS="127.0.0.1,192.168.1.0/24")
ALLOWED_IPS = os.environ.get("ALLOWED_IPS", "").strip()
ALLOWED_NETWORKS = []

# Authentication configuration
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
PUBLIC_PATHS = {
    "/", "/logs", "/static", "/favicon.ico", "/register", "/auth/activate", "/auth/recover", "/check-auth",
    "/health", "/healthz", "/docs", "/openapi.json", "/redoc"
}

# Feature flags for request logging
FULL_BODY_LOGGING = str(os.environ.get("FULL_BODY_LOGGING", "true")).lower() in ("1", "true", "yes")
MAX_FULL_BODY_BYTES = int(os.environ.get("MAX_FULL_BODY_BYTES", "5242880"))  # 5MB default


def init_middleware(app_logger: logging.Logger, app_logs_dir: Path, app_request_id_ctx: ContextVar[Optional[str]]):
    """Initialize middleware with logger and context from main app."""
    global logger, logs_dir, request_id_ctx, ALLOWED_NETWORKS
    logger = app_logger
    logs_dir = app_logs_dir
    request_id_ctx = app_request_id_ctx
    
    # Parse IP whitelist configuration
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


def _is_textual_content_type(ct: str) -> bool:
    """Check if content type is textual (for logging purposes)."""
    if not ct:
        return False
    ct = ct.lower()
    if ct.startswith("text/"):
        return True
    # treat common structured text types as textual
    if "json" in ct or "xml" in ct or "+json" in ct or "javascript" in ct or "yaml" in ct:
        return True
    return False


async def ip_whitelist_middleware(request: StarletteRequest, call_next):
    """IP whitelist middleware: short-circuit requests from non-whitelisted IPs."""
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


async def auth_middleware(request: StarletteRequest, call_next):
    """Check JWT first, then legacy auth cookies when REQUIRE_AUTH=true."""
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
    
    # Verify JWT from Authorization header or navigation fallback cookie.
    try:
        from fastapi_app.services.jwt_service import verify_access_token, JWT_COOKIE_NAME
        from fastapi_app.services.user_service import find_device_by_id

        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        jwt_token = None
        if auth_header:
            scheme, _, token = auth_header.partition(" ")
            if scheme.lower() == "bearer" and token:
                jwt_token = token.strip()
        if not jwt_token:
            jwt_token = request.cookies.get(JWT_COOKIE_NAME)

        if jwt_token:
            payload = verify_access_token(jwt_token)
            if payload:
                device = find_device_by_id(payload["sub"])
                if device and device.get("status") == "active":
                    request.scope["auth_device_id"] = payload["sub"]
                    return await call_next(request)
    except Exception as e:
        logger.error(f"JWT auth middleware error: {e}")

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

    # Extract authenticated device/user from JWT or legacy cookie
    user_ident = "anonymous"
    try:
        from fastapi_app.services.jwt_service import verify_access_token, JWT_COOKIE_NAME
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        jwt_token = None
        if auth_header:
            scheme, _, token = auth_header.partition(" ")
            if scheme.lower() == "bearer" and token:
                jwt_token = token.strip()
        if not jwt_token:
            jwt_token = request.cookies.get(JWT_COOKIE_NAME)
        if jwt_token:
            payload = verify_access_token(jwt_token)
            if payload:
                user_ident = str(payload.get("sub", "anonymous"))[:8]
    except Exception:
        pass

    if user_ident == "anonymous":
        try:
            from fastapi_app.services.cookie_service import get_cookie_token, create_cookie_token
            from fastapi_app.services.user_service import USERS_FILE_PATH
            
            cookie_token = get_cookie_token(request)
            if cookie_token and os.path.exists(USERS_FILE_PATH):
                with open(USERS_FILE_PATH, "r") as file:
                    for line in file:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 2:
                            token = parts[0]
                            status = parts[1]
                            if status == "active":
                                expected_hash = create_cookie_token(token)
                                if cookie_token == expected_hash:
                                    # Use first 8 chars of token as user identifier
                                    user_ident = token[:8] if len(token) >= 8 else token
                                    break
        except Exception:
            pass  # Fallback to "anonymous" on any error

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
