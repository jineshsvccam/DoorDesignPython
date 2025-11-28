# 🔐 One-Time Token Authentication System

## Overview

This authentication system uses **one-time registration tokens** with **cookie-based access** for secure, password-free user management.

## How It Works

1. **Admin generates tokens** → Unique registration URLs are created
2. **User clicks their link** → Auto-registered with browser & IP tracking
3. **Cookie is set** → Stored securely in user's browser
4. **Subsequent visits** → Cookie automatically verified (no login needed)
5. **Token becomes invalid** → After first use, link cannot be reused

## Architecture

```
fastapi_app/
├── routes/
│   └── auth.py              # Registration & admin endpoints
├── services/
│   ├── token_service.py     # Token generation & validation
│   ├── user_service.py      # User registration & management
│   └── cookie_service.py    # Secure cookie handling
└── data/
    ├── tokens.txt           # Token storage (token | status | date)
    └── users.txt            # User records (token | status | date | browser | ip)
```

## Setup Instructions

### 1. Configure Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Required: Secret for admin endpoints (change this!)
ADMIN_SECRET=your-super-secret-admin-key-here

# Required: Cookie encryption key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
COOKIE_SECRET_KEY=your-64-character-hex-key-here

# Optional: Base URL for generating registration links
BASE_URL=http://43.204.19.13:8000

# Optional: Enable authentication requirement (default: false)
REQUIRE_AUTH=false

# Optional: Enable HTTPS cookie security (set to true if using HTTPS)
HTTPS=false
```

### 2. Generate Secure Keys

```powershell
# Generate COOKIE_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Generate ADMIN_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Start the Server

```powershell
python -m uvicorn fastapi_app.main:app --reload --host 0.0.0.0 --port 8000
```

## Admin API Usage

### 🔑 Generate Registration Tokens

**Endpoint:** `POST /admin/generate-tokens`

```bash
# Generate 5 registration links
curl -X POST "http://localhost:8000/admin/generate-tokens?admin_secret=YOUR_SECRET&count=5"
```

**Response:**

```json
{
  "success": true,
  "count": 5,
  "registration_links": [
    "http://localhost:8000/register?token=abc123xyz456",
    "http://localhost:8000/register?token=def789uvw012",
    ...
  ]
}
```

### 📋 List Unused Tokens

**Endpoint:** `GET /admin/tokens`

```bash
curl "http://localhost:8000/admin/tokens?admin_secret=YOUR_SECRET"
```

**Response:**

```json
{
  "success": true,
  "unused_count": 3,
  "tokens": ["abc123xyz456", "def789uvw012", ...],
  "registration_links": [...]
}
```

### 👥 List Registered Users

**Endpoint:** `GET /admin/users`

```bash
curl "http://localhost:8000/admin/users?admin_secret=YOUR_SECRET"
```

**Response:**

```json
{
  "success": true,
  "user_count": 2,
  "users": [
    {
      "token": "abc123xyz456",
      "status": "active",
      "registered_date": "2025-11-28 10:30:15",
      "browser": "Mozilla/5.0...",
      "ip_address": "192.168.1.100"
    }
  ]
}
```

## User Registration Flow

### Step 1: User Receives Link

Share the registration link with your user:

```
http://your-domain.com/register?token=abc123xyz456
```

### Step 2: User Clicks Link

- Token is validated (must be unused)
- User details (browser, IP) are saved to `users.txt`
- Token is marked as "used" in `tokens.txt`
- Secure cookie is set (expires in 30 days)
- User is redirected to home page (`/`)

### Step 3: Subsequent Visits

- User accesses the site normally
- Cookie is automatically checked
- Access granted if valid

## Authentication Enforcement

### Enable Authentication (Optional)

Set `REQUIRE_AUTH=true` to protect all endpoints except:

- `/` (home page)
- `/register` (registration)
- `/check-auth` (auth status check)
- `/health`, `/healthz` (health checks)
- `/docs`, `/openapi.json`, `/redoc` (API docs)
- `/static/*` (static files)

When enabled, all other endpoints require a valid authentication cookie.

### Check Authentication Status

**Endpoint:** `GET /check-auth`

```bash
curl -b cookies.txt "http://localhost:8000/check-auth"
```

**Response:**

```json
{ "authenticated": true }
```

## Security Features

### ✅ Implemented

- ✅ **One-time tokens** - Links cannot be reused after registration
- ✅ **Hashed cookies** - SHA256 hash prevents tampering
- ✅ **HttpOnly cookies** - Not accessible via JavaScript (XSS protection)
- ✅ **SameSite=Lax** - CSRF protection
- ✅ **Secure flag** - Auto-enabled for HTTPS environments
- ✅ **Environment-based secrets** - No hardcoded credentials
- ✅ **IP & browser tracking** - Audit trail for registrations
- ✅ **Admin-only token generation** - Protected by secret key

