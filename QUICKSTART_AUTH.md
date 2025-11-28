# 🚀 Quick Start Guide - Authentication System

## 5-Minute Setup

### 1. Generate Secrets

```powershell
# Generate secure keys
python -c "import secrets; print('ADMIN_SECRET=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('COOKIE_SECRET_KEY=' + secrets.token_hex(32))"
```

### 2. Create .env File

Create `.env` in the project root:

```bash
ADMIN_SECRET=your-generated-admin-secret-here
COOKIE_SECRET_KEY=your-generated-64-char-hex-key-here
BASE_URL=http://localhost:8000
REQUIRE_AUTH=false
```

### 3. Start Server

```powershell
python -m uvicorn fastapi_app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Generate Registration Links

**Option A: Using CLI Tool**

```powershell
python tools/auth_admin.py generate 3
```

**Option B: Using API**

```powershell
$secret = "your-admin-secret"
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/admin/generate-tokens?admin_secret=$secret&count=3"
$response.registration_links
```

### 5. Test Registration

Copy one of the generated links and open in browser:

```
http://localhost:8000/register?token=abc123xyz456
```

You should be:

1. Registered automatically
2. Redirected to home page
3. Have a cookie set (valid for 30 days)

### 6. Verify Setup

```powershell
# Run the test suite
python tools/test_auth.py

# Or check manually
python tools/auth_admin.py stats
```

---

## Common Commands

### Token Management

```powershell
# Generate tokens
python tools/auth_admin.py generate 10

# List unused tokens
python tools/auth_admin.py tokens

# Show statistics
python tools/auth_admin.py stats
```

### User Management

```powershell
# List registered users
python tools/auth_admin.py users

# Show user details
python tools/auth_admin.py info abc123xyz456

# Block a user
python tools/auth_admin.py block abc123xyz456

# Unblock a user
python tools/auth_admin.py unblock abc123xyz456
```

---

## Enable Authentication (Optional)

To require authentication for all endpoints:

1. Edit `.env`:

   ```bash
   REQUIRE_AUTH=true
   ```

2. Restart server

3. Now all endpoints except public paths require a valid cookie

---

## API Testing

```powershell
# Generate tokens via API
$secret = "your-admin-secret"
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/admin/generate-tokens?admin_secret=$secret&count=5"

# List users via API
Invoke-RestMethod -Uri "http://localhost:8000/admin/users?admin_secret=$secret"

# Check auth status
Invoke-RestMethod -Uri "http://localhost:8000/check-auth"
```

---

## Troubleshooting

### "Import error" when running CLI

```powershell
# Make sure you're in the project root
cd c:\Users\USER\source\repos\DoorDesignPython
python tools/auth_admin.py help
```

### "Invalid admin secret"

Check your `.env` file has the correct `ADMIN_SECRET` value.

### "Cookie not set"

- Check browser allows cookies
- Verify you're on the same domain (localhost vs 127.0.0.1)
- Check if `HTTPS=true` is set incorrectly for local dev

### Token link doesn't work

```powershell
# Verify token exists and is unused
python tools/auth_admin.py tokens
```

---

## Next Steps

- Read full documentation: `fastapi_app/AUTH_README.md`
- Set up production secrets before deploying
- Enable HTTPS and set `HTTPS=true` for production
- Consider enabling `REQUIRE_AUTH=true` for restricted access
- Monitor `fastapi_app/data/users.txt` for registrations

---

## Security Checklist

- [ ] Generated strong `ADMIN_SECRET`
- [ ] Generated strong `COOKIE_SECRET_KEY`
- [ ] Added `.env` to `.gitignore` ✅ (already done)
- [ ] Added `data/` to `.gitignore` ✅ (already done)
- [ ] Set `HTTPS=true` for production
- [ ] Set `BASE_URL` to production domain
- [ ] Never commit secrets to Git
- [ ] Keep admin secret private

---

**Need Help?** Run: `python tools/auth_admin.py help`
