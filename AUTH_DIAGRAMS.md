# 🔐 Authentication System - Flow Diagrams

## 1. Registration Flow

```
┌─────────────┐
│   Admin     │
└──────┬──────┘
       │
       │ 1. Generate tokens
       ▼
┌─────────────────────────────────┐
│  POST /admin/generate-tokens    │
│  ?admin_secret=XXX&count=5      │
└──────┬──────────────────────────┘
       │
       │ 2. Create tokens
       ▼
┌─────────────────────────────────┐
│  Token Service                  │
│  - Generate UUID tokens         │
│  - Save to tokens.txt           │
│  - Create registration URLs     │
└──────┬──────────────────────────┘
       │
       │ 3. Share link
       ▼
   User receives:
   http://domain.com/register?token=abc123xyz456
       │
       │ 4. User clicks link
       ▼
┌─────────────────────────────────┐
│  GET /register?token=XXX        │
└──────┬──────────────────────────┘
       │
       │ 5. Validate token
       ▼
┌─────────────────────────────────┐
│  Token Service                  │
│  ✓ Token exists?                │
│  ✓ Token unused?                │
│  ✓ Not already registered?      │
└──────┬──────────────────────────┘
       │
       │ 6. Save user
       ▼
┌─────────────────────────────────┐
│  User Service                   │
│  - Save to users.txt            │
│  - Record: browser, IP, date    │
│  - Mark token as "used"         │
└──────┬──────────────────────────┘
       │
       │ 7. Set cookie
       ▼
┌─────────────────────────────────┐
│  Cookie Service                 │
│  - Hash: SHA256(token+secret)   │
│  - Set cookie (30 days)         │
│  - HttpOnly, SameSite=Lax       │
└──────┬──────────────────────────┘
       │
       │ 8. Redirect
       ▼
┌─────────────────────────────────┐
│  User sees home page (/)        │
│  ✅ Authenticated!               │
└─────────────────────────────────┘
```

---

## 2. Subsequent Access Flow

```
┌─────────────┐
│    User     │
│ (has cookie)│
└──────┬──────┘
       │
       │ 1. Visit website
       ▼
┌─────────────────────────────────┐
│  GET /generate-single-dxf/      │
│  Cookie: door_access=hash...    │
└──────┬──────────────────────────┘
       │
       │ 2. Check REQUIRE_AUTH
       ▼
┌─────────────────────────────────┐
│  Auth Middleware                │
│  REQUIRE_AUTH enabled?          │
└──────┬──────────────────────────┘
       │
       │ YES → 3. Check path
       ▼
┌─────────────────────────────────┐
│  Is path public?                │
│  (/register, /health, etc.)     │
└──────┬──────────────────────────┘
       │
       │ NO → 4. Verify cookie
       ▼
┌─────────────────────────────────┐
│  Cookie Service                 │
│  - Extract cookie from request  │
│  - Read users.txt               │
│  - Check hash matches any user  │
│  - Verify status = "active"     │
└──────┬──────────────────────────┘
       │
       ├──► ✅ Valid → Allow request
       │
       └──► ❌ Invalid → 401 Unauthorized
```

---

## 3. Admin Management Flow

```
┌─────────────┐
│   Admin     │
└──────┬──────┘
       │
       ├───────────────────────────────────────┐
       │                                       │
       │ List Users                            │ Block User
       ▼                                       ▼
┌──────────────────────┐            ┌──────────────────────┐
│ GET /admin/users     │            │ Edit users.txt       │
│ ?admin_secret=XXX    │            │ Change: active →     │
└──────┬───────────────┘            │         blocked      │
       │                            └──────┬───────────────┘
       │ Returns:                          │
       │ - Token                           │ User cookie now
       │ - Status                          │ invalid on next
       │ - Date                            │ request
       │ - IP
       │ - Browser
       ▼
   Admin sees all
   registered users

┌─────────────┐
│   Admin     │
└──────┬──────┘
       │
       │ Generate Tokens
       ▼
┌──────────────────────┐
│ POST /admin/         │
│ generate-tokens      │
│ ?admin_secret=XXX    │
│ &count=5             │
└──────┬───────────────┘
       │
       │ Returns:
       │ - registration_links[]
       ▼
   Admin shares links
   with users
```

---

## 4. CLI Tool Flow

