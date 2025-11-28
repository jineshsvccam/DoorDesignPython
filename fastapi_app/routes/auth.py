from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi_app.services.token_service import validate_token, mark_token_as_used, generate_tokens, get_unused_tokens, create_registration_links
from fastapi_app.services.user_service import save_registered_user, is_token_already_registered, get_registered_user
from fastapi_app.services.cookie_service import set_access_cookie, get_cookie_token, create_cookie_token
import os

router = APIRouter()

# Admin secret from environment variable
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production")


async def verify_authenticated_user(request: Request):
    """
    Dependency to check if user has valid cookie.
    Raises 401 if not authenticated.
    """
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

    # 4. Save user details (browser & IP)
    browser = request.headers.get("user-agent", "Unknown Browser")
    ip = request.client.host if request.client else "Unknown IP"
    save_registered_user(token, browser=browser, ip=ip)

    # 5. Mark token as used so no one else can reuse it
    mark_token_as_used(token)

    # 6. Create redirect response and set access cookie
    redirect_response = RedirectResponse(url="/", status_code=302)
    set_access_cookie(redirect_response, token)

    # 7. Return redirect with cookie
    return redirect_response


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
