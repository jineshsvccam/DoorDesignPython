import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional, Dict, Any


JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "door_jwt"
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.environ.get("JWT_EXPIRE_SECONDS", str(30 * 24 * 60 * 60)))

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or os.environ.get("COOKIE_SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("JWT_SECRET_KEY") and not os.environ.get("COOKIE_SECRET_KEY"):
    print("WARNING: Using auto-generated JWT_SECRET_KEY. Set JWT_SECRET_KEY for production.")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_visitor_id(visitor_id: str) -> str:
    return hashlib.sha256(visitor_id.encode("utf-8")).hexdigest()


def create_access_token(device_id: str, visitor_id_hash: str) -> str:
    now = int(time.time())
    header = {"typ": "JWT", "alg": JWT_ALGORITHM}
    payload = {
        "sub": device_id,
        "visitor_id_hash": visitor_id_hash,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_SECONDS,
    }

    signing_input = ".".join([
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    signature = hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            JWT_SECRET_KEY.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        provided_signature = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return None

        header = json.loads(_b64url_decode(header_part))
        if header.get("alg") != JWT_ALGORITHM:
            return None

        payload = json.loads(_b64url_decode(payload_part))
        exp = int(payload.get("exp", 0))
        if exp < int(time.time()):
            return None

        if not payload.get("sub") or not payload.get("visitor_id_hash"):
            return None

        return payload
    except Exception:
        return None
