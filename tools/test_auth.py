"""
Test script for the authentication system.
Run this after starting the server to verify everything works.
"""

import requests
import os
import sys

# Configuration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change_me_in_production")


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_health_check():
    """Test basic health endpoint"""
    print_section("1. Testing Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print("✅ Health check passed")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_generate_tokens():
    """Test token generation"""
    print_section("2. Testing Token Generation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/generate-tokens",
            params={
                "admin_secret": ADMIN_SECRET,
                "count": 3
            }
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Generated {data['count']} tokens")
        print("\n📋 Registration Links:")
        for i, link in enumerate(data['registration_links'], 1):
            print(f"   {i}. {link}")
        
        return data['registration_links']
    except requests.exceptions.HTTPError as e:
        print(f"❌ Token generation failed: {e}")
        if e.response is not None:
            print(f"   Response: {e.response.text}")
        return []
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        return []


def test_list_tokens():
    """Test listing unused tokens"""
    print_section("3. Testing Token List")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/tokens",
            params={"admin_secret": ADMIN_SECRET}
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Found {data['unused_count']} unused tokens")
        if data['unused_count'] > 0:
            print("\n🔑 Unused tokens:")
            for token in data['tokens'][:5]:  # Show first 5
                print(f"   - {token}")
        
        return data['tokens']
    except Exception as e:
        print(f"❌ Token listing failed: {e}")
        return []


def test_registration(token):
    """Test user registration with a token"""
    print_section("4. Testing Registration Flow")
    
    try:
        # Create a session to maintain cookies
        session = requests.Session()
        
        response = session.get(
            f"{BASE_URL}/register",
            params={"token": token},
            allow_redirects=False
        )
        
        if response.status_code == 302:
            print(f"✅ Registration successful")
            print(f"   Redirect to: {response.headers.get('location')}")
            
            # Check if cookie was set
            if 'door_access' in session.cookies:
                print(f"   Cookie set: door_access")
                return session
            else:
                print(f"   ⚠️  No cookie found in response")
                return None
        else:
            print(f"❌ Registration failed with status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return None


def test_check_auth(session):
    """Test authentication check"""
    print_section("5. Testing Authentication Check")
    
    if not session:
        print("⚠️  Skipping - no session available")
        return
    
    try:
        response = session.get(f"{BASE_URL}/check-auth")
        response.raise_for_status()
        data = response.json()
        
        if data.get('authenticated'):
            print("✅ Authentication verified successfully")
        else:
            print("❌ Authentication check failed")
            
    except Exception as e:
        print(f"❌ Auth check failed: {e}")


def test_list_users():
    """Test listing registered users"""
    print_section("6. Testing User List")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/users",
            params={"admin_secret": ADMIN_SECRET}
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Found {data['user_count']} registered users")
        if data['user_count'] > 0:
            print("\n👥 Registered users:")
            for user in data['users'][:5]:  # Show first 5
                print(f"   - Token: {user['token'][:12]}...")
                print(f"     Status: {user['status']}")
                print(f"     Registered: {user['registered_date']}")
                print(f"     IP: {user['ip_address']}")
                print()
        
    except Exception as e:
        print(f"❌ User listing failed: {e}")


def test_invalid_admin_secret():
    """Test that invalid admin secret is rejected"""
    print_section("7. Testing Invalid Admin Secret")
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/generate-tokens",
            params={
                "admin_secret": "wrong_secret",
                "count": 1
            }
        )
        
        if response.status_code == 403:
            print("✅ Invalid admin secret correctly rejected")
        else:
            print(f"❌ Expected 403, got {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Test failed with exception: {e}")


def main():
    print("\n" + "="*60)
    print("  🔐 AUTHENTICATION SYSTEM TEST SUITE")
    print("="*60)
    print(f"\n🌐 Server: {BASE_URL}")
    print(f"🔑 Admin Secret: {'*' * len(ADMIN_SECRET)}")
    
    # Run tests
    if not test_health_check():
        print("\n❌ Server is not responding. Please start the server first.")
        sys.exit(1)
    
    # Generate tokens
    links = test_generate_tokens()
    
    # List tokens
    tokens = test_list_tokens()
    
    # Test registration if we have tokens
    session = None
    if tokens:
        print(f"\n💡 Using token: {tokens[0]}")
        session = test_registration(tokens[0])
        test_check_auth(session)
    else:
        print("\n⚠️  No tokens available for registration test")
    
    # List users
    test_list_users()
    
    # Test security
    test_invalid_admin_secret()
    
    # Summary
    print_section("✅ Test Summary")
    print("All basic tests completed!")
    print("\nNext steps:")
    print("1. Copy a registration link from above")
    print("2. Open it in your browser")
    print("3. Check that you're redirected to the home page")
    print("4. Try accessing the site again - you should stay logged in")
    
    if links:
        print(f"\n📋 Quick test link:")
        print(f"   {links[0]}")


if __name__ == "__main__":
    # Check if server URL is accessible
    try:
        requests.get(f"{BASE_URL}/health", timeout=2)
    except Exception:
        print(f"\n❌ Cannot connect to {BASE_URL}")
        print("   Make sure the server is running:")
        print("   python -m uvicorn fastapi_app.main:app --reload")
        sys.exit(1)
    
    main()
