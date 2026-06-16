"""
Admin CLI tool for managing authentication tokens and users.
Usage: python tools/auth_admin.py [command]
"""

import sys
import os
from pathlib import Path
from typing import Union

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load .env file if it exists
env_file = Path(__file__).resolve().parents[1] / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value

from fastapi_app.services.token_service import (
    generate_tokens, get_unused_tokens, create_registration_links,
    mark_token_as_used, TOKENS_FILE_PATH
)
from fastapi_app.services.user_service import (
    get_registered_user, activate_user, deactivate_user, USERS_FILE_PATH,
    load_devices, revoke_device
)


def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def cmd_generate(count: Union[int, str] = 5) -> None:
    """Generate new registration tokens"""
    print_header("🔑 Generate Registration Tokens")
    
    try:
        count_int = int(count)
        if count_int < 1 or count_int > 50:
            print("❌ Count must be between 1 and 50")
            return
    except ValueError:
        print("❌ Invalid count")
        return
    
    generate_tokens(count_int)
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    links = create_registration_links(base_url)
    
    print(f"✅ Generated {len(links)} registration links:\n")
    for i, link in enumerate(links, 1):
        print(f"{i}. {link}")
    
    print(f"\n📄 Tokens saved to: {TOKENS_FILE_PATH}")


def cmd_list_tokens():
    """List all unused tokens"""
    print_header("📋 Unused Tokens")
    
    tokens = get_unused_tokens()
    
    if not tokens:
        print("No unused tokens found.")
        print("Generate new tokens with: python tools/auth_admin.py generate 5")
        return
    
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    
    print(f"Found {len(tokens)} unused tokens:\n")
    for i, token in enumerate(tokens, 1):
        link = f"{base_url}/register?token={token}"
        print(f"{i}. Token: {token}")
        print(f"   Link:  {link}\n")


def cmd_list_users():
    """List all registered users"""
    print_header("👥 Registered Users")
    
    if not os.path.exists(USERS_FILE_PATH):
        print("No users registered yet.")
        return
    
    users = []
    with open(USERS_FILE_PATH, "r") as file:
        for line in file:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                users.append({
                    "token": parts[0],
                    "status": parts[1],
                    "registered_date": parts[2],
                    "browser": parts[3] if len(parts) > 3 else "N/A",
                    "ip_address": parts[4] if len(parts) > 4 else "N/A"
                })
    
    if not users:
        print("No users registered yet.")
        return
    
    print(f"Found {len(users)} registered users:\n")
    for i, user in enumerate(users, 1):
        status_icon = "✅" if user['status'] == 'active' else "🚫"
        print(f"{i}. {status_icon} Status: {user['status']}")
        print(f"   Token:      {user['token']}")
        print(f"   Registered: {user['registered_date']}")
        print(f"   IP:         {user['ip_address']}")
        print(f"   Browser:    {user['browser'][:60]}...")
        print()


def cmd_block_user(token):
    """Block a user by token"""
    print_header("🚫 Block User")
    
    if not token:
        print("❌ Please provide a token")
        print("Usage: python tools/auth_admin.py block TOKEN")
        return
    
    user = get_registered_user(token)
    if not user:
        print(f"❌ User with token '{token}' not found")
        return
    
    if user['status'] == 'blocked':
        print(f"⚠️  User already blocked")
        return
    
    deactivate_user(token)
    print(f"✅ User blocked successfully")
    print(f"   Token: {token}")
    print(f"   Previous status: {user['status']}")


def cmd_unblock_user(token):
    """Unblock a user by token"""
    print_header("✅ Unblock User")
    
    if not token:
        print("❌ Please provide a token")
        print("Usage: python tools/auth_admin.py unblock TOKEN")
        return
    
    user = get_registered_user(token)
    if not user:
        print(f"❌ User with token '{token}' not found")
        return
    
    if user['status'] == 'active':
        print(f"⚠️  User already active")
        return
    
    activate_user(token)
    print(f"✅ User unblocked successfully")
    print(f"   Token: {token}")
    print(f"   Previous status: {user['status']}")


def cmd_user_info(token):
    """Show detailed user information"""
    print_header("ℹ️  User Information")
    
    if not token:
        print("❌ Please provide a token")
        print("Usage: python tools/auth_admin.py info TOKEN")
        return
    
    user = get_registered_user(token)
    if not user:
        print(f"❌ User with token '{token}' not found")
        return
    
    status_icon = "✅" if user['status'] == 'active' else "🚫"
    print(f"{status_icon} Status:         {user['status']}")
    print(f"🔑 Token:          {user['token']}")
    print(f"📅 Registered:     {user['registered_date']}")
    print(f"🌐 IP Address:     {user['ip_address']}")
    print(f"🖥️  Browser:        {user['browser']}")


