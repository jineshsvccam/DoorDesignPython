# 🚀 Production Deployment Guide

## Pre-Deployment Checklist

### 1. Security Configuration

```bash
# Generate production secrets
python -c "import secrets; print('ADMIN_SECRET=' + secrets.token_urlsafe(32))" >> .env
python -c "import secrets; print('COOKIE_SECRET_KEY=' + secrets.token_hex(32))" >> .env

# Set production values in .env
ADMIN_SECRET=<your-generated-secret>
COOKIE_SECRET_KEY=<your-generated-key>
BASE_URL=https://your-production-domain.com
HTTPS=true
REQUIRE_AUTH=true  # Enable if you want mandatory authentication
ALLOWED_IPS=       # Set if you want IP whitelist

# Secure the .env file (Linux/Unix)
chmod 600 .env

# Secure the .env file (Windows)
icacls .env /inheritance:r /grant:r "%USERNAME%:F"
```

### 2. File Permissions

```bash
# Ensure data directory is writable
mkdir -p fastapi_app/data
chmod 700 fastapi_app/data  # Owner only

# Ensure log directory is writable
mkdir -p fastapi_app/logs
chmod 755 fastapi_app/logs
```

### 3. Environment Variables

Production `.env` should contain:

```bash
# Required
ADMIN_SECRET=<strong-32-char-secret>
COOKIE_SECRET_KEY=<64-hex-char-key>
BASE_URL=https://your-domain.com

# Recommended
HTTPS=true
REQUIRE_AUTH=true
FULL_BODY_LOGGING=false  # Disable in production for performance
MAX_FULL_BODY_BYTES=1048576  # 1MB limit

# Optional security
ALLOWED_IPS=203.0.113.0/24,198.51.100.0/24  # Whitelist IPs
```

---

## Deployment Options

### Option 1: Direct with Uvicorn (Development/Testing)

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python -m uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8000
```

### Option 2: Production with Gunicorn + Uvicorn Workers

```bash
# Install gunicorn
pip install gunicorn uvicorn[standard]

# Run with multiple workers
gunicorn fastapi_app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log
```

### Option 3: Systemd Service (Linux)

Create `/etc/systemd/system/doordesign.service`:

```ini
[Unit]
Description=Door Design FastAPI Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/DoorDesignPython
Environment="PATH=/opt/DoorDesignPython/venv/bin"
EnvironmentFile=/opt/DoorDesignPython/.env
ExecStart=/opt/DoorDesignPython/venv/bin/gunicorn \
    fastapi_app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile /var/log/doordesign/access.log \
    --error-logfile /var/log/doordesign/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable doordesign
sudo systemctl start doordesign
sudo systemctl status doordesign
```

### Option 4: Docker Container

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p fastapi_app/data fastapi_app/logs output

# Expose port
EXPOSE 8000

# Run application
CMD ["gunicorn", "fastapi_app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120"]
```

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  doordesign:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./fastapi_app/data:/app/fastapi_app/data
      - ./fastapi_app/logs:/app/fastapi_app/logs
      - ./output:/app/output
    environment:
      - ADMIN_SECRET=${ADMIN_SECRET}
      - COOKIE_SECRET_KEY=${COOKIE_SECRET_KEY}
      - BASE_URL=${BASE_URL}
      - HTTPS=true
      - REQUIRE_AUTH=true
    restart: unless-stopped
```

Run with:

```bash
docker-compose up -d
```

---

## Reverse Proxy Configuration

### Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Client max body size (for large Excel uploads)
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running requests
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }

    # Static files
    location /static/ {
        alias /opt/DoorDesignPython/frontend/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Apache

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    Redirect permanent / https://your-domain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName your-domain.com

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/your-domain.crt
    SSLCertificateKeyFile /etc/ssl/private/your-domain.key

    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    # Set forwarded headers
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"

    # Increase timeout for long requests
    ProxyTimeout 300
</VirtualHost>
```

---

## Initial Setup After Deployment

### 1. Verify Server is Running

