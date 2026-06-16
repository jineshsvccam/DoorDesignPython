from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends, Body
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi_app.services.token_service import validate_token, mark_token_as_used, generate_tokens, get_unused_tokens, create_registration_links
from fastapi_app.services.user_service import (
    save_registered_user,
    is_token_already_registered,
    get_registered_user,
    register_device,
    find_device_by_visitor_id,
    find_device_by_id,
    update_device_last_seen,
    load_devices,
    revoke_device,
)
from fastapi_app.services.cookie_service import set_access_cookie, get_cookie_token, create_cookie_token
from fastapi_app.services.jwt_service import (
    create_access_token,
    verify_access_token,
    hash_visitor_id,
    JWT_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_SECONDS,
)
import os
from pathlib import Path

router = APIRouter()

# Admin secret from environment variable
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production")


def _get_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return None
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _set_jwt_cookie(response: Response, token: str):
    is_https = os.environ.get("HTTPS", "false").lower() in ("true", "1", "yes")
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_SECONDS,
        httponly=True,
        secure=is_https,
        samesite="lax",
    )


def _issue_token_response(device):
    token = create_access_token(device["device_id"], device["visitor_id_hash"])
    response = JSONResponse({"success": True, "token": token})
    _set_jwt_cookie(response, token)
    return response


def _forbidden_response():
    forbidden_path = Path(__file__).resolve().parents[2] / "frontend" / "forbidden.html"
    if forbidden_path.exists():
        return HTMLResponse(forbidden_path.read_text(encoding="utf-8"), status_code=401)
    return JSONResponse({"detail": "Device is not registered"}, status_code=401)


async def verify_authenticated_user(request: Request):
    """
    Dependency to check if user has valid JWT or legacy cookie.
    Raises 401 if not authenticated.
    """
    jwt_token = _get_bearer_token(request) or request.cookies.get(JWT_COOKIE_NAME)
    if jwt_token:
        payload = verify_access_token(jwt_token)
        if payload:
            device = find_device_by_id(payload["sub"])
            if device and device.get("status") == "active":
                return True

    cookie_token = get_cookie_token(request)
    if not cookie_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get all registered users and verify cookie matches
    from fastapi_app.services.user_service import USERS_FILE_PATH
    if not os.path.exists(USERS_FILE_PATH):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Validate cookie against any registered user token
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
        raise HTTPException(status_code=401, detail="Invalid authentication")
    
    return True


@router.get("/register")
async def register_user(request: Request, response: Response, token: Optional[str] = None):
    """
    Registration endpoint using one-time token.
    Example: http://43.204.19.13:8000/register?token=abc123xyz
    """

    # 1. Token missing in URL
    if not token:
        return HTMLResponse(
            "<h3>❌ Invalid Registration Link</h3><p>No token provided.</p>",
            status_code=400
        )

    # 2. Check token validity: Not expired, not used before
    if not validate_token(token):
        return HTMLResponse(
            "<h3>❌ Invalid or Expired Link</h3><p>This link cannot be used.</p>",
            status_code=400
        )

    # 3. If user already registered with this token → reject
    if is_token_already_registered(token):
        return HTMLResponse(
            "<h3>⚠️ This link has already been used.</h3><p>You are already registered.</p>",
            status_code=400
        )

    # 4. Keep activation URLs, but let the browser complete device registration
    # with FingerprintJS. /static is public, so first-time devices can load it.
    return RedirectResponse(url=f"/static/index.html?activation_token={token}", status_code=302)


@router.post("/auth/activate")
async def activate_device(request: Request, payload: dict = Body(...)):
    token = str(payload.get("token") or "").strip()
    visitor_id = str(payload.get("visitor_id") or "").strip()
    device_label = str(payload.get("device_label") or "").strip()
    device_type = str(payload.get("device_type") or "").strip().lower()

    if not token or not visitor_id:
        raise HTTPException(status_code=400, detail="token and visitor_id are required")
    if device_type not in ("", "mobile", "desktop"):
        raise HTTPException(status_code=400, detail="device_type must be mobile or desktop")

    if not validate_token(token):
        raise HTTPException(status_code=400, detail="Invalid or expired activation token")

    browser = request.headers.get("user-agent", "Unknown Browser")
    ip = request.client.host if request.client else "Unknown IP"
    device, error = register_device(
        visitor_id,
        user_agent=browser,
        device_label=device_label,
        ip=ip,
        device_type=device_type,
    )
    if error:
        raise HTTPException(status_code=403, detail=error)

    # Preserve the existing users.txt registration history for admin compatibility.
    save_registered_user(token, browser=browser, ip=ip)
    mark_token_as_used(token)

    return _issue_token_response(device)


