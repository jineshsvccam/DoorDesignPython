"""
Manual test script for the JWT + FingerprintJS-style authentication flow.

Run after starting the server:
    python tools/test_auth.py
"""

import os
import sys
import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production")


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def test_health_check():
    print_section("1. Health Check")
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    response.raise_for_status()
    print(response.json())


def generate_tokens(count):
    print_section("2. Generate Activation Tokens")
    response = requests.post(
        f"{BASE_URL}/admin/generate-tokens",
        params={"admin_secret": ADMIN_SECRET, "count": count},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    print(f"Generated links: {data['count']}")
    return [link.rsplit("token=", 1)[1] for link in data["registration_links"]]


def activate_device(token, visitor_id):
    response = requests.get(
        f"{BASE_URL}/register",
        params={"token": token},
        allow_redirects=False,
        timeout=10,
    )
    if response.status_code != 302:
        raise RuntimeError(f"Registration URL failed: {response.status_code} {response.text[:200]}")

    response = requests.post(
        f"{BASE_URL}/auth/activate",
        json={
            "token": token,
            "visitor_id": visitor_id,
            "device_label": "manual test device",
            "device_type": "desktop",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    assert data["success"] is True
    assert data["token"]
    return data["token"]


def test_first_activation(token):
    print_section("3. First Activation + Device Registration")
    jwt_token = activate_device(token, f"manual-test-visitor-{token}")
    print("JWT issued")
    return jwt_token


def test_jwt_validation(jwt_token):
    print_section("4. JWT Validation")
    response = requests.get(
        f"{BASE_URL}/check-auth",
        headers={"Authorization": f"Bearer {jwt_token}"},
        timeout=10,
    )
    response.raise_for_status()
    print(response.json())
    assert response.json().get("authenticated") is True


def test_device_recovery(visitor_id):
    print_section("5. Device Recovery")
    response = requests.post(
        f"{BASE_URL}/auth/recover",
        json={"visitor_id": visitor_id},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    assert data["success"] is True
    assert data["token"]
    print("Recovery JWT issued")
    return data["token"]


def test_invalid_activation_token():
    print_section("6. Invalid Activation Token")
    response = requests.post(
        f"{BASE_URL}/auth/activate",
        json={"token": "invalid-token", "visitor_id": "manual-invalid-device"},
        timeout=10,
    )
    print(f"Status: {response.status_code}")
    assert response.status_code == 400


def list_devices():
    response = requests.get(
        f"{BASE_URL}/admin/devices",
        params={"admin_secret": ADMIN_SECRET},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["devices"]


def test_revoked_device(visitor_id):
    print_section("7. Revoked Device")
    devices = list_devices()
    active = [device for device in devices if device["status"] == "active"]
    if not active:
        print("No active device found to revoke; skipping")
        return

    device_id = active[0]["device_id"]
    response = requests.post(
        f"{BASE_URL}/admin/devices/{device_id}/revoke",
        params={"admin_secret": ADMIN_SECRET},
        timeout=10,
    )
    response.raise_for_status()

    response = requests.post(
        f"{BASE_URL}/auth/recover",
        json={"visitor_id": visitor_id},
        timeout=10,
    )
    print(f"Recovery after revoke status: {response.status_code}")
    assert response.status_code == 401


def test_device_limit(tokens):
    print_section("8. Device Limit")
    successes = 0
    for token in tokens:
        try:
            activate_device(token, f"manual-limit-visitor-{token}")
            successes += 1
        except requests.HTTPError as exc:
            print(f"Activation rejected with status {exc.response.status_code}")
            assert exc.response.status_code == 403
            break
    print(f"Additional successful activations: {successes}")


def main():
    print_section("JWT Device Auth Test Suite")
    print(f"Server: {BASE_URL}")

    test_health_check()
    tokens = generate_tokens(6)
    first_token = tokens[0]
    first_visitor_id = f"manual-test-visitor-{first_token}"

    jwt_token = test_first_activation(first_token)
    test_jwt_validation(jwt_token)
    recovered = test_device_recovery(first_visitor_id)
    test_jwt_validation(recovered)
    test_invalid_activation_token()
    test_device_limit(tokens[1:])
    test_revoked_device(first_visitor_id)

    print_section("Done")
    print("Manual auth tests completed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nTest failed: {exc}")
        sys.exit(1)
