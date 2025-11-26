# Deployment Guide

**Version**: 1.0  
**Last Updated**: November 2024

Production deployment guide for the Vendor AI Agent system. This document covers containerization, infrastructure setup, security hardening, and operational best practices.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Container Deployment](#container-deployment)
4. [PostgreSQL Production Setup](#postgresql-production-setup)
5. [Environment Configuration](#environment-configuration)
6. [Process Management](#process-management)
7. [Reverse Proxy Setup](#reverse-proxy-setup)
8. [Security Hardening](#security-hardening)
9. [Monitoring & Logging](#monitoring--logging)
10. [Backup & Recovery](#backup--recovery)
11. [Scaling Considerations](#scaling-considerations)
12. [CI/CD Integration](#cicd-integration)
13. [Deployment Checklist](#deployment-checklist)
14. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum Production Server:**
- **OS**: Ubuntu 22.04 LTS / RHEL 8+ / Amazon Linux 2023
- **CPU**: 4 cores (8+ recommended for high throughput)
- **RAM**: 8GB (16GB+ recommended)
- **Storage**: 50GB SSD (100GB+ for large document volumes)
- **Python**: 3.10 or 3.11

**Network Requirements:**
- Outbound HTTPS (443) for API calls: OpenAI, SAM.gov, Apollo, Serper, Google Maps
- Inbound access on configured ports (default: 8501 for dashboard, 8000 for API)
- PostgreSQL port (5432) accessible from application servers

### Required Services

- **PostgreSQL**: 14+ (15+ recommended)
- **Redis**: 7+ (optional, for distributed caching)
- **Nginx**: 1.18+ (or alternative reverse proxy)
- **Systemd** or **Supervisor** for process management

---

## Architecture Overview

### Deployment Topology

```
┌─────────────────┐
│   Load Balancer │
│    (Optional)   │
└────────┬────────┘
         │
┌────────▼────────┐
│  Nginx Reverse  │
│      Proxy      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────┐
│ API  │  │ Dash  │
│ App  │  │ board │
└───┬──┘  └───┬───┘
    │         │
    └────┬────┘
         │
┌────────▼────────┐
│   PostgreSQL    │
│    Database     │
└─────────────────┘
         │
┌────────▼────────┐
│  External APIs  │
│ (OpenAI, SAM,   │
│ Apollo, Serper) │
└─────────────────┘
```

### Component Roles

| Component | Purpose | Scaling |
|-----------|---------|---------|
| **CLI Pipeline** | Batch processing of tender documents | Horizontal (multiple workers) |
| **Dashboard** | Visual inspection and debugging | Single instance (Streamlit) |
| **PostgreSQL** | Persistent vendor/tender data | Vertical (replicas for read scaling) |
| **Nginx** | SSL termination, reverse proxy | Load balanced |

---

## Container Deployment

### Dockerfile

Create `Dockerfile` in project root:

```dockerfile
# Production Dockerfile for Vendor AI Agent
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/data /app/outputs && \
    chown -R appuser:appuser /app

WORKDIR /app

# Install Poetry
ENV POETRY_VERSION=1.7.1 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Copy dependency files
COPY --chown=appuser:appuser pyproject.toml poetry.lock ./

# Install dependencies (production only)
RUN poetry install --only main --no-root --no-directory

# Copy application code
COPY --chown=appuser:appuser . .

# Install application
RUN poetry install --only main

# Switch to non-root user
USER appuser

# Health check endpoint (for dashboard)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default command (override in docker-compose or deployment)
CMD ["python", "-m", "streamlit", "run", "src/vendor_ai_agent/dashboard.py"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: vendor_ai_db
    environment:
      POSTGRES_DB: vendor_ai
      POSTGRES_USER: vendor_ai_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    networks:
      - vendor_ai_net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vendor_ai_user -d vendor_ai"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: vendor_ai_app
    environment:
      DATABASE_URL: postgresql://vendor_ai_user:${DB_PASSWORD}@postgres:5432/vendor_ai
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SAM_API_KEY: ${SAM_API_KEY}
      APOLLO_API_KEY: ${APOLLO_API_KEY}
      SERPER_API_KEY: ${SERPER_API_KEY}
      GOOGLE_MAPS_API_KEY: ${GOOGLE_MAPS_API_KEY}
      HUNTER_API_KEY: ${HUNTER_API_KEY}
      LANGCHAIN_TRACING_V2: ${LANGCHAIN_TRACING_V2:-false}
      LANGCHAIN_API_KEY: ${LANGCHAIN_API_KEY}
      SQL_ECHO: "false"
    volumes:
      - ./data:/app/data:ro
      - ./outputs:/app/outputs
    ports:
      - "8501:8501"
    networks:
      - vendor_ai_net
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: vendor_ai_proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - vendor_ai_net
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:

networks:
  vendor_ai_net:
    driver: bridge
```

### Building and Running

```bash
# Build image
docker build -t vendor-ai-agent:latest .

# Run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f app

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Running Database Migrations

```bash
# Run migrations in container
docker-compose exec app poetry run alembic upgrade head

# Or during initial setup
docker-compose run --rm app poetry run alembic upgrade head
```

---

## PostgreSQL Production Setup

### Installation (Ubuntu/Debian)

```bash
# Install PostgreSQL 15
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE vendor_ai;
CREATE USER vendor_ai_user WITH ENCRYPTED PASSWORD 'your_secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE vendor_ai TO vendor_ai_user;

# Connect to database
\c vendor_ai

# Grant schema privileges
GRANT ALL ON SCHEMA public TO vendor_ai_user;

# Exit
\q
```

### Production Configuration

Edit `/etc/postgresql/15/main/postgresql.conf`:

```ini
# Connection Settings
listen_addresses = 'localhost'  # or specific IP for remote access
max_connections = 100
shared_buffers = 2GB            # 25% of RAM
effective_cache_size = 6GB      # 75% of RAM
maintenance_work_mem = 512MB
work_mem = 16MB

# WAL Settings (Write-Ahead Logging)
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB
checkpoint_completion_target = 0.9

# Query Tuning
random_page_cost = 1.1          # for SSDs
effective_io_concurrency = 200  # for SSDs

# Logging
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_min_duration_statement = 1000  # Log queries > 1s
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
```

Edit `/etc/postgresql/15/main/pg_hba.conf`:

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   vendor_ai       vendor_ai_user                          md5
host    vendor_ai       vendor_ai_user  127.0.0.1/32            md5
host    vendor_ai       vendor_ai_user  ::1/128                 md5

# For remote access (use with caution, prefer SSH tunnels)
# host    vendor_ai       vendor_ai_user  10.0.0.0/8              md5
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### Run Migrations

```bash
# From application directory
cd /opt/vendor_ai_agent
source .venv/bin/activate

# Run migrations
poetry run alembic upgrade head
```

### Backup Configuration

Create `/opt/scripts/backup_vendor_ai.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/var/backups/vendor_ai"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="vendor_ai"
DB_USER="vendor_ai_user"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Dump database
pg_dump -U "$DB_USER" -Fc -f "$BACKUP_DIR/vendor_ai_${TIMESTAMP}.dump" "$DB_NAME"

# Compress old backups
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -exec gzip {} \;

# Delete old backups
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: vendor_ai_${TIMESTAMP}.dump"
```

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /opt/scripts/backup_vendor_ai.sh >> /var/log/vendor_ai_backup.log 2>&1
```

---

## Environment Configuration

### Production Environment Variables

Create `/opt/vendor_ai_agent/.env.production`:

```bash
# Application Environment
ENV=production
DEBUG=false

# Database (PostgreSQL)
DATABASE_URL=postgresql://vendor_ai_user:SECURE_PASSWORD@localhost:5432/vendor_ai
SQL_ECHO=false

# OpenAI API
OPENAI_API_KEY=sk-prod-your-key-here

# External APIs
SAM_API_KEY=your-sam-api-key
APOLLO_API_KEY=your-apollo-api-key
SERPER_API_KEY=your-serper-api-key
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
HUNTER_API_KEY=your-hunter-api-key

# LangSmith (Optional - Production Monitoring)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=ls-prod-your-key
LANGCHAIN_PROJECT=vendor-agent-production

# LLM Configuration
SMART_LLM_MODEL=gpt-4o
CHEAP_LLM_MODEL=gpt-4o-mini
VISION_LLM_MODEL=gpt-4o-mini
USE_FLEX_TIER=true

# Pipeline Configuration
ENABLE_AUTO_INGESTION=true

# Paths
DATA_DIR=/opt/vendor_ai_agent/data
OUTPUT_DIR=/var/vendor_ai/outputs
```

### Secrets Management

**Option 1: AWS Systems Manager Parameter Store**

```python
# src/vendor_ai_agent/secrets.py
import boto3
import os
from functools import lru_cache

@lru_cache
def get_secret(key: str) -> str:
    if os.getenv('ENV') != 'production':
        return os.getenv(key, '')
    
    ssm = boto3.client('ssm', region_name='us-east-1')
    response = ssm.get_parameter(
        Name=f'/vendor-ai/{key}',
        WithDecryption=True
    )
    return response['Parameter']['Value']

# Usage in config.py
from .secrets import get_secret

openai_api_key = get_secret('OPENAI_API_KEY')
```

**Option 2: HashiCorp Vault**

```python
# src/vendor_ai_agent/secrets.py
import hvac
import os

def get_vault_client():
    return hvac.Client(
        url=os.getenv('VAULT_ADDR', 'http://localhost:8200'),
        token=os.getenv('VAULT_TOKEN')
    )

def get_secret(key: str) -> str:
    if os.getenv('ENV') != 'production':
        return os.getenv(key, '')
    
    client = get_vault_client()
    secret = client.secrets.kv.v2.read_secret_version(
        path='vendor-ai/config'
    )
    return secret['data']['data'][key]
```

**Option 3: Docker Secrets**

```yaml
# docker-compose.yml (Docker Swarm)
services:
  app:
    secrets:
      - openai_api_key
      - db_password
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key
      DB_PASSWORD_FILE: /run/secrets/db_password

secrets:
  openai_api_key:
    external: true
  db_password:
    external: true
```

```python
# Load secrets from files
def load_secret_from_file(env_var: str) -> str:
    file_path = os.getenv(f'{env_var}_FILE')
    if file_path and os.path.exists(file_path):
        with open(file_path) as f:
            return f.read().strip()
    return os.getenv(env_var, '')
```

---

## Process Management

### Systemd Service (Recommended)

Create `/etc/systemd/system/vendor-ai-dashboard.service`:

```ini
[Unit]
Description=Vendor AI Agent Dashboard
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=vendor-ai
Group=vendor-ai
WorkingDirectory=/opt/vendor_ai_agent
Environment="PATH=/opt/vendor_ai_agent/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/opt/vendor_ai_agent/.env.production
ExecStart=/opt/vendor_ai_agent/.venv/bin/streamlit run src/vendor_ai_agent/dashboard.py --server.port=8501 --server.address=127.0.0.1

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/vendor_ai_agent/outputs /var/vendor_ai

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vendor-ai-dashboard

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/vendor-ai-worker@.service` (for batch processing):

```ini
[Unit]
Description=Vendor AI Agent Worker %i
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=oneshot
User=vendor-ai
Group=vendor-ai
WorkingDirectory=/opt/vendor_ai_agent
Environment="PATH=/opt/vendor_ai_agent/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/opt/vendor_ai_agent/.env.production
ExecStart=/opt/vendor_ai_agent/.venv/bin/python scripts/run_full_pipeline.py %I

StandardOutput=journal
StandardError=journal
SyslogIdentifier=vendor-ai-worker-%i
```

Enable and start services:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable dashboard service
sudo systemctl enable vendor-ai-dashboard.service
sudo systemctl start vendor-ai-dashboard.service

# Check status
sudo systemctl status vendor-ai-dashboard.service

# View logs
sudo journalctl -u vendor-ai-dashboard.service -f

# Run worker for specific tender
sudo systemctl start vendor-ai-worker@tender_12345.service
```

### Supervisor (Alternative)

Install supervisor:

```bash
sudo apt install supervisor
```

Create `/etc/supervisor/conf.d/vendor-ai.conf`:

```ini
[program:vendor-ai-dashboard]
command=/opt/vendor_ai_agent/.venv/bin/streamlit run src/vendor_ai_agent/dashboard.py --server.port=8501 --server.address=127.0.0.1
directory=/opt/vendor_ai_agent
user=vendor-ai
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/vendor_ai/dashboard.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=PATH="/opt/vendor_ai_agent/.venv/bin:%(ENV_PATH)s"
```

Manage service:

```bash
# Update configuration
sudo supervisorctl reread
sudo supervisorctl update

# Start/stop/restart
sudo supervisorctl start vendor-ai-dashboard
sudo supervisorctl stop vendor-ai-dashboard
sudo supervisorctl restart vendor-ai-dashboard

# Check status
sudo supervisorctl status vendor-ai-dashboard
```

---

## Reverse Proxy Setup

### Nginx Configuration

Create `/etc/nginx/sites-available/vendor-ai`:

```nginx
# Upstream servers
upstream vendor_ai_dashboard {
    server 127.0.0.1:8501 max_fails=3 fail_timeout=30s;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name vendor-ai.example.com;

    # Let's Encrypt ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name vendor-ai.example.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/vendor-ai.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vendor-ai.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Logging
    access_log /var/log/nginx/vendor-ai-access.log combined;
    error_log /var/log/nginx/vendor-ai-error.log warn;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=vendor_ai_limit:10m rate=10r/s;
    limit_req zone=vendor_ai_limit burst=20 nodelay;

    # Max upload size (for tender documents)
    client_max_body_size 100M;

    # Dashboard
    location / {
        proxy_pass http://vendor_ai_dashboard;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Streamlit WebSocket settings
        proxy_buffering off;
        proxy_read_timeout 86400;
    }

    # Health check endpoint
    location /_health {
        access_log off;
        proxy_pass http://vendor_ai_dashboard/_stcore/health;
    }

    # Static files (if serving output files)
    location /outputs/ {
        alias /var/vendor_ai/outputs/;
        autoindex off;
        
        # Basic auth for output files
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

Enable site:

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/vendor-ai /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d vendor-ai.example.com

# Auto-renewal (certbot installs cron job automatically)
# Test renewal
sudo certbot renew --dry-run
```

### Basic Authentication for Dashboard

```bash
# Install htpasswd utility
sudo apt install apache2-utils

# Create password file
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Add additional users
sudo htpasswd /etc/nginx/.htpasswd user2
```

Add to nginx config:

```nginx
location / {
    auth_basic "Vendor AI Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://vendor_ai_dashboard;
    # ... rest of config
}
```

---

## Security Hardening

### Application Security

**1. API Key Rotation**

Implement key rotation policy:

```python
# src/vendor_ai_agent/security.py
from datetime import datetime, timedelta
import os

def check_key_expiration(key_name: str, rotation_days: int = 90):
    rotation_file = f"/opt/vendor_ai_agent/.keys/{key_name}_rotated_at"
    
    if not os.path.exists(rotation_file):
        return True  # Needs rotation
    
    with open(rotation_file) as f:
        last_rotation = datetime.fromisoformat(f.read().strip())
    
    return (datetime.now() - last_rotation).days > rotation_days

def record_key_rotation(key_name: str):
    os.makedirs("/opt/vendor_ai_agent/.keys", exist_ok=True)
    rotation_file = f"/opt/vendor_ai_agent/.keys/{key_name}_rotated_at"
    with open(rotation_file, 'w') as f:
        f.write(datetime.now().isoformat())
```

**2. Input Validation**

```python
# src/vendor_ai_agent/validators.py
import re
from pathlib import Path

def validate_file_path(file_path: str, allowed_dirs: list[str]) -> bool:
    path = Path(file_path).resolve()
    return any(str(path).startswith(allowed_dir) for allowed_dir in allowed_dirs)

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

def validate_api_key_format(key: str, prefix: str) -> bool:
    return key.startswith(prefix) and len(key) > 20
```

**3. Rate Limiting**

```python
# src/vendor_ai_agent/rate_limiter.py
from functools import wraps
from time import time, sleep
from collections import defaultdict
import threading

class RateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = defaultdict(list)
        self.lock = threading.Lock()
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                now = time()
                self.calls[func.__name__] = [
                    call_time for call_time in self.calls[func.__name__]
                    if now - call_time < 60
                ]
                
                if len(self.calls[func.__name__]) >= self.calls_per_minute:
                    sleep(60 - (now - self.calls[func.__name__][0]))
                
                self.calls[func.__name__].append(time())
            
            return func(*args, **kwargs)
        return wrapper

# Usage
rate_limiter = RateLimiter(calls_per_minute=50)

@rate_limiter
def call_openai_api():
    pass
```

### Database Security

**1. Connection Security**

Always use SSL for database connections:

```python
# In config.py
DATABASE_URL = "postgresql://user:pass@host:5432/db?sslmode=require"
```

PostgreSQL SSL setup:

```bash
# Generate self-signed certificate (or use CA-signed)
sudo -u postgres openssl req -new -x509 -days 365 -nodes \
    -text -out /var/lib/postgresql/15/main/server.crt \
    -keyout /var/lib/postgresql/15/main/server.key

sudo chmod 600 /var/lib/postgresql/15/main/server.key
sudo chown postgres:postgres /var/lib/postgresql/15/main/server.*
```

Enable SSL in `postgresql.conf`:

```ini
ssl = on
ssl_cert_file = '/var/lib/postgresql/15/main/server.crt'
ssl_key_file = '/var/lib/postgresql/15/main/server.key'
```

**2. Least Privilege Access**

```sql
-- Create read-only user for reporting
CREATE USER vendor_ai_readonly WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE vendor_ai TO vendor_ai_readonly;
GRANT USAGE ON SCHEMA public TO vendor_ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vendor_ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO vendor_ai_readonly;

-- Revoke unnecessary permissions
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

### System Hardening

**1. Firewall Configuration (UFW)**

```bash
# Enable firewall
sudo ufw enable

# Allow SSH (change port if using non-standard)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow PostgreSQL only from application server
sudo ufw allow from 10.0.1.10 to any port 5432

# Check status
sudo ufw status verbose
```

**2. File Permissions**

```bash
# Application directory
sudo chown -R vendor-ai:vendor-ai /opt/vendor_ai_agent
sudo chmod 750 /opt/vendor_ai_agent

# Environment file
sudo chmod 600 /opt/vendor_ai_agent/.env.production

# Output directory
sudo mkdir -p /var/vendor_ai/outputs
sudo chown vendor-ai:vendor-ai /var/vendor_ai/outputs
sudo chmod 755 /var/vendor_ai/outputs
```

**3. SELinux (RHEL/CentOS)**

```bash
# Set SELinux contexts
sudo semanage fcontext -a -t httpd_sys_content_t "/var/vendor_ai/outputs(/.*)?"
sudo restorecon -Rv /var/vendor_ai/outputs

# Allow nginx to connect to network
sudo setsebool -P httpd_can_network_connect 1
```

### Dependency Security

**1. Vulnerability Scanning**

```bash
# Scan dependencies with pip-audit
pip install pip-audit
pip-audit

# Or with safety
pip install safety
safety check --json
```

**2. Pinned Dependencies**

Always use `poetry.lock` in production:

```bash
# Install exact versions from lock file
poetry install --no-dev
```

**3. Regular Updates**

```bash
# Check for updates
poetry show --outdated

# Update dependencies
poetry update

# Run tests after updates
pytest tests/
```

---

## Monitoring & Logging

### Application Logging

Configure structured logging in production:

```python
# src/vendor_ai_agent/logging_config.py
import logging
import logging.handlers
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

def setup_logging(log_level=logging.INFO):
    logger = logging.getLogger('vendor_ai_agent')
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # File handler (rotating)
    file_handler = logging.handlers.RotatingFileHandler(
        '/var/log/vendor_ai/app.log',
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    return logger

# In main application
from .logging_config import setup_logging
logger = setup_logging()
```

### Prometheus Metrics (Optional)

Install prometheus client:

```bash
poetry add prometheus-client
```

Expose metrics:

```python
# src/vendor_ai_agent/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Metrics
pipeline_runs = Counter('pipeline_runs_total', 'Total pipeline runs', ['status'])
pipeline_duration = Histogram('pipeline_duration_seconds', 'Pipeline execution time')
vendors_discovered = Gauge('vendors_discovered', 'Number of vendors discovered')
llm_calls = Counter('llm_calls_total', 'Total LLM API calls', ['model', 'status'])
llm_tokens = Counter('llm_tokens_total', 'Total tokens used', ['model', 'type'])

def start_metrics_server(port=9090):
    start_http_server(port)

# Usage in pipeline
@pipeline_duration.time()
def run_pipeline():
    try:
        # ... pipeline logic
        pipeline_runs.labels(status='success').inc()
    except Exception:
        pipeline_runs.labels(status='failure').inc()
        raise
```

Start metrics server:

```python
# In dashboard.py or separate metrics service
from .metrics import start_metrics_server
start_metrics_server(port=9090)
```

### Health Checks

Create health check endpoint:

```python
# src/vendor_ai_agent/health.py
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import text
from .database import get_session, get_engine

@dataclass
class HealthStatus:
    status: str
    timestamp: str
    database: bool
    dependencies: dict

def check_health() -> HealthStatus:
    health = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': False,
        'dependencies': {}
    }
    
    # Check database
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health['database'] = True
    except Exception as e:
        health['status'] = 'unhealthy'
        health['dependencies']['database_error'] = str(e)
    
    # Check OpenAI
    import openai
    try:
        client = openai.OpenAI()
        client.models.list()
        health['dependencies']['openai'] = 'ok'
    except Exception as e:
        health['status'] = 'degraded'
        health['dependencies']['openai'] = 'unavailable'
    
    return HealthStatus(**health)
```

### Log Aggregation (ELK Stack)

**Filebeat Configuration** (`/etc/filebeat/filebeat.yml`):

```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/vendor_ai/*.log
    json.keys_under_root: true
    json.add_error_key: true
    fields:
      app: vendor-ai-agent
      env: production

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "vendor-ai-%{+yyyy.MM.dd}"

setup.kibana:
  host: "kibana:5601"
```

---

## Backup & Recovery

### Database Backup Strategy

**Full Backup Script** (`/opt/scripts/full_backup.sh`):

```bash
#!/bin/bash
set -e

BACKUP_DIR="/var/backups/vendor_ai"
S3_BUCKET="s3://your-backup-bucket/vendor-ai"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="vendor_ai"
DB_USER="vendor_ai_user"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting full backup..."

# Database dump
pg_dump -U "$DB_USER" -Fc -f "$BACKUP_DIR/db_${TIMESTAMP}.dump" "$DB_NAME"

# Application data
tar -czf "$BACKUP_DIR/data_${TIMESTAMP}.tar.gz" /opt/vendor_ai_agent/data

# Upload to S3 (if configured)
if command -v aws &> /dev/null; then
    aws s3 cp "$BACKUP_DIR/db_${TIMESTAMP}.dump" "$S3_BUCKET/db/"
    aws s3 cp "$BACKUP_DIR/data_${TIMESTAMP}.tar.gz" "$S3_BUCKET/data/"
    echo "[$(date)] Backups uploaded to S3"
fi

# Cleanup old local backups
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Backup completed successfully"
```

**Incremental Backup (WAL Archiving)**

Configure in `postgresql.conf`:

```ini
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /var/backups/wal_archive/%f && cp %p /var/backups/wal_archive/%f'
archive_timeout = 300  # 5 minutes
```

Create archive directory:

```bash
sudo mkdir -p /var/backups/wal_archive
sudo chown postgres:postgres /var/backups/wal_archive
sudo chmod 700 /var/backups/wal_archive
```

### Disaster Recovery

**Recovery Script** (`/opt/scripts/restore_backup.sh`):

```bash
#!/bin/bash
set -e

BACKUP_FILE="$1"
DB_NAME="vendor_ai"
DB_USER="vendor_ai_user"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

echo "WARNING: This will drop and recreate the database!"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Stop application
sudo systemctl stop vendor-ai-dashboard.service

# Drop and recreate database
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

# Restore dump
pg_restore -U "$DB_USER" -d "$DB_NAME" -v "$BACKUP_FILE"

# Run migrations (if schema changed)
cd /opt/vendor_ai_agent
source .venv/bin/activate
poetry run alembic upgrade head

# Start application
sudo systemctl start vendor-ai-dashboard.service

echo "Restore completed successfully"
```

### Point-in-Time Recovery (PITR)

```bash
# Stop PostgreSQL
sudo systemctl stop postgresql

# Restore base backup
cd /var/lib/postgresql/15/main
sudo -u postgres rm -rf *
sudo -u postgres tar -xzf /var/backups/vendor_ai/base_backup.tar.gz

# Configure recovery
sudo -u postgres cat > recovery.conf <<EOF
restore_command = 'cp /var/backups/wal_archive/%f %p'
recovery_target_time = '2024-11-20 15:30:00'
EOF

# Start PostgreSQL (will enter recovery mode)
sudo systemctl start postgresql

# Check recovery status
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"
```

---

## Scaling Considerations

### Horizontal Scaling

**1. Load Balanced Dashboard**

Use multiple dashboard instances behind load balancer:

```yaml
# docker-compose.scale.yml
services:
  dashboard:
    image: vendor-ai-agent:latest
    deploy:
      replicas: 3
    environment:
      - DATABASE_URL=postgresql://...
    networks:
      - vendor_ai_net
```

Run with:

```bash
docker-compose -f docker-compose.yml -f docker-compose.scale.yml up -d
```

**2. Distributed Pipeline Workers**

Use message queue for pipeline jobs:

```python
# src/vendor_ai_agent/worker.py
from celery import Celery
import os

app = Celery('vendor_ai_worker',
             broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
             backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

@app.task
def process_tender(tender_path: str):
    from .pipeline import run_full_pipeline
    return run_full_pipeline(tender_path)

# Submit job
from .worker import process_tender
result = process_tender.delay('/data/tender_12345')
```

Start workers:

```bash
celery -A src.vendor_ai_agent.worker worker --loglevel=info --concurrency=4
```

### Vertical Scaling

**PostgreSQL Tuning for Larger Datasets**

For databases > 100GB:

```ini
# postgresql.conf
shared_buffers = 8GB
effective_cache_size = 24GB
maintenance_work_mem = 2GB
work_mem = 64MB
max_connections = 200

# Query optimization
random_page_cost = 1.1
effective_io_concurrency = 300
```

**Application Memory**

For large document processing:

```python
# In config.py
import os

# Limit concurrent processing
MAX_CONCURRENT_DOCUMENTS = int(os.getenv('MAX_CONCURRENT_DOCS', '5'))

# Chunk large files
DOCUMENT_CHUNK_SIZE = int(os.getenv('DOC_CHUNK_SIZE', '10000'))
```

### Caching Layer

Implement Redis for API response caching:

```python
# src/vendor_ai_agent/cache.py
import redis
import json
import hashlib
from functools import wraps

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    db=0,
    decode_responses=True
)

def cache_response(ttl_seconds=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hashlib.md5(str(args).encode()).hexdigest()}"
            
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, ttl_seconds, json.dumps(result))
            return result
        return wrapper
    return decorator

# Usage
@cache_response(ttl_seconds=86400)  # 24 hours
def search_sam_vendors(naics_code: str):
    # ... expensive API call
    pass
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run tests
        run: poetry run pytest tests/
      
      - name: Security scan
        run: |
          poetry run pip-audit
          poetry run bandit -r src/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Docker Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ secrets.DOCKER_REGISTRY }}
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_REGISTRY }}/vendor-ai-agent:latest
            ${{ secrets.DOCKER_REGISTRY }}/vendor-ai-agent:${{ github.sha }}
          cache-from: type=registry,ref=${{ secrets.DOCKER_REGISTRY }}/vendor-ai-agent:buildcache
          cache-to: type=registry,ref=${{ secrets.DOCKER_REGISTRY }}/vendor-ai-agent:buildcache,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /opt/vendor_ai_agent
            docker-compose pull
            docker-compose up -d --no-deps app
            docker-compose exec -T app poetry run alembic upgrade head
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  IMAGE_TAG: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

test:
  stage: test
  image: python:3.11
  before_script:
    - pip install poetry
    - poetry install
  script:
    - poetry run pytest tests/
    - poetry run pip-audit
  only:
    - main
    - merge_requests

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $IMAGE_TAG .
    - docker push $IMAGE_TAG
  only:
    - main

deploy:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
  script:
    - ssh $DEPLOY_USER@$DEPLOY_HOST "
        cd /opt/vendor_ai_agent &&
        docker-compose pull &&
        docker-compose up -d --no-deps app &&
        docker-compose exec -T app poetry run alembic upgrade head
      "
  only:
    - main
  when: manual
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All tests passing (`pytest tests/`)
- [ ] Security scan completed (`pip-audit`, `bandit`)
- [ ] Database migrations tested (`alembic upgrade head`)
- [ ] Environment variables configured (`.env.production`)
- [ ] Secrets stored securely (AWS SSM, Vault, etc.)
- [ ] SSL certificates obtained and configured
- [ ] Firewall rules configured
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting configured
- [ ] Documentation updated

### Deployment Steps

1. **Backup Current System**
   ```bash
   /opt/scripts/full_backup.sh
   ```

2. **Pull Latest Code**
   ```bash
   cd /opt/vendor_ai_agent
   git pull origin main
   ```

3. **Update Dependencies**
   ```bash
   poetry install --no-dev
   ```

4. **Run Migrations**
   ```bash
   poetry run alembic upgrade head
   ```

5. **Restart Services**
   ```bash
   sudo systemctl restart vendor-ai-dashboard.service
   ```

6. **Verify Deployment**
   ```bash
   sudo systemctl status vendor-ai-dashboard.service
   curl -f http://localhost:8501/_stcore/health
   ```

7. **Monitor Logs**
   ```bash
   sudo journalctl -u vendor-ai-dashboard.service -f
   ```

### Post-Deployment

- [ ] Health checks passing
- [ ] Dashboard accessible
- [ ] Test pipeline run completed successfully
- [ ] No errors in logs
- [ ] Monitoring dashboards showing normal metrics
- [ ] Backup verification

---

## Troubleshooting

### Common Issues

**1. Database Connection Failures**

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connections
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity WHERE datname='vendor_ai';"

# Test connection from app
psql "postgresql://vendor_ai_user:password@localhost:5432/vendor_ai" -c "SELECT 1;"
```

**2. Service Won't Start**

```bash
# Check service logs
sudo journalctl -u vendor-ai-dashboard.service -n 100

# Check permissions
ls -la /opt/vendor_ai_agent
ls -la /opt/vendor_ai_agent/.env.production

# Test manual start
cd /opt/vendor_ai_agent
source .venv/bin/activate
streamlit run src/vendor_ai_agent/dashboard.py
```

**3. High Memory Usage**

```bash
# Check process memory
ps aux | grep streamlit

# Monitor in real-time
top -p $(pgrep -f streamlit)

# Adjust worker limits in config
export MAX_CONCURRENT_DOCS=2
```

**4. SSL Certificate Issues**

```bash
# Check certificate validity
sudo certbot certificates

# Test SSL configuration
openssl s_client -connect vendor-ai.example.com:443 -servername vendor-ai.example.com

# Renew certificate
sudo certbot renew --force-renewal
```

**5. Permission Denied Errors**

```bash
# Fix ownership
sudo chown -R vendor-ai:vendor-ai /opt/vendor_ai_agent
sudo chown -R vendor-ai:vendor-ai /var/vendor_ai

# Fix permissions
sudo chmod 750 /opt/vendor_ai_agent
sudo chmod 600 /opt/vendor_ai_agent/.env.production
```

### Emergency Recovery

**Rollback Deployment**

```bash
# Restore previous version
cd /opt/vendor_ai_agent
git checkout <previous-commit>
poetry install --no-dev

# Rollback database
poetry run alembic downgrade -1

# Restart service
sudo systemctl restart vendor-ai-dashboard.service
```

**Database Recovery**

```bash
# Restore from latest backup
/opt/scripts/restore_backup.sh /var/backups/vendor_ai/db_20241125_020000.dump
```

### Performance Debugging

```bash
# Check database query performance
sudo -u postgres psql vendor_ai <<EOF
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
EOF

# Monitor API response times
sudo journalctl -u vendor-ai-dashboard.service | grep -E "duration|time" | tail -20

# Check system resources
htop
iostat -x 2 5
vmstat 2 5
```

---

## Additional Resources

### Documentation References

- [API Reference](API_REFERENCE.md)
- [Configuration Guide](CONFIGURATION.md)
- [Database Schema](DATABASE_SCHEMA.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Pipeline Workflow](PIPELINE_WORKFLOW.md)

### External Documentation

- [PostgreSQL Production Checklist](https://www.postgresql.org/docs/current/index.html)
- [Nginx Security Best Practices](https://nginx.org/en/docs/)
- [Docker Production Guide](https://docs.docker.com/production/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Systemd Service Management](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

### Support

For deployment assistance or issues:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review application logs: `/var/log/vendor_ai/`
3. Check system logs: `sudo journalctl -u vendor-ai-dashboard.service`
4. Contact system administrator or DevOps team

---

**Document Version**: 1.0  
**Last Updated**: November 2024  
**Maintained By**: DevOps Team