def cmd_stats():
    """Show authentication system statistics"""
    print_header("📊 Authentication Statistics")
    
    # Token stats
    unused_tokens = get_unused_tokens()
    total_tokens = 0
    used_tokens = 0
    
    if os.path.exists(TOKENS_FILE_PATH):
        with open(TOKENS_FILE_PATH, "r") as file:
            for line in file:
                total_tokens += 1
                if "| used |" in line:
                    used_tokens += 1
    
    # User stats
    total_users = 0
    active_users = 0
    blocked_users = 0
    
    if os.path.exists(USERS_FILE_PATH):
        with open(USERS_FILE_PATH, "r") as file:
            for line in file:
                total_users += 1
                if "| active |" in line:
                    active_users += 1
                elif "| blocked |" in line:
                    blocked_users += 1
    
    print(f"🔑 Tokens:")
    print(f"   Total:   {total_tokens}")
    print(f"   Used:    {used_tokens}")
    print(f"   Unused:  {len(unused_tokens)}")
    
    print(f"\n👥 Users:")
    print(f"   Total:   {total_users}")
    print(f"   Active:  {active_users}")
    print(f"   Blocked: {blocked_users}")
    
    print(f"\n📄 Files:")
    print(f"   Tokens:  {TOKENS_FILE_PATH}")
    print(f"   Users:   {USERS_FILE_PATH}")


def cmd_list_devices():
    """List registered FingerprintJS devices"""
    print_header("Registered Devices")

    devices = load_devices().get("devices", [])
    if not devices:
        print("No devices registered yet.")
        return

    for i, device in enumerate(devices, 1):
        visitor_hash = device.get("visitor_id_hash", "")
        print(f"{i}. Status:      {device.get('status', 'unknown')}")
        print(f"   Device ID:   {device.get('device_id', '')}")
        print(f"   Type:        {device.get('device_type', 'desktop')}")
        print(f"   Label:       {device.get('device_label', '') or 'N/A'}")
        print(f"   Registered:  {device.get('registered_at', '')}")
        print(f"   Last seen:   {device.get('last_seen_at', '')}")
        print(f"   IP:          {device.get('ip_address', '')}")
        print(f"   Visitor:     {visitor_hash[:12]}...")
        print(f"   Browser:     {(device.get('user_agent', '') or 'N/A')[:80]}")
        print()


def cmd_revoke_device(device_id):
    """Revoke a registered device by device_id"""
    print_header("Revoke Device")

    if not device_id:
        print("Please provide a device_id")
        print("Usage: python tools/auth_admin.py revoke-device DEVICE_ID")
        return

    if revoke_device(device_id):
        print("Device revoked successfully")
        print(f"Device ID: {device_id}")
    else:
        print(f"Device not found: {device_id}")


def cmd_help():
    """Show help message"""
    print_header("🔐 Auth Admin CLI - Help")
    
    commands = [
        ("generate [count]", "Generate registration tokens (default: 5)"),
        ("tokens", "List all unused tokens"),
        ("users", "List all registered users"),
        ("info TOKEN", "Show detailed user information"),
        ("block TOKEN", "Block a user by token"),
        ("unblock TOKEN", "Unblock a user by token"),
        ("stats", "Show authentication statistics"),
        ("devices", "List registered FingerprintJS devices"),
        ("revoke-device DEVICE_ID", "Revoke a registered device"),
        ("help", "Show this help message"),
    ]
    
    print("Available commands:\n")
    for cmd, desc in commands:
        print(f"  {cmd:20} - {desc}")
    
    print("\nExamples:")
    print("  python tools/auth_admin.py generate 10")
    print("  python tools/auth_admin.py tokens")
    print("  python tools/auth_admin.py users")
    print("  python tools/auth_admin.py block abc123xyz456")
    print("  python tools/auth_admin.py stats")
    
    print("\nEnvironment Variables:")
    print("  BASE_URL        - Base URL for registration links (default: http://localhost:8000)")
    print("  ADMIN_SECRET    - Secret for API admin endpoints")


def main():
    if len(sys.argv) < 2:
        cmd_help()
        return
    
    command = sys.argv[1].lower()
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    commands = {
        "generate": lambda: cmd_generate(args[0] if args else 5),
        "tokens": cmd_list_tokens,
        "users": cmd_list_users,
        "block": lambda: cmd_block_user(args[0] if args else None),
        "unblock": lambda: cmd_unblock_user(args[0] if args else None),
        "info": lambda: cmd_user_info(args[0] if args else None),
        "stats": cmd_stats,
        "devices": cmd_list_devices,
        "revoke-device": lambda: cmd_revoke_device(args[0] if args else None),
        "help": cmd_help,
    }
    
    if command not in commands:
        print(f"❌ Unknown command: {command}")
        print("Run 'python tools/auth_admin.py help' for available commands")
        return
    
    try:
        commands[command]()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