### ⚠️ Security Recommendations

1. **Always use HTTPS in production** - Set `HTTPS=true`
2. **Keep ADMIN_SECRET private** - Never commit to Git
3. **Rotate COOKIE_SECRET_KEY periodically** - Invalidates all sessions
4. **Use strong secrets** - 32+ character random strings
5. **Monitor users.txt** - Review registered users regularly
6. **Enable REQUIRE_AUTH** - When you want mandatory authentication
7. **Combine with IP whitelist** - Use `ALLOWED_IPS` for extra security

## File Storage Format

### tokens.txt

```
abc123xyz456 | unused | 2025-11-28 10:00:00
def789uvw012 | used | 2025-11-28 11:30:00
```

### users.txt

```
abc123xyz456 | active | 2025-11-28 11:30:15 | Mozilla/5.0... | 192.168.1.100
def789uvw012 | blocked | 2025-11-28 12:00:00 | Chrome/120... | 192.168.1.101
```

## User Management

### Block a User

Edit `users.txt` and change status from `active` to `blocked`:

```
abc123xyz456 | blocked | 2025-11-28 11:30:15 | Mozilla/5.0... | 192.168.1.100
```

The user's cookie will no longer grant access.

### Reactivate a User

Change status back to `active` in `users.txt`.

### Clear All Sessions

Delete the `users.txt` file or change the `COOKIE_SECRET_KEY` to invalidate all cookies.

## Troubleshooting

### Issue: "Invalid admin secret"

- Check that `ADMIN_SECRET` environment variable is set correctly
- Verify you're passing the correct secret in the query parameter

### Issue: "Authentication required"

- User needs to register using a valid token link
- Cookie may have expired (30 days default)
- User may have cleared browser cookies

### Issue: "This link has already been used"

- Token has been used by another user
- Generate a new token using `/admin/generate-tokens`

### Issue: Cookie not persisting

- Check browser allows cookies
- Verify `HTTPS=true` if using HTTPS
- Ensure domain matches (localhost vs 127.0.0.1)

## Integration Example

### Protect a Custom Endpoint

```python
from fastapi import Depends
from fastapi_app.routes.auth import verify_authenticated_user

@app.get("/protected-endpoint")
async def protected_route(
    authenticated: bool = Depends(verify_authenticated_user)
):
    return {"message": "You are authenticated!"}
```

### Frontend Cookie Check

```javascript
// Check if user is authenticated
fetch("/check-auth")
  .then((res) => res.json())
  .then((data) => {
    if (!data.authenticated) {
      window.location.href = "/register?token=YOUR_TOKEN";
    }
  });
```

## Testing

### Test Registration Flow

```powershell
# 1. Generate tokens
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/admin/generate-tokens?admin_secret=YOUR_SECRET&count=1"
$token = $response.registration_links[0]

# 2. Open registration link in browser
Start-Process $token

# 3. Check authentication
Invoke-RestMethod -Uri "http://localhost:8000/check-auth" -WebSession $session
```

## Production Deployment Checklist

- [ ] Set strong `ADMIN_SECRET` (32+ characters)
- [ ] Set strong `COOKIE_SECRET_KEY` (64 hex characters)
- [ ] Set `HTTPS=true` for production
- [ ] Set `BASE_URL` to your production domain
- [ ] Set `REQUIRE_AUTH=true` to enforce authentication
- [ ] Configure `ALLOWED_IPS` if using IP whitelist
- [ ] Do not commit `.env` file to version control
- [ ] Add `data/` directory to `.gitignore`
- [ ] Set up monitoring for `users.txt` and `tokens.txt`
- [ ] Configure log rotation for auth events

## API Reference Summary

| Endpoint                 | Method | Auth   | Description                      |
| ------------------------ | ------ | ------ | -------------------------------- |
| `/register`              | GET    | Public | User registration with token     |
| `/check-auth`            | GET    | Public | Check authentication status      |
| `/admin/generate-tokens` | POST   | Admin  | Generate new registration tokens |
| `/admin/tokens`          | GET    | Admin  | List unused tokens               |
| `/admin/users`           | GET    | Admin  | List registered users            |

## Support

For issues or questions:

1. Check environment variables are set correctly
2. Review `fastapi_app/logs/app.log` for errors
3. Verify `data/tokens.txt` and `data/users.txt` exist and are readable
4. Ensure file permissions allow read/write access
