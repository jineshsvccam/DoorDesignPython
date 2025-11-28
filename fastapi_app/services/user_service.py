import os
from datetime import datetime
from pathlib import Path

# Path to users storage file (absolute path)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
USERS_FILE_PATH = DATA_DIR / "users.txt"


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