```bash
curl https://your-domain.com/health
# Expected: {"status":"ok","uptime_s":...}
```

### 2. Generate Initial Tokens

```bash
# Method A: Using API
curl -X POST "https://your-domain.com/admin/generate-tokens?admin_secret=YOUR_SECRET&count=10"

# Method B: Using CLI (if you have server access)
python tools/auth_admin.py generate 10
```

### 3. Distribute Registration Links

Share the generated links with your authorized users:

```
https://your-domain.com/register?token=abc123xyz456
```

### 4. Monitor Initial Registrations

```bash
# Watch registered users
python tools/auth_admin.py users

# Or via API
curl "https://your-domain.com/admin/users?admin_secret=YOUR_SECRET"
```

---

## Monitoring & Maintenance

### Log Locations

```bash
# Application logs
tail -f fastapi_app/logs/app.log

# Request logs (when FULL_BODY_LOGGING=true)
ls -lh fastapi_app/logs/requests/

# Error logs
ls -lh fastapi_app/logs/errors/

# Access logs (if using Gunicorn/Nginx)
tail -f /var/log/nginx/access.log
```

### Regular Maintenance Tasks

```bash
# Weekly: Check registered users
python tools/auth_admin.py stats

# Monthly: Rotate logs (if not using logrotate)
find fastapi_app/logs/ -name "*.log" -mtime +30 -delete

# As needed: Block suspicious users
python tools/auth_admin.py block <token>

# As needed: Generate more tokens
python tools/auth_admin.py generate 20
```

### Backup Important Data

```bash
# Backup authentication data
tar -czf backup-$(date +%Y%m%d).tar.gz \
    fastapi_app/data/tokens.txt \
    fastapi_app/data/users.txt \
    .env

# Automated daily backup (cron)
0 2 * * * cd /opt/DoorDesignPython && tar -czf /backups/doordesign-$(date +\%Y\%m\%d).tar.gz fastapi_app/data/ .env
```

---

## Security Hardening

### 1. Enable IP Whitelist (Optional)

```bash
# In .env, restrict to specific IPs/ranges
ALLOWED_IPS=203.0.113.0/24,198.51.100.0/24
```

### 2. Require Authentication

```bash
# In .env
REQUIRE_AUTH=true
```

### 3. Set Up Fail2Ban (Linux)

Create `/etc/fail2ban/filter.d/doordesign.conf`:

```ini
[Definition]
failregex = .*"event": "request.denied".*"client_ip": "<HOST>".*
            .*403.*<HOST>.*
ignoreregex =
```

Add to `/etc/fail2ban/jail.local`:

```ini
[doordesign]
enabled = true
port = http,https
filter = doordesign
logpath = /opt/DoorDesignPython/fastapi_app/logs/app.log
maxretry = 5
bantime = 3600
findtime = 600
```

### 4. SSL/TLS Best Practices

```bash
# Use Let's Encrypt for free SSL
sudo certbot --nginx -d your-domain.com

# Or generate self-signed (testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/selfsigned.key \
    -out /etc/ssl/certs/selfsigned.crt
```

---

## Troubleshooting Production Issues

### Issue: 502 Bad Gateway

```bash
# Check if app is running
systemctl status doordesign

# Check if port is listening
netstat -tlnp | grep 8000

# Check recent logs
tail -50 fastapi_app/logs/app.log
```

### Issue: Users Can't Register

```bash
# Check if tokens exist
python tools/auth_admin.py tokens

# Verify BASE_URL is correct
echo $BASE_URL

# Check file permissions
ls -l fastapi_app/data/
```

### Issue: Authentication Not Working

```bash
# Verify COOKIE_SECRET_KEY is set
echo $COOKIE_SECRET_KEY | wc -c  # Should be 64

# Check HTTPS setting matches actual deployment
grep HTTPS .env

# Check user status
python tools/auth_admin.py users
```

### Issue: High Memory/CPU Usage

```bash
# Check active processes
ps aux | grep gunicorn

# Reduce workers in production config
# Decrease FULL_BODY_LOGGING and MAX_FULL_BODY_BYTES

# Monitor resource usage
htop
```

