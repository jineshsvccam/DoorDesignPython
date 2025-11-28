from fastapi import Response, Request
from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import os
import secrets

COOKIE_NAME = "door_access"
COOKIE_EXPIRY_DAYS = 3650   # 10 years (effectively permanent)

# Use environment variable for secret key, generate secure one if not set
SECRET_KEY = os.environ.get("COOKIE_SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("COOKIE_SECRET_KEY"):
    print(f"WARNING: Using auto-generated COOKIE_SECRET_KEY. Set COOKIE_SECRET_KEY environment variable for production.")
    print(f"Generated key: {SECRET_KEY}")

# Detect if running on HTTPS
IS_HTTPS = os.environ.get("HTTPS", "false").lower() in ("true", "1", "yes")


def create_cookie_token(token: str) -> str:
    """
    Create a hashed cookie token using token + secret key
    Prevents users from manually editing cookies.
    """
    raw = token + SECRET_KEY
    return hashlib.sha256(raw.encode()).hexdigest()


def set_access_cookie(response: Response, token: str):
    """
    Sets the cookie in the user's browser after registration.
    """
    hashed_cookie = create_cookie_token(token)
    
    expiry = datetime.now(timezone.utc) + timedelta(days=COOKIE_EXPIRY_DAYS)
    response.set_cookie(
        key=COOKIE_NAME,
        value=hashed_cookie,
        expires=expiry,
        httponly=True,
        secure=IS_HTTPS,        # Auto-detect based on environment
        samesite="lax",
    )
    return True


def get_cookie_token(request: Request) -> Optional[str]:
    """
    Get the cookie from the browser request
    """
    return request.cookies.get(COOKIE_NAME)


def validate_cookie(request: Request, token: str) -> bool:
    """
    Validates if the cookie matches the hashed value for the user token.
    """
    cookie_value = get_cookie_token(request)
    if not cookie_value:
        return False

    expected_hash = create_cookie_token(token)
    return cookie_value == expected_hash


def clear_cookie(response: Response):
    """
    Clear cookie (logout or invalid access)
    """
    response.delete_cookie(COOKIE_NAME)