```
┌─────────────┐
│   Admin     │
└──────┬──────┘
       │
       │ python tools/auth_admin.py generate 5
       ▼
┌─────────────────────────────────┐
│  CLI Tool                       │
│  - Reads token_service          │
│  - Generates tokens directly    │
│  - Writes to tokens.txt         │
│  - Displays links               │
└─────────────────────────────────┘

┌─────────────┐
│   Admin     │
└──────┬──────┘
       │
       │ python tools/auth_admin.py users
       ▼
┌─────────────────────────────────┐
│  CLI Tool                       │
│  - Reads users.txt              │
│  - Displays formatted list      │
│  - Shows status, IP, browser    │
└─────────────────────────────────┘

┌─────────────┐
│   Admin     │
└──────┬──────┘
       │
       │ python tools/auth_admin.py block abc123
       ▼
┌─────────────────────────────────┐
│  CLI Tool                       │
│  - Reads users.txt              │
│  - Updates status to "blocked"  │
│  - Saves changes                │
└─────────────────────────────────┘
```

---

## 5. Data Storage Structure

```
fastapi_app/data/
│
├── tokens.txt
│   ├─► abc123xyz456 | unused | 2025-11-28 10:00:00
│   ├─► def789uvw012 | used | 2025-11-28 11:30:00
│   └─► ghi345rst678 | used | 2025-11-28 12:15:00
│
└── users.txt
    ├─► def789uvw012 | active | 2025-11-28 11:30:15 | Mozilla/5.0... | 192.168.1.100
    └─► ghi345rst678 | blocked | 2025-11-28 12:15:30 | Chrome/120... | 192.168.1.101

Flow:
1. Token created → tokens.txt (unused)
2. User registers → token marked "used" + user added to users.txt
3. Admin blocks → user status changed to "blocked"
```

---

## 6. Security Architecture

```
┌─────────────────────────────────┐
│  Environment Variables          │
│  (.env file)                    │
│                                 │
│  ADMIN_SECRET=random32chars     │
│  COOKIE_SECRET_KEY=random64hex  │
└──────┬──────────────────────────┘
       │
       ├───────────────────┬────────────────────┐
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│ Admin API    │  │ Cookie Hashing  │  │ Token Gen    │
│ Protection   │  │ SHA256(token+   │  │ UUID4        │
│              │  │ secret)         │  │ 12 chars     │
└──────────────┘  └─────────────────┘  └──────────────┘

Cookie Security:
┌─────────────────────────────────┐
│  Set-Cookie: door_access=hash   │
│  - HttpOnly (no JS access)      │
│  - SameSite=Lax (CSRF protect)  │
│  - Secure (if HTTPS=true)       │
│  - Expires: 30 days             │
└─────────────────────────────────┘
```

---

## 7. Request Flow with REQUIRE_AUTH=true

```
Request → IP Whitelist → Auth Check → Logging → Handler
  │           │             │           │         │
  │           │             │           │         └─► Response
  │           │             │           └─► Log request/response
  │           │             └─► Cookie valid? → ✅/❌
  │           └─► IP allowed? → ✅/❌
  └─► Client IP

Public paths (always allowed):
- /
- /static/*
- /register
- /check-auth
- /health
- /healthz
- /docs
- /openapi.json
- /redoc
```

---

## 8. Complete System Diagram

```
                    ┌─────────────────────────┐
                    │   Admin/Developer       │
                    └────────┬────────────────┘
                             │
                 ┌───────────┼───────────┐
                 │                       │
                 ▼                       ▼
        ┌────────────────┐      ┌────────────────┐
        │  CLI Tool      │      │  Admin API     │
        │  auth_admin.py │      │  /admin/*      │
        └────────┬───────┘      └────────┬───────┘
                 │                       │
                 └───────────┬───────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Token Service  │
                    │  User Service   │
                    │  Cookie Service │
                    └────────┬────────┘
                             │
                     ┌───────┼───────┐
                     │               │
                     ▼               ▼
            ┌─────────────┐  ┌─────────────┐
            │ tokens.txt  │  │ users.txt   │
            └─────────────┘  └─────────────┘
                     │               │
                     └───────┬───────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Registration   │
                    │  /register      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  End User       │
                    │  (Browser)      │
                    │  + Cookie       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Protected      │
                    │  Endpoints      │
                    │  (DXF API)      │
                    └─────────────────┘
```

---

## Legend

- `┌─┐` = Component/Service
- `│` = Data flow
- `▼` = Direction of flow
- `✅` = Allowed/Success
- `❌` = Denied/Failure
- `→` = Leads to