@router.post("/auth/recover")
async def recover_device(payload: dict = Body(...)):
    visitor_id = str(payload.get("visitor_id") or "").strip()
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id is required")

    device = find_device_by_visitor_id(visitor_id)
    if not device or device.get("status") != "active":
        return _forbidden_response()

    update_device_last_seen(device["device_id"])
    return _issue_token_response(device)


@router.post("/admin/generate-tokens")
async def admin_generate_tokens(
    admin_secret: str,
    count: int = 5
):
    """
    Admin endpoint to generate registration tokens.
    Requires ADMIN_SECRET from environment.
    Example: POST /admin/generate-tokens?admin_secret=YOUR_SECRET&count=5
    """
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    if count < 1 or count > 50:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 50")
    
    # Generate tokens
    generate_tokens(count)
    
    # Get the base URL from environment or use default
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    links = create_registration_links(base_url)
    
    return JSONResponse({
        "success": True,
        "count": len(links),
        "registration_links": links
    })


@router.get("/admin/tokens")
async def admin_list_tokens(admin_secret: str):
    """
    Admin endpoint to list all unused tokens.
    Example: GET /admin/tokens?admin_secret=YOUR_SECRET
    """
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    unused = get_unused_tokens()
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    links = [f"{base_url}/register?token={t}" for t in unused]
    
    return JSONResponse({
        "success": True,
        "unused_count": len(unused),
        "tokens": unused,
        "registration_links": links
    })


@router.get("/admin/users")
async def admin_list_users(admin_secret: str):
    """
    Admin endpoint to list all registered users.
    Example: GET /admin/users?admin_secret=YOUR_SECRET
    """
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    from fastapi_app.services.user_service import USERS_FILE_PATH
    
    if not os.path.exists(USERS_FILE_PATH):
        return JSONResponse({"success": True, "users": []})
    
    users = []
    with open(USERS_FILE_PATH, "r") as file:
        for line in file:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                users.append({
                    "token": parts[0],
                    "status": parts[1],
                    "registered_date": parts[2],
                    "browser": parts[3] if len(parts) > 3 else "",
                    "ip_address": parts[4] if len(parts) > 4 else ""
                })
    
    return JSONResponse({
        "success": True,
        "user_count": len(users),
        "users": users
    })


@router.get("/admin/devices")
async def admin_list_devices(admin_secret: str):
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    devices = load_devices().get("devices", [])
    safe_devices = []
    for device in devices:
        safe_devices.append({
            "device_id": device.get("device_id"),
            "status": device.get("status"),
            "registered_at": device.get("registered_at"),
            "last_seen_at": device.get("last_seen_at"),
            "user_agent": device.get("user_agent"),
            "ip_address": device.get("ip_address"),
            "device_label": device.get("device_label"),
            "device_type": device.get("device_type") or "desktop",
            "visitor_id_hash": (device.get("visitor_id_hash") or "")[:12] + "...",
        })

    return JSONResponse({
        "success": True,
        "device_count": len(safe_devices),
        "devices": safe_devices,
    })


@router.post("/admin/devices/{device_id}/revoke")
async def admin_revoke_device(device_id: str, admin_secret: str):
    if admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    if not revoke_device(device_id):
        raise HTTPException(status_code=404, detail="Device not found")

    return JSONResponse({"success": True, "device_id": device_id, "status": "revoked"})


@router.get("/check-auth")
async def check_auth_status(request: Request):
    """
    Check if the current user is authenticated.
    Returns authentication status.
    """
    try:
        await verify_authenticated_user(request)
        return JSONResponse({"authenticated": True})
    except HTTPException:
        return JSONResponse({"authenticated": False})
