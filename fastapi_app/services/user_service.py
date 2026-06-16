import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi_app.services.jwt_service import hash_visitor_id

# Path to users storage file (absolute path)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
USERS_FILE_PATH = DATA_DIR / "users.txt"
DEVICES_FILE_PATH = DATA_DIR / "devices.json"
MAX_DEVICES = 5


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def save_registered_user(token: str, browser: str = "", ip: str = ""):
    """
    Save user details after successful registration.
    Format: token | active | registered_date | browser | ip_address
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if is_token_already_registered(token):
        return False

    with open(USERS_FILE_PATH, "a") as file:
        file.write(f"{token} | active | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                   f"{browser} | {ip}\n")
    return True


def is_token_already_registered(token: str) -> bool:
    """
    Check if the token already exists in users.txt
    """
    if not os.path.exists(USERS_FILE_PATH):
        return False

    with open(USERS_FILE_PATH, "r") as file:
        for line in file:
            parts = line.strip().split("|")
            if parts and parts[0].strip() == token:
                return True
    return False


def get_registered_user(token: str):
    """
    Retrieve full user info by token.
    Returns a dict or None.
    """
    if not os.path.exists(USERS_FILE_PATH):
        return None

    with open(USERS_FILE_PATH, "r") as file:
        for line in file:
            parts = [p.strip() for p in line.split("|")]
            if parts[0] == token:
                return {
                    "token": parts[0],
                    "status": parts[1],
                    "registered_date": parts[2],
                    "browser": parts[3] if len(parts) > 3 else "",
                    "ip_address": parts[4] if len(parts) > 4 else ""
                }
    return None


def activate_user(token: str):
    """
    Change user status to active (in case you want to re-enable manually)
    """
    update_user_status(token, "active")


def deactivate_user(token: str):
    """
    Deactivate the user (in case you want to block them later)
    """
    update_user_status(token, "blocked")


def update_user_status(token: str, new_status: str):
    """
    Update the status of a user inside users.txt
    """
    if not os.path.exists(USERS_FILE_PATH):
        return

    updated_lines = []
    with open(USERS_FILE_PATH, "r") as file:
        for line in file:
            parts = [p.strip() for p in line.split("|")]
            if parts[0] == token:
                parts[1] = new_status
                updated_lines.append(" | ".join(parts) + "\n")
            else:
                updated_lines.append(line)

    with open(USERS_FILE_PATH, "w") as file:
        file.writelines(updated_lines)


def load_devices() -> Dict[str, Any]:
    """
    Load registered devices from devices.json.
    Format: {"devices": [...]}
    """
    if not os.path.exists(DEVICES_FILE_PATH):
        return {"devices": []}

    try:
        with open(DEVICES_FILE_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
            return {"devices": []}
        return data
    except Exception:
        return {"devices": []}


def save_devices(data: Dict[str, Any]):
    """
    Save devices.json atomically enough for this small single-instance app.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = DEVICES_FILE_PATH.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    os.replace(tmp_path, DEVICES_FILE_PATH)


def get_active_devices():
    data = load_devices()
    return [device for device in data["devices"] if device.get("status") == "active"]


def count_active_devices() -> int:
    return len(get_active_devices())


def find_device_by_visitor_id(visitor_id: str) -> Optional[Dict[str, Any]]:
    visitor_hash = hash_visitor_id(visitor_id)
    data = load_devices()
    for device in data["devices"]:
        if device.get("visitor_id_hash") == visitor_hash:
            return device
    return None


def find_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    data = load_devices()
    for device in data["devices"]:
        if device.get("device_id") == device_id:
            return device
    return None


def infer_device_type(user_agent: str = "") -> str:
    ua = (user_agent or "").lower()
    mobile_markers = ("mobile", "android", "iphone", "ipad", "ipod")
    return "mobile" if any(marker in ua for marker in mobile_markers) else "desktop"


def register_device(visitor_id: str, user_agent: str = "", device_label: str = "", ip: str = "", device_type: str = ""):
    """
    Register a FingerprintJS visitor ID as an active device.
    Returns (device, error_message).
    """
    visitor_hash = hash_visitor_id(visitor_id)
    data = load_devices()

    for device in data["devices"]:
        if device.get("visitor_id_hash") == visitor_hash:
            if device.get("status") != "active":
                return None, "Device is revoked"
            device["last_seen_at"] = _utc_now()
            device["device_type"] = device.get("device_type") or device_type or infer_device_type(user_agent)
            if device_label:
                device["device_label"] = device_label
            save_devices(data)
            return device, None

    active_count = len([device for device in data["devices"] if device.get("status") == "active"])
    if active_count >= MAX_DEVICES:
        return None, f"Maximum device limit of {MAX_DEVICES} reached"

    now = _utc_now()
    device = {
        "device_id": str(uuid.uuid4()),
        "visitor_id_hash": visitor_hash,
        "status": "active",
        "registered_at": now,
        "last_seen_at": now,
        "user_agent": user_agent,
        "ip_address": ip,
        "device_label": device_label or "",
        "device_type": device_type or infer_device_type(user_agent),
    }
    data["devices"].append(device)
    save_devices(data)
    return device, None


def update_device_last_seen(device_id: str):
    data = load_devices()
    for device in data["devices"]:
        if device.get("device_id") == device_id:
            device["last_seen_at"] = _utc_now()
            save_devices(data)
            return True
    return False


def revoke_device(device_id: str) -> bool:
    data = load_devices()
    for device in data["devices"]:
        if device.get("device_id") == device_id:
            device["status"] = "revoked"
            device["last_seen_at"] = _utc_now()
            save_devices(data)
            return True
    return False
