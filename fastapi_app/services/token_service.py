import os
import uuid
from datetime import datetime
from pathlib import Path

# Path to token storage file (absolute path)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TOKENS_FILE_PATH = DATA_DIR / "tokens.txt"


def generate_tokens(count=5):
    """
    Generate multiple one-time tokens and store them in tokens.txt
    Format: token | unused | created_date
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)  # Ensure folder exists

    with open(TOKENS_FILE_PATH, "a") as file:
        for _ in range(count):
            token = uuid.uuid4().hex[:12]  # Short unique token
            file.write(f"{token} | unused | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    return True


def get_unused_tokens():
    """
    Read all unused tokens from tokens.txt
    """
    if not os.path.exists(TOKENS_FILE_PATH):
        return []

    tokens = []
    with open(TOKENS_FILE_PATH, "r") as file:
        for line in file:
            parts = line.strip().split("|")
            if len(parts) >= 2 and parts[1].strip() == "unused":
                tokens.append(parts[0].strip())
    return tokens


def validate_token(token: str) -> bool:
    """
    Check if token exists and is unused
    """
    return token in get_unused_tokens()


def mark_token_as_used(token: str):
    """
    Mark a token as used (to block reuse)
    """
    if not os.path.exists(TOKENS_FILE_PATH):
        return

    updated_lines = []
    with open(TOKENS_FILE_PATH, "r") as file:
        for line in file:
            parts = line.strip().split("|")
            if parts[0].strip() == token:
                updated_lines.append(f"{token} | used | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            else:
                updated_lines.append(line)

    with open(TOKENS_FILE_PATH, "w") as file:
        file.writelines(updated_lines)


def create_registration_links(base_url: str):
    """
    Create full registration URLs for users.
    Example: http://43.204.19.13:8000/register?token=xyz123
    """
    urls = []
    for token in get_unused_tokens():
        urls.append(f"{base_url}/register?token={token}")
    return urls