---

## Performance Tuning

### 1. Optimize Gunicorn Workers

```bash
# Rule of thumb: (2 x CPU cores) + 1
workers = $(( 2 * $(nproc) + 1 ))

gunicorn ... --workers $workers
```

### 2. Disable Verbose Logging

```bash
# In .env for production
FULL_BODY_LOGGING=false
```

### 3. Add Caching (Nginx)

```nginx
# Cache static files
location /static/ {
    alias /opt/DoorDesignPython/frontend/;
    expires 7d;
    add_header Cache-Control "public, immutable";
}

# Cache health checks
location /health {
    proxy_pass http://127.0.0.1:8000;
    proxy_cache health_cache;
    proxy_cache_valid 200 10s;
}
```

---

## Scaling Considerations

### Horizontal Scaling

If deploying multiple instances:

1. **Use shared storage** for `fastapi_app/data/`

   ```bash
   # Mount NFS or similar
   mount -t nfs server:/data /opt/DoorDesignPython/fastapi_app/data
   ```

2. **Sync COOKIE_SECRET_KEY** across all instances

3. **Use load balancer** (nginx, HAProxy, AWS ELB)

4. **Consider database backend** instead of text files
   - Migrate to PostgreSQL/MySQL for concurrent access
   - Use Redis for session storage

---

## Health Checks

### Kubernetes Liveness/Readiness

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Uptime Monitoring

Use external monitoring services:

- UptimeRobot
- Pingdom
- StatusCake
- AWS CloudWatch

Configure alerts for:

- 5xx errors
- Response time > 5s
- Disk space > 90%
- Memory usage > 90%

---

## Disaster Recovery

### Restore from Backup

```bash
# Stop service
sudo systemctl stop doordesign

# Restore data
cd /opt/DoorDesignPython
tar -xzf /backups/doordesign-20251128.tar.gz

# Verify permissions
chown -R www-data:www-data fastapi_app/data/

# Start service
sudo systemctl start doordesign
```

### Rotate Secrets (Emergency)

```bash
# Generate new secrets
python -c "import secrets; print(secrets.token_hex(32))" > new_cookie_secret

# Update .env
sed -i "s/^COOKIE_SECRET_KEY=.*/COOKIE_SECRET_KEY=$(cat new_cookie_secret)/" .env

# Restart service (will invalidate all sessions)
sudo systemctl restart doordesign

# Generate new tokens
python tools/auth_admin.py generate 50
```

---

## Compliance & Auditing

### GDPR Considerations

If storing user data in EU:

- Document data retention policy
- Implement user data deletion endpoint
- Log access to personal data
- Provide data export functionality

### Audit Logging

Already implemented:

- ✅ Request/response logging (when enabled)
- ✅ Per-request JSON files
- ✅ Error logging with tracebacks
- ✅ User registration tracking (IP, browser, date)

---

## Support & Updates

### Update Application

```bash
# Backup first
tar -czf backup-before-update.tar.gz fastapi_app/ .env

# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart doordesign

# Verify
curl https://your-domain.com/health
```

---

## Production Checklist

Before going live:

- [ ] Strong `ADMIN_SECRET` configured
- [ ] Strong `COOKIE_SECRET_KEY` configured
- [ ] `HTTPS=true` set in .env
- [ ] `BASE_URL` points to production domain
- [ ] SSL certificate installed and valid
- [ ] Reverse proxy configured (Nginx/Apache)
- [ ] File permissions secured (700 for data/)
- [ ] `.env` file secured (not in Git, 600 permissions)
- [ ] Logs directory writable
- [ ] Initial tokens generated
- [ ] Health check responds correctly
- [ ] Backup strategy implemented
- [ ] Monitoring/alerting configured
- [ ] Firewall rules configured
- [ ] Rate limiting enabled (if needed)
- [ ] Documentation updated with production URLs
- [ ] Team trained on admin tools

---

**Status:** Ready for Production Deployment ✅
