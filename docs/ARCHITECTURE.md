# Tender Vendor AI Agent – Technical Architecture

This document provides a comprehensive guide to the system architecture, design principles, and technical implementation of the Tender Vendor AI Agent. It maps functional stages to code modules, explains data flow, and documents extensibility patterns.

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Architecture](#module-architecture)
3. [Pipeline Architecture](#pipeline-architecture)
4. [Data Flow](#data-flow)
5. [Extensibility Points](#extensibility-points)
6. [Configuration System](#configuration-system)
7. [Database Architecture](#database-architecture)
8. [Error Handling Strategy](#error-handling-strategy)
9. [Performance Architecture](#performance-architecture)
10. [Security Architecture](#security-architecture)

---

## 8. Security Architecture

### Security Principles

**1. Defense in Depth**
- Multiple layers of security controls
- No single point of failure
- Assume each layer can be breached

**2. Least Privilege**
- Minimum necessary permissions
- Time-limited access tokens
- Role-based access control (RBAC)

**3. Secure by Default**
- Environment variables for secrets
- HTTPS-only communication
- Encrypted data at rest

**4. Audit Trail**
- Log all sensitive operations
- Track who accessed what data
- Immutable audit logs

### API Key Management

**1. Environment Variables (Never Commit Secrets)**

```python
# config.py
import os
from typing import Optional

class Config:
    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    APOLLO_API_KEY: Optional[str] = os.getenv("APOLLO_API_KEY")
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:pass@localhost/vendor_ai"
    )
    
    @classmethod
    def validate(cls):
        """Validate required secrets are present."""
        missing = []
        
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.APOLLO_API_KEY:
            missing.append("APOLLO_API_KEY")
        
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

# Validate on startup
Config.validate()
```

**.env.example (Template for Users):**
```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-...

# Apollo.io API Key (optional, for contact enrichment)
APOLLO_API_KEY=...

# Serper API Key (optional, for web search)
SERPER_API_KEY=...

# Database URL
DATABASE_URL=postgresql://user:password@localhost:5432/vendor_ai

# Environment
ENVIRONMENT=development  # development, staging, production
```

**.gitignore (Prevent Accidental Commits):**
```
.env
.env.local
*.pem
*.key
secrets/
```

**2. Secret Managers (Production Deployments)**

```python
# AWS Secrets Manager
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}")
        raise

# Usage
if os.getenv("ENVIRONMENT") == "production":
    secrets = get_secret("vendor-ai-agent/api-keys")
    Config.OPENAI_API_KEY = secrets["openai_api_key"]
    Config.APOLLO_API_KEY = secrets["apollo_api_key"]
```

**Alternative: HashiCorp Vault**
```python
import hvac

client = hvac.Client(url='https://vault.example.com:8200')
client.token = os.getenv("VAULT_TOKEN")

secret = client.secrets.kv.v2.read_secret_version(
    path='vendor-ai-agent/api-keys'
)

Config.OPENAI_API_KEY = secret['data']['data']['openai_api_key']
```

**3. Key Rotation Policy**

| Secret | Rotation Frequency | Automation |
|--------|-------------------|------------|
| API Keys (OpenAI, Apollo) | 90 days | Manual (vendor-specific) |
| Database Passwords | 90 days | Automated (AWS RDS) |
| JWT Signing Keys | 30 days | Automated (key versioning) |
| SSH Keys | 180 days | Manual |

**Rotation Process:**
1. Generate new key
2. Add to secrets manager with version tag
3. Update application config (zero-downtime deploy)
4. Verify new key works
5. Revoke old key after 24h grace period

### Data Privacy & GDPR Compliance

**1. PII Handling (Vendor Contacts)**

```python
class PIIProtection:
    """Anonymize and protect personally identifiable information."""
    
    @staticmethod
    def anonymize_email(email: str) -> str:
        """Hash email for logging/analytics."""
        return hashlib.sha256(email.encode()).hexdigest()[:16]
    
    @staticmethod
    def redact_phone(phone: str) -> str:
        """Redact phone number for logs."""
        if len(phone) >= 4:
            return f"***-***-{phone[-4:]}"
        return "***"
    
    @staticmethod
    def mask_contact(contact: dict) -> dict:
        """Mask PII in contact data for logging."""
        return {
            "name": contact.get("name", "")[:1] + "***",
            "email": PIIProtection.anonymize_email(contact.get("email", "")),
            "phone": PIIProtection.redact_phone(contact.get("phone", ""))
        }

# Usage in logging
logger.info(
    f"Enriched contact: {PIIProtection.mask_contact(contact)}"
)
```

**2. Data Retention Policies**

```sql
-- Automatically delete old enrichment data (90 days)
CREATE OR REPLACE FUNCTION cleanup_old_enrichment_data()
RETURNS void AS $$
BEGIN
    DELETE FROM vendor_enrichment_data
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    DELETE FROM execution_logs
    WHERE created_at < NOW() - INTERVAL '365 days';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup (run daily via cron/scheduler)
SELECT cron.schedule(
    'cleanup-enrichment',
    '0 2 * * *',  -- 2 AM daily
    'SELECT cleanup_old_enrichment_data();'
);
```

**3. Right to Erasure (GDPR Article 17)**

```python
class GDPRCompliance:
    """GDPR data subject rights implementation."""
    
    def delete_vendor_data(self, vendor_id: str, reason: str):
        """Delete all data for a specific vendor (right to erasure)."""
        with session_scope() as session:
            # Log deletion request (immutable audit trail)
            session.execute(
                """
                INSERT INTO data_deletion_log (vendor_id, reason, deleted_at)
                VALUES (:vendor_id, :reason, NOW())
                """,
                {"vendor_id": vendor_id, "reason": reason}
            )
            
            # Delete vendor data (cascades to enrichment_data)
            session.query(Vendor).filter_by(id=vendor_id).delete()
            
            # Delete from cache
            self.cache.delete(f"vendor:{vendor_id}")
            
            logger.info(f"Deleted vendor {vendor_id} per GDPR request")
    
    def export_vendor_data(self, vendor_id: str) -> dict:
        """Export all data for a vendor (right to data portability)."""
        vendor = session.query(Vendor).filter_by(id=vendor_id).first()
        
        return {
            "vendor": vendor.to_dict(),
            "enrichment_data": vendor.enrichment_data,
            "execution_logs": [log.to_dict() for log in vendor.execution_logs],
            "exported_at": datetime.utcnow().isoformat()
        }
```

**4. Data Anonymization for Testing**

```python
def anonymize_production_data():
    """Create anonymized test dataset from production data."""
    vendors = session.query(Vendor).all()
    
    for vendor in vendors:
        # Replace real names with fake names
        vendor.legal_name = f"Company_{vendor.id[:8]}"
        vendor.contact_email = f"contact_{vendor.id[:8]}@example.com"
        vendor.contact_phone = f"555-{random.randint(1000, 9999)}"
        
        # Keep non-PII data (NAICS, location, capabilities)
        # These are needed for testing matching logic
    
    session.commit()
```

### Input Validation & Sanitization

**1. PDF Validation**

```python
import magic
from pathlib import Path

class PDFValidator:
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "application/x-pdf"
    ]
    
    @classmethod
    def validate(cls, file_path: Path) -> None:
        """Validate PDF file before parsing."""
        # Check file exists
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > cls.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_size / 1024 / 1024:.1f} MB "
                f"(max {cls.MAX_FILE_SIZE / 1024 / 1024} MB)"
            )
        
        # Check MIME type (prevent XXE, zip bombs, etc.)
        mime_type = magic.from_file(str(file_path), mime=True)
        if mime_type not in cls.ALLOWED_MIME_TYPES:
            raise ValueError(
                f"Invalid file type: {mime_type}. "
                f"Expected PDF (application/pdf)"
            )
        
        # Check for encryption/password protection
        try:
            with pdfplumber.open(file_path) as pdf:
                if pdf.metadata.get("Encrypt"):
                    raise ValueError("Password-protected PDFs not supported")
        except Exception as e:
            raise ValueError(f"Failed to open PDF: {e}")

# Usage
try:
    PDFValidator.validate(Path(tender_file))
    tender = parse_tender_document(tender_file)
except ValueError as e:
    logger.error(f"PDF validation failed: {e}")
    raise
```

**2. SQL Injection Prevention**

```python
# GOOD: Parameterized queries (safe)
def get_vendor_by_uei(uei: str) -> Optional[Vendor]:
    return session.query(Vendor).filter_by(uei=uei).first()

# GOOD: SQLAlchemy ORM (safe)
vendors = session.query(Vendor).filter(
    Vendor.all_naics_codes.contains([naics_code])
).all()

# BAD: String concatenation (vulnerable to SQL injection)
def get_vendor_by_uei_UNSAFE(uei: str):
    query = f"SELECT * FROM vendors WHERE uei = '{uei}'"  # NEVER DO THIS
    return session.execute(query).fetchall()

# If raw SQL is necessary, use parameterized queries
def execute_raw_query(uei: str):
    query = "SELECT * FROM vendors WHERE uei = :uei"
    return session.execute(query, {"uei": uei}).fetchall()
```

**3. XSS Prevention (Dashboard Output)**

```python
import html

def sanitize_output(text: str) -> str:
    """Escape HTML entities to prevent XSS."""
    return html.escape(text)

# Usage in Streamlit dashboard
st.write(f"Vendor: {sanitize_output(vendor.legal_name)}")

# Or use Streamlit's built-in escaping (default behavior)
st.dataframe(vendors_df)  # Automatically escapes HTML
```

**4. NAICS Code Validation**

```python
import re

class NAICSValidator:
    """Validate NAICS codes (6-digit format)."""
    
    NAICS_PATTERN = re.compile(r"^\d{6}$")
    
    @classmethod
    def validate(cls, naics: str) -> str:
        """Validate and normalize NAICS code."""
        # Remove whitespace
        naics = naics.strip()
        
        # Check format
        if not cls.NAICS_PATTERN.match(naics):
            raise ValueError(
                f"Invalid NAICS code: {naics}. "
                f"Expected 6-digit format (e.g., 541330)"
            )
        
        # Validate range (NAICS codes are 11xxxx to 92xxxx)
        code_int = int(naics)
        if code_int < 110000 or code_int > 999999:
            raise ValueError(f"NAICS code out of range: {naics}")
        
        return naics
    
    @classmethod
    def validate_list(cls, naics_list: List[str]) -> List[str]:
        """Validate list of NAICS codes."""
        validated = []
        errors = []
        
        for naics in naics_list:
            try:
                validated.append(cls.validate(naics))
            except ValueError as e:
                errors.append(str(e))
        
        if errors:
            raise ValueError(f"NAICS validation errors: {'; '.join(errors)}")
        
        return validated

# Usage
try:
    naics_codes = NAICSValidator.validate_list(["541330", "541511"])
except ValueError as e:
    logger.error(f"NAICS validation failed: {e}")
```

### Rate Limiting & Abuse Prevention

**1. Per-API-Key Rate Limiting**

```python
from functools import wraps
from datetime import datetime, timedelta
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def rate_limit(max_calls: int, period_seconds: int):
    """Rate limit decorator using Redis."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract API key from kwargs or args
            api_key = kwargs.get("api_key") or args[0]
            
            # Redis key: rate_limit:<api_key>:<function_name>
            redis_key = f"rate_limit:{api_key}:{func.__name__}"
            
            # Get current call count
            current_calls = redis_client.get(redis_key)
            
            if current_calls and int(current_calls) >= max_calls:
                raise RateLimitExceeded(
                    f"Rate limit exceeded: {max_calls} calls per {period_seconds}s"
                )
            
            # Increment call count
            pipe = redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, period_seconds)
            pipe.execute()
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Usage
@rate_limit(max_calls=10, period_seconds=60)
def call_openai_api(api_key: str, prompt: str):
    """Limited to 10 calls per minute per API key."""
    pass
```

**2. IP-Based Throttling**

```python
from fastapi import Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/discover")
@limiter.limit("5/minute")  # 5 requests per minute per IP
async def discover_vendors(request: Request, tender_file: UploadFile):
    """Discover vendors for a tender."""
    pass

# Handle rate limit exceeded
@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "retry_after": exc.retry_after
        }
    )
```

**3. Circuit Breaker Pattern**

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
def call_apollo_api(query: str):
    """Call Apollo API with circuit breaker.
    
    If 5 consecutive failures occur, circuit opens for 60 seconds.
    """
    response = requests.get(
        "https://api.apollo.io/search",
        params={"query": query},
        timeout=10
    )
    response.raise_for_status()
    return response.json()

# Fallback when circuit is open
try:
    results = call_apollo_api("software vendor")
except CircuitBreakerError:
    logger.warning("Apollo API circuit breaker open, using fallback")
    results = fallback_vendor_search(query)
```

### Audit Logging

**1. Execution Logging (Who Accessed What Data)**

```sql
-- execution_logs table (already exists)
CREATE TABLE execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id UUID REFERENCES tenders(id),
    stage VARCHAR(50),
    status VARCHAR(20),
    user_id VARCHAR(255),  -- API key hash or user identifier
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Index for audit queries
CREATE INDEX idx_execution_logs_user ON execution_logs(user_id, created_at);
CREATE INDEX idx_execution_logs_tender ON execution_logs(tender_id);
```

```python
def log_execution(
    tender_id: str,
    stage: str,
    status: str,
    user_id: str,
    ip_address: str,
    metadata: dict
):
    """Log pipeline execution for audit trail."""
    session.execute(
        """
        INSERT INTO execution_logs 
        (tender_id, stage, status, user_id, ip_address, metadata)
        VALUES (:tender_id, :stage, :status, :user_id, :ip_address, :metadata)
        """,
        {
            "tender_id": tender_id,
            "stage": stage,
            "status": status,
            "user_id": hashlib.sha256(user_id.encode()).hexdigest()[:16],
            "ip_address": ip_address,
            "metadata": json.dumps(metadata)
        }
    )
```

**2. API Call Logging**

```python
import logging
from datetime import datetime

class APILogger:
    """Log all external API calls for audit and debugging."""
    
    def __init__(self):
        self.logger = logging.getLogger("api_calls")
        handler = logging.FileHandler("logs/api_calls.log")
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        cost: float = 0.0
    ):
        """Log API call details."""
        self.logger.info(
            f"{service} | {method} {endpoint} | "
            f"status={status_code} | latency={latency_ms:.0f}ms | "
            f"cost=${cost:.4f}"
        )

# Usage
api_logger = APILogger()

def call_openai_with_logging(prompt: str):
    start = time.time()
    
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    
    latency = (time.time() - start) * 1000
    cost = calculate_cost(response.usage)
    
    api_logger.log_call(
        service="openai",
        endpoint="/v1/chat/completions",
        method="POST",
        status_code=200,
        latency_ms=latency,
        cost=cost
    )
    
    return response
```

**3. Security Event Logging**

```python
class SecurityLogger:
    """Log security-related events."""
    
    @staticmethod
    def log_failed_auth(user_id: str, ip_address: str):
        """Log failed authentication attempt."""
        logger.warning(
            f"Failed auth attempt | user={user_id} | ip={ip_address}",
            extra={
                "event_type": "auth_failure",
                "user_id": user_id,
                "ip_address": ip_address
            }
        )
    
    @staticmethod
    def log_suspicious_activity(user_id: str, activity: str):
        """Log suspicious activity (rate limit exceeded, invalid input, etc.)."""
        logger.error(
            f"Suspicious activity | user={user_id} | activity={activity}",
            extra={
                "event_type": "suspicious_activity",
                "user_id": user_id,
                "activity": activity
            }
        )
    
    @staticmethod
    def log_data_access(user_id: str, resource: str, action: str):
        """Log sensitive data access."""
        logger.info(
            f"Data access | user={user_id} | resource={resource} | action={action}",
            extra={
                "event_type": "data_access",
                "user_id": user_id,
                "resource": resource,
                "action": action
            }
        )

# Usage
if invalid_api_key:
    SecurityLogger.log_failed_auth(api_key, request.ip)
    raise HTTPException(status_code=401, detail="Invalid API key")
```

### Secure Deployment Practices

**1. HTTPS Only**

```python
# FastAPI - Force HTTPS in production
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# Nginx configuration
server {
    listen 80;
    server_name api.vendor-ai.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.vendor-ai.example.com;
    
    ssl_certificate /etc/letsencrypt/live/api.vendor-ai.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.vendor-ai.example.com/privkey.pem;
    
    # Strong SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

**2. Database Encryption at Rest**

```python
# PostgreSQL - Enable encryption at rest (AWS RDS)
resource "aws_db_instance" "vendor_ai" {
  identifier           = "vendor-ai-postgres"
  engine              = "postgres"
  instance_class      = "db.t3.medium"
  
  # Enable encryption
  storage_encrypted   = true
  kms_key_id         = aws_kms_key.postgres_key.arn
  
  # Enable automated backups (encrypted)
  backup_retention_period = 7
  
  # Enable audit logging
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
}

# Encrypt sensitive fields in application layer
from cryptography.fernet import Fernet

class FieldEncryption:
    """Encrypt sensitive fields before storing in database."""
    
    def __init__(self):
        # Store encryption key in secrets manager
        self.key = os.getenv("FIELD_ENCRYPTION_KEY").encode()
        self.cipher = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string."""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string."""
        return self.cipher.decrypt(ciphertext.encode()).decode()

# Usage
encryptor = FieldEncryption()
vendor.contact_email = encryptor.encrypt("contact@example.com")
```

**3. Network Isolation (VPC)**

```hcl
# Terraform - AWS VPC configuration
resource "aws_vpc" "vendor_ai" {
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Name = "vendor-ai-vpc"
  }
}

# Public subnet (for load balancer)
resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.vendor_ai.id
  cidr_block = "10.0.1.0/24"
  
  tags = {
    Name = "vendor-ai-public"
  }
}

# Private subnet (for application servers)
resource "aws_subnet" "private" {
  vpc_id     = aws_vpc.vendor_ai.id
  cidr_block = "10.0.2.0/24"
  
  tags = {
    Name = "vendor-ai-private"
  }
}

# Security group - Allow only necessary ports
resource "aws_security_group" "app" {
  vpc_id = aws_vpc.vendor_ai.id
  
  # Allow HTTPS from load balancer
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.1.0/24"]
  }
  
  # Allow PostgreSQL from app servers only
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.2.0/24"]
  }
  
  # Deny all other inbound traffic
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
  }
}
```

**4. Container Security Scanning**

```dockerfile
# Dockerfile - Use minimal base image
FROM python:3.11-slim

# Run as non-root user
RUN useradd -m -u 1000 appuser

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Run application
CMD ["uvicorn", "src.vendor_ai_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# GitHub Actions - Container scanning workflow
name: Security Scan

on: [push]

jobs:
  scan:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t vendor-ai:${{ github.sha }} .
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: vendor-ai:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

**5. Secrets Scanning**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package-lock.json

# Run on every commit to prevent secrets from being committed
```

```bash
# Initialize secrets baseline
detect-secrets scan > .secrets.baseline

# Update baseline when adding new secrets placeholders
detect-secrets scan --baseline .secrets.baseline
```

### Security Checklist

**Pre-Deployment:**
- [ ] All secrets in environment variables (never in code)
- [ ] `.env` file in `.gitignore`
- [ ] API keys rotated in last 90 days
- [ ] Database uses encrypted connections (SSL/TLS)
- [ ] HTTPS enforced for all endpoints
- [ ] Input validation on all user inputs
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output escaping)
- [ ] Rate limiting configured
- [ ] Audit logging enabled
- [ ] Container vulnerability scan passed
- [ ] Secrets scanning enabled (pre-commit hook)
- [ ] Non-root user in Docker containers
- [ ] Network isolation configured (VPC)
- [ ] Database encryption at rest enabled
- [ ] Backup and disaster recovery plan documented

**Post-Deployment:**
- [ ] Monitor audit logs for suspicious activity
- [ ] Review API usage patterns weekly
- [ ] Rotate API keys every 90 days
- [ ] Update dependencies monthly (security patches)
- [ ] Conduct security audit quarterly
- [ ] Review and update access permissions quarterly
- [ ] Test disaster recovery plan annually

---


### High-Level Architecture

The Tender Vendor AI Agent is a **multi-stage pipeline system** that automates vendor discovery and capability matching for government procurement tenders. The architecture follows a **plug-and-play design** with clear separation of concerns across eight primary stages:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TENDER VENDOR AI AGENT                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Ingestion  │───▶│  Document    │───▶│ Requirement  │              │
│  │   (SAM/CKAN) │    │  Parsing     │    │ Extraction   │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Vendor     │───▶│  Filtering   │───▶│  Enrichment  │              │
│  │  Discovery   │    │  & Deduping  │    │  (Contacts)  │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐                                   │
│  │  Capability  │───▶│    Output    │                                   │
│  │   Matching   │    │  Generation  │                                   │
│  └──────────────┘    └──────────────┘                                   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Design Principles

**1. Protocol-Driven Design**
- All modules implement typed protocols defined in `contracts.py`
- Enables **runtime polymorphism** without tight coupling
- New implementations can be swapped in without modifying pipeline logic

**2. Dependency Injection via Context**
- `PipelineContext` carries all module instances and configuration
- Modules receive dependencies explicitly, not via global state
- Facilitates testing, mocking, and parallel execution

**3. Fail-Safe Execution**
- Each stage has **graceful degradation** paths
- Missing data triggers fallbacks, not crashes
- Comprehensive logging at stage boundaries

**4. Incremental Enrichment**
- Data models support **partial population**
- Confidence scores track data quality at field level
- Vendors flow through pipeline even with incomplete data

**5. Cost-Aware Operations**
- LLM and API calls are **deferred until necessary**
- Filtering happens **before** expensive enrichment (see optimization section)
- Caching reduces redundant external requests

**6. Source-Agnostic Data Models**
- `TenderProfile` and `Vendor` models normalize heterogeneous sources
- US (SAM.gov) and Canada (CKAN) data flows through same pipeline
- Database schema unifies government contract formats

**7. Extensibility Over Configuration**
- New vendor sources: implement `VendorSource` protocol
- New enrichment providers: implement `EnrichmentProvider` protocol
- New output formats: extend `OutputGenerator`

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.11+ | Type hints, dataclasses, async support |
| **Database** | PostgreSQL 14+ | Transactional storage, JSONB support |
| **ORM** | SQLAlchemy 2.0 | Schema management, query optimization |
| **Migrations** | Alembic | Database version control |
| **LLM** | OpenAI GPT-4o | Requirement extraction, capability matching |
| **Document Processing** | PyPDF2, pdfplumber | PDF text/table extraction |
| **Web Scraping** | BeautifulSoup4, requests | Website content extraction |
| **Search APIs** | Serper (Google), DuckDuckGo | Vendor discovery, contact enrichment |
| **Government APIs** | SAM.gov API v2, CKAN API | Tender ingestion, vendor lookup |
| **CLI** | argparse | Command-line interface |
| **Dashboard** | Streamlit | Interactive UI for pipeline execution |

### System Boundaries

**What the System Does:**
- Ingests tender documents (PDF/Word/Excel) + API metadata
- Extracts structured requirements (NAICS, location, certifications, set-asides)
- Discovers vendors from government registries and web search
- Enriches vendor profiles with contacts and website content
- Scores vendor-tender fit using LLM-powered capability matching
- Outputs ranked vendor lists (Excel/CSV/JSON)

**What the System Does NOT Do:**
- Bid preparation or proposal writing
- Contract award prediction or outcome tracking
- Direct vendor communication or CRM functionality
- Real-time tender monitoring or alerting
- Legal compliance verification beyond set-aside filtering

### Deployment Models

**1. Local Execution (Current)**
- CLI: `python -m vendor_ai_agent.cli --tender data/tender.pdf`
- Dashboard: `streamlit run src/vendor_ai_agent/dashboard.py`
- Database: Local PostgreSQL instance

**2. Cloud Deployment (Planned)**
- Containerized via Docker (see `DEPLOYMENT.md`)
- Horizontal scaling for parallel tender processing
- Managed PostgreSQL (RDS/Cloud SQL)
- API gateway for programmatic access

---

## Module Architecture

The system consists of **60+ Python modules** organized into functional layers. This section provides a comprehensive breakdown of each module's responsibilities, interfaces, and dependencies.

### Directory Structure

```
src/vendor_ai_agent/
├── ingestion/           # Tender data acquisition from external APIs
├── modules/             # Core pipeline stages (20+ modules)
├── sources/             # Vendor discovery implementations (9 sources)
├── enrichment_providers/# Contact enrichment implementations (13 providers)
├── database/            # SQLAlchemy models and session management
├── cli.py              # Command-line interface
├── pipeline.py         # Pipeline orchestration
├── config.py           # Configuration dataclasses
├── contracts.py        # Protocol definitions for all stages
├── models.py           # Data models (TenderProfile, Vendor, etc.)
└── dashboard.py        # Streamlit UI
```

### 1. Ingestion Layer (`ingestion/`)

**Purpose:** Fetch tender metadata from government procurement APIs.

| Module | Class | Responsibilities | External Dependencies |
|--------|-------|------------------|----------------------|
| `sam.py` | `SamClient` | SAM.gov API v2 client (opportunities search) | `requests`, SAM.gov API key |
| `sam.py` | `UsSamIngestor` | Maps SAM.gov JSON to `api_metadata` dict | None |
| `canada.py` | `CanadaCkanClient` | CKAN API client for CanadaBuys datasets | `requests`, CKAN endpoint |
| `canada.py` | `CanadaBuysIngestor` | Maps CKAN records to `api_metadata` dict | None |
| `router.py` | `TenderIngestionRouter` | Routes ingestion requests to SAM/Canada based on source parameter | `ingestion.sam`, `ingestion.canada` |
| `base.py` | `BaseTenderIngestor` (ABC) | Abstract base class defining `ingest()` protocol | None |

**Key Interfaces:**
```python
class BaseTenderIngestor(ABC):
    @abstractmethod
    def ingest(self, tender_id: str, **kwargs) -> dict:
        """Returns api_metadata dict with normalized keys."""
```

**Data Flow:**
- Input: `tender_id` (SAM notice ID or CKAN reference number)
- Output: `api_metadata` dict with keys: `title`, `description`, `posted_date`, `response_deadline`, `naics_codes`, `set_asides`, `place_of_performance`, `contracting_office`

### 2. Document Processing Layer (`modules/document_parser.py`)

**Purpose:** Extract structured text and tables from uploaded tender documents.

| Component | Responsibilities | Supported Formats |
|-----------|------------------|-------------------|
| `TenderDocumentParser` | Orchestrates parsing across file types | PDF, DOCX, XLSX, TXT |
| `PdfParser` | Text extraction via PyPDF2 + pdfplumber for tables | `.pdf` |
| `WordParser` | Text extraction via python-docx | `.docx` |
| `ExcelParser` | Sheet/cell data via openpyxl | `.xlsx`, `.xls` |
| `TextParser` | Plain text passthrough | `.txt` |

**Output Data Model:**
```python
@dataclass
class TenderSection:
    section_type: str  # "text", "table", "header", "footer"
    content: str
    page_number: Optional[int]
    table_data: Optional[list[list[str]]]  # For section_type="table"
    metadata: dict  # Font size, position, etc.
```

**Key Features:**
- **Table Classification:** Heuristics identify NAICS tables, pricing tables, contact tables
- **Section Hierarchy:** Headers/footers separated from body content
- **Metadata Preservation:** Page numbers, font sizes, bounding boxes retained
- **Error Handling:** Corrupted PDFs trigger fallback to raw text extraction

### 3. Requirement Extraction Layer (`modules/requirement_extractor.py`)

**Purpose:** Transform unstructured document text into structured `TenderProfile` using LLM.

| Component | Responsibilities | LLM Usage |
|-----------|------------------|-----------|
| `RequirementExtractor` | GPT-4o prompt orchestration | ~3,000 tokens input, ~500 tokens output |
| `PromptBuilder` | Context-aware prompt construction | Injection of NAICS codes from tables |
| `ResponseParser` | JSON validation and error recovery | Handles malformed LLM output |

**Extraction Schema (`TenderProfile`):**
```python
@dataclass
class TenderProfile:
    tender_id: str
    title: str
    description: str
    project_summary: str  # LLM-generated descriptive phrase
    
    naics_codes: list[str]  # 6-digit codes
    required_certifications: list[str]  # e.g., ["8(a)", "HUBZone"]
    set_aside_status: Optional[str]  # "Small Business", "WOSB", etc.
    
    geographic_requirements: dict  # {"country": "US", "states": ["CA"], "zip_codes": []}
    minimum_years_experience: Optional[int]
    minimum_annual_revenue: Optional[float]
    
    estimated_contract_value: Optional[float]
    contract_duration_months: Optional[int]
    
    technical_keywords: list[str]  # Domain-specific terms
    required_licenses: list[str]
    
    response_deadline: Optional[datetime]
    contact_info: dict  # Contracting officer details
```

**LLM Prompt Strategy:**
- **System Message:** Role definition ("procurement requirements analyst")
- **Few-Shot Examples:** 3 annotated tender extractions
- **Context Injection:** Full document text + table data
- **Structured Output:** JSON schema enforcement via function calling
- **Fallback Logic:** Keyword-based extraction if LLM fails (see `_infer_project_type()`)

**Cost Optimization:**
- Reuses same LLM call for all fields (~$0.00000075/document marginal cost)
- Caches extractions in database to avoid re-processing
- Token limits enforced (max 8,000 tokens input)

### 4. Vendor Discovery Layer (`modules/vendor_discovery.py` + `sources/`)

**Purpose:** Aggregate vendors from multiple sources using pluggable `VendorSource` implementations.

**Core Module:**
| Component | Responsibilities |
|-----------|------------------|
| `VendorDiscovery` | Parallel execution of sources, deduplication by DUNS/UEI |
| `SourceRegistry` | Runtime registration of vendor sources |
| `SourcePriority` | Ordering logic (SAM.gov first, web search last) |

**Vendor Sources (9 Implementations):**

| Source | Module | Data Origin | Typical Results | API Cost |
|--------|--------|-------------|-----------------|----------|
| **SAM.gov Entity** | `sources/sam.py` | SAM.gov Entity Management API | 500-2,000 | Free |
| **USAspending.gov** | `sources/usaspending.py` | Federal contract awards | 1,000-5,000 | Free |
| **Canada Contracts** | `sources/canada_contracts.py` | Canadian contract history | 200-1,500 | Free |
| **Apollo Search** | `sources/apollo_search.py` | B2B database (250M+ companies) | 50-200 | $0.01/credit |
| **Serper Search** | `sources/serper.py` | Google search results | 10-50 | $0.002/query |
| **DuckDuckGo Search** | `sources/duckduckgo.py` | Web scraping | 5-20 | Free |
| **Thomas Net** | `sources/thomas_net.py` | Industrial supplier directory (planned) | 100-500 | Scraping |
| **Bloomberg Gov** | `sources/bloomberg_gov.py` | Government contractor database (planned) | 500-2,000 | Subscription |
| **Local Database** | `sources/database.py` | Previously discovered vendors | 10-100 | Free |

**Source Interface:**
```python
class VendorSource(Protocol):
    def search(self, profile: TenderProfile) -> list[Vendor]:
        """Discover vendors matching tender requirements."""
    
    @property
    def source_name(self) -> str:
        """Unique identifier for this source."""
    
    @property
    def priority(self) -> int:
        """Execution order (lower = earlier)."""
```

**Search Strategy:**
- **NAICS-based:** Query by primary NAICS code + geographic filters
- **Keyword-based:** Extract industry terms from `technical_keywords`
- **Historical:** Match against similar past tenders
- **Set-aside filtering:** Pre-filter by 8(a), HUBZone, SDVOSB, etc.

**Deduplication Logic:**
1. Normalize by UEI (Unique Entity Identifier) if present
2. Fall back to DUNS number
3. Fuzzy matching on company name + address (Levenshtein distance < 0.15)
4. Merge metadata from multiple sources (confidence score aggregation)

### 5. Filtering Layer (`modules/filtering.py`)

**Purpose:** Apply rule-based filters to reduce vendor pool before expensive enrichment.

**Filter Stages (Sequential):**

| Stage | Module | Elimination Rate | Logic |
|-------|--------|------------------|-------|
| **Duplicate Detection** | `duplicate_detector.py` | 30-50% | UEI/DUNS deduplication + fuzzy name matching |
| **Eligibility Check** | `eligibility_checker.py` | 10-20% | Active SAM registration, exclusions list, set-aside qualifications |
| **Geographic Match** | `geographic_matcher.py` | 20-40% | State/region requirements, international vendors for ITAR |
| **NAICS Alignment** | `naics_matcher.py` | 5-15% | Primary/secondary NAICS codes, SBA size standards |
| **Preliminary Ranking** | `preliminary_ranker.py` | Top 300 | Contract history, past performance, revenue size |

**Filtering Configuration:**
```python
@dataclass
class FilterConfig:
    max_vendors_after_filtering: int = 300
    enable_strict_geographic: bool = True
    require_active_sam_registration: bool = True
    allow_international_vendors: bool = False
    min_naics_match_confidence: float = 0.6
```

**Key Algorithms:**

**Geographic Matching:**
```python
def matches_geography(vendor: Vendor, requirements: dict) -> bool:
    if requirements.get("states"):
        return vendor.state in requirements["states"]
    if requirements.get("zip_codes"):
        return vendor.zip_code[:3] in [z[:3] for z in requirements["zip_codes"]]
    return True  # No geographic restriction
```

**NAICS Distance Scoring:**
- **Exact match (6 digits):** Score = 1.0
- **Subsector match (4 digits):** Score = 0.8
- **Industry group match (3 digits):** Score = 0.6
- **Sector match (2 digits):** Score = 0.4

### 6. Enrichment Layer (`modules/enrichment.py` + `enrichment_providers/`)

**Purpose:** Augment vendor records with contact details and website content.

**Core Module:**
| Component | Responsibilities |
|-----------|------------------|
| `VendorEnricher` | Sequential provider execution, skip logic |
| `EnrichmentCache` | 7-day TTL cache for website/contact data |
| `ConfidenceAggregator` | Merges confidence scores across providers |

**Enrichment Providers (13 Implementations):**

| Provider | Module | Data Acquired | Confidence | Cost |
|----------|--------|---------------|------------|------|
| **Apollo Email** | `apollo_enrichment.py` | Direct email, phone | 0.9 | $0.02/lookup |
| **Hunter.io** | `hunter_enrichment.py` | Email patterns, generic contacts | 0.7 | $0.01/lookup |
| **Serper Search** | `serper_search.py` | Google snippet extraction | 0.5 | $0.002/query |
| **DuckDuckGo Scrape** | `duckduckgo_scrape.py` | Website discovery + scraping | 0.6 | Free |
| **Website Scraper** | `website_scraper.py` | Contact page parsing | 0.8 | Free |
| **RocketReach** | `rocketreach.py` (planned) | Executive contacts | 0.9 | $0.05/credit |
| **ZoomInfo** | `zoominfo.py` (planned) | Corporate contacts | 0.95 | Subscription |
| **Clearbit** | `clearbit.py` (planned) | Company metadata | 0.85 | $0.03/lookup |
| **Static Fallback** | `static_contacts.py` | info@domain.com placeholders | 0.1 | Free |

**Provider Interface:**
```python
class EnrichmentProvider(Protocol):
    def enrich(self, vendor: Vendor) -> Vendor:
        """Augment vendor with contacts/metadata. Returns modified vendor."""
    
    @property
    def provider_name(self) -> str:
        """Unique identifier for this provider."""
    
    def should_skip(self, vendor: Vendor) -> bool:
        """Skip if vendor already has high-confidence data."""
```

**Enrichment Workflow:**
1. Check cache for recent enrichment (< 7 days)
2. Iterate providers in configured order
3. Skip provider if `should_skip()` returns True
4. Apply rate limiting (3 seconds + jitter for free APIs)
5. Validate extracted contacts (email RFC 5322, phone E.164)
6. Update confidence scores (max across providers)
7. Cache results with TTL

**Skip Logic Example:**
```python
def should_skip(self, vendor: Vendor) -> bool:
    if vendor.email and vendor.contact_confidence > 0.8:
        return True  # Already have high-confidence email
    return False
```

### 7. Capability Matching Layer (`modules/capability_matching.py`)

**Purpose:** Score vendor-tender fit using LLM-powered semantic matching.

| Component | Responsibilities | LLM Tokens |
|-----------|------------------|------------|
| `CapabilityMatcher` | Orchestrates scoring across vendor pool | ~1,500/vendor |
| `PromptBuilder` | Constructs context from tender + vendor data | N/A |
| `ScoreParser` | Extracts numeric scores + rationales from LLM output | N/A |
| `ReferenceExtractor` | Identifies specific contract references in rationale | N/A |

**Scoring Prompt Structure:**
```
System: You are a procurement analyst scoring vendor-tender fit.

User: 
Tender: [title, description, NAICS, certifications, location]
Vendor: [name, NAICS, past contracts, certifications, website_content excerpt]

Rate the vendor on a scale of 0-100 for this tender. Provide:
1. Overall score (0-100)
2. Dimension scores: capability (0-30), experience (0-30), certifications (0-20), geography (0-20)
3. Rationale (2-3 sentences)
4. Specific contract references supporting your score
```

**Output Data Model:**
```python
@dataclass
class VendorMatchResult:
    vendor: Vendor
    overall_score: float  # 0-100
    capability_score: float  # 0-30
    experience_score: float  # 0-30
    certification_score: float  # 0-20
    geographic_score: float  # 0-20
    rationale: str
    contract_references: list[str]
    confidence: float  # LLM confidence (0-1)
```

**Batch Processing:**
- Processes vendors in batches of 10 to optimize API throughput
- Parallel requests (max 5 concurrent) to reduce wall-clock time
- Retry logic for rate limit errors (exponential backoff)

**Cost Management:**
- ~$0.015 per vendor scored (GPT-4o pricing)
- $4.50 for 300-vendor shortlist
- Caching prevents re-scoring same vendor for same tender

### 8. Output Generation Layer (`modules/output_generator.py`)

**Purpose:** Serialize scored vendor list to multiple output formats.

| Format | Module | Features | Use Case |
|--------|--------|----------|----------|
| **Excel (XLSX)** | `excel_generator.py` | Multi-sheet, formulas, conditional formatting | Human review, pivot tables |
| **CSV** | `csv_generator.py` | Flattened structure, UTF-8 BOM | Bulk import, database loading |
| **JSON** | `json_generator.py` | Nested structure, full metadata | API consumption, further processing |

**Excel Output Structure:**
```
Sheet 1 - Vendor Rankings
├── Rank | Score | Company | NAICS | Certifications | Location | Contact
├── (Conditional formatting: green = score > 80, yellow = 60-80, red < 60)

Sheet 2 - Detailed Rationales
├── Company | Overall Score | Capability | Experience | Certification | Geography | Rationale | References

Sheet 3 - Tender Summary
├── Title | NAICS | Location | Set-Asides | Deadline | Total Vendors Scored
```

**CSV Flattening Logic:**
- Arrays → pipe-delimited strings (`naics_codes: "541330|541511|541512"`)
- Nested dicts → JSON-encoded strings
- Contact confidence → numeric column

### 9. Supporting Modules

| Module | Purpose |
|--------|---------|
| `contracts.py` | Protocol definitions for all pipeline stages (typed interfaces) |
| `models.py` | Data models (`TenderProfile`, `Vendor`, `VendorMatchResult`, etc.) |
| `config.py` | Configuration dataclasses (`LLMConfig`, `DiscoveryConfig`, etc.) |
| `pipeline.py` | Pipeline orchestration via `TenderVendorPipeline` and `PipelineContext` |
| `cli.py` | Command-line interface using argparse |
| `dashboard.py` | Streamlit UI for interactive pipeline execution |

---

## Pipeline Architecture

The pipeline executes as a **directed acyclic graph (DAG)** of stages, orchestrated by `TenderVendorPipeline` and coordinated through `PipelineContext`.

### Pipeline Orchestration

**Core Components:**

| Component | Responsibilities |
|-----------|------------------|
| `TenderVendorPipeline` | Main orchestrator; executes stages in order, handles errors |
| `PipelineContext` | Dependency injection container (modules + config + shared state) |
| `PipelineState` | Mutable state tracking (current stage, timing, errors) |
| `PipelineLogger` | Stage-boundary logging with timing and data counts |

**Pipeline Initialization:**
```python
pipeline = TenderVendorPipeline(
    config=RuntimeConfig(...),
    context=PipelineContext(
        document_parser=TenderDocumentParser(),
        requirement_extractor=RequirementExtractor(llm_config),
        vendor_discovery=VendorDiscovery(sources=[sam, canada, apollo]),
        vendor_filter=VendorFilter(filter_config),
        vendor_enricher=VendorEnricher(providers=[apollo, serper, static]),
        capability_matcher=CapabilityMatcher(llm_config),
        output_generator=OutputGenerator(output_config)
    )
)
```

### Stage Execution Flow

**Full Pipeline (8 Stages):**

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: TENDER INGESTION (Optional)                                     │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  tender_id (e.g., "SAM-12345" or "CKAN-67890")                   │
│ Action: TenderIngestionRouter → SAM/Canada API call                     │
│ Output: api_metadata dict (title, NAICS, deadline, etc.)                │
│ Timing: 2-5 seconds                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: DOCUMENT PARSING                                                │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  tender_files (PDF/DOCX/XLSX paths)                              │
│ Action: TenderDocumentParser → text + table extraction                  │
│ Output: List[TenderSection] (text blocks, tables, metadata)             │
│ Timing: 10-60 seconds (depends on page count)                           │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: REQUIREMENT EXTRACTION                                          │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  TenderSections + api_metadata                                    │
│ Action: RequirementExtractor → GPT-4o structured extraction             │
│ Output: TenderProfile (NAICS, location, certifications, etc.)           │
│ Timing: 5-15 seconds (LLM latency)                                      │
│ Cost:   ~$0.003 per tender                                               │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: VENDOR DISCOVERY                                                │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  TenderProfile                                                    │
│ Action: VendorDiscovery → parallel source queries (SAM, CKAN, Apollo)   │
│ Output: List[Vendor] (2,000-10,000 raw vendors)                         │
│ Timing: 30-120 seconds (parallel API calls)                             │
│ Cost:   $0.01-0.50 (Apollo credits)                                     │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: FILTERING & DEDUPLICATION                                       │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  List[Vendor] (raw)                                               │
│ Action: VendorFilter → duplicate detection → eligibility → geography    │
│         → NAICS matching → preliminary ranking → top 300                │
│ Output: List[Vendor] (filtered to top 300)                              │
│ Timing: 10-30 seconds (rule-based, no LLM)                              │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 6: CONTACT ENRICHMENT                                              │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  List[Vendor] (filtered 300)                                     │
│ Action: VendorEnricher → Apollo → Serper → DuckDuckGo → static fallback │
│ Output: List[Vendor] (with email, phone, website_content)               │
│ Timing: 15-45 minutes (rate limiting on free APIs)                      │
│ Cost:   $6-18 (Apollo/Hunter lookups)                                   │
│ Optimization: Only enriches post-filtering (94% time/cost savings)      │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 7: CAPABILITY MATCHING                                             │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  TenderProfile + List[Vendor] (enriched)                         │
│ Action: CapabilityMatcher → GPT-4o scoring (batch of 10, parallel)      │
│ Output: List[VendorMatchResult] (scores, rationales, references)        │
│ Timing: 5-10 minutes (LLM latency, 300 vendors)                         │
│ Cost:   $4.50 (300 vendors × $0.015/vendor)                             │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 8: OUTPUT GENERATION                                               │
│ ─────────────────────────────────────────────────────────────────────── │
│ Input:  List[VendorMatchResult] (sorted by score descending)            │
│ Action: OutputGenerator → Excel + CSV + JSON serialization              │
│ Output: tender_vendors.xlsx, tender_vendors.csv, tender_vendors.json    │
│ Timing: 5-10 seconds (file I/O)                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Total Pipeline Timing:**
- **Optimized Flow:** 25-35 minutes (post-optimization)
- **Previous Flow:** 7-8 hours (enriched before filtering)

**Total Pipeline Cost:**
- **Optimized:** $11-22 per tender
- **Previous:** $300+ per tender

### Stage Dependencies

**Dependency Graph:**
```
api_metadata ─┐
              ├──→ TenderProfile ──→ Discovery ──→ Filtering ──→ Enrichment ──→ Matching ──→ Output
doc_sections ─┘
```

**Key Insights:**
1. **Ingestion is optional** (can start with uploaded PDFs only)
2. **Filtering before enrichment** is critical for cost/time optimization
3. **Enrichment and Matching can run in parallel** (future optimization)
4. **Output generation is independent** (can regenerate without re-running pipeline)

### Error Handling Per Stage

| Stage | Error Type | Handling Strategy |
|-------|------------|-------------------|
| Ingestion | API timeout, 404 | Graceful skip; proceed with doc parsing only |
| Parsing | Corrupted PDF | Fallback to raw text extraction |
| Extraction | LLM timeout | Retry once; fall back to keyword extraction |
| Discovery | Source API error | Skip failed source; continue with available sources |
| Filtering | Invalid vendor data | Log warning; exclude vendor from results |
| Enrichment | Provider rate limit | Exponential backoff (max 3 retries); skip provider |
| Matching | LLM rate limit | Batch retry with exponential backoff |
| Output | File write error | Retry with temp directory; fail pipeline if persistent |

**Global Error Recovery:**
- Each stage catches exceptions and logs to `pipeline.log`
- Pipeline continues to next stage unless critical failure (e.g., no vendors discovered)
- Final report includes stage-level error summary

### Pipeline Configuration

**Runtime Configuration:**
```python
@dataclass
class RuntimeConfig:
    llm: LLMConfig
    discovery: DiscoveryConfig
    enrichment: EnrichmentConfig
    filtering: FilterConfig
    output: OutputConfig
    
    sam_api_key: Optional[str]
    apollo_api_key: Optional[str]
    hunter_api_key: Optional[str]
    serper_api_key: Optional[str]
    
    database_url: str
    log_level: str = "INFO"
```

**Pipeline Execution Modes:**

1. **Full Pipeline (Default):**
   ```python
   pipeline.run(tender_id="SAM-12345", tender_files=["rfp.pdf"])
   ```

2. **Document-Only Mode:**
   ```python
   pipeline.run(tender_files=["rfp.pdf"])  # Skip ingestion
   ```

3. **API-Only Mode:**
   ```python
   pipeline.run(tender_id="SAM-12345")  # No document parsing
   ```

4. **Cached Extraction Mode:**
   ```python
   pipeline.run(tender_id="SAM-12345", use_cached_extraction=True)
   ```

### Parallelization Strategy

**Current Implementation (Sequential):**
- Stages execute one after another
- Within-stage parallelization:
  - **Discovery:** Parallel source queries (max 5 concurrent)
  - **Enrichment:** Serial provider execution (rate limiting)
  - **Matching:** Parallel LLM requests (batch of 10)

**Future Optimization (Parallel Stages):**
```python
async def run_optimized(self):
    api_metadata, doc_sections = await asyncio.gather(
        self.ingest_async(),
        self.parse_async()
    )
    
    tender_profile = await self.extract_async(api_metadata, doc_sections)
    
    discovered = await self.discover_async(tender_profile)
    filtered = await self.filter_async(discovered)
    
    enriched, preliminary_scores = await asyncio.gather(
        self.enrich_async(filtered),
        self.preliminary_score_async(filtered)  # LLM-free fast scoring
    )
    
    matches = await self.match_async(tender_profile, enriched)
    await self.output_async(matches)
```

**Estimated Speedup:** 40-50% reduction in wall-clock time (25 min → 12-15 min)

---

## Data Flow

This section traces how data transforms through each pipeline stage, showing schema evolution and key transformations.

### Data Model Evolution

**Stage-by-Stage Schema:**

```
INGESTION
├─ Input:  tender_id (string)
├─ API Response: JSON from SAM.gov/CKAN
└─ Output: api_metadata (dict)
     ├─ title: str
     ├─ description: str
     ├─ posted_date: datetime
     ├─ response_deadline: datetime
     ├─ naics_codes: list[str]
     ├─ set_asides: list[str]
     ├─ place_of_performance: dict
     └─ contracting_office: dict

DOCUMENT PARSING
├─ Input:  tender_files (list[Path])
├─ Raw PDF/DOCX bytes → Text + Tables
└─ Output: doc_sections (list[TenderSection])
     ├─ section_type: "text" | "table" | "header" | "footer"
     ├─ content: str
     ├─ page_number: int
     ├─ table_data: list[list[str]] (if section_type="table")
     └─ metadata: dict (font_size, position, etc.)

REQUIREMENT EXTRACTION
├─ Input:  api_metadata + doc_sections
├─ LLM Processing: GPT-4o structured extraction
└─ Output: TenderProfile
     ├─ tender_id: str
     ├─ title: str
     ├─ description: str
     ├─ project_summary: str (LLM-generated)
     ├─ naics_codes: list[str] (6-digit codes)
     ├─ required_certifications: list[str]
     ├─ set_aside_status: Optional[str]
     ├─ geographic_requirements: dict
     ├─ minimum_years_experience: Optional[int]
     ├─ minimum_annual_revenue: Optional[float]
     ├─ estimated_contract_value: Optional[float]
     ├─ contract_duration_months: Optional[int]
     ├─ technical_keywords: list[str]
     ├─ required_licenses: list[str]
     ├─ response_deadline: Optional[datetime]
     └─ contact_info: dict

VENDOR DISCOVERY
├─ Input:  TenderProfile
├─ Source Queries: Parallel API calls to SAM, CKAN, Apollo, Serper
└─ Output: discovered_vendors (list[Vendor], 2,000-10,000 items)
     ├─ vendor_id: str (UEI or generated UUID)
     ├─ name: str
     ├─ duns: Optional[str]
     ├─ uei: Optional[str]
     ├─ naics_codes: list[str]
     ├─ address: dict (street, city, state, zip, country)
     ├─ certifications: list[str]
     ├─ past_contracts: list[dict] (from SAM/CKAN)
     ├─ annual_revenue: Optional[float]
     ├─ employee_count: Optional[int]
     ├─ sam_registration_status: Optional[str]
     ├─ sam_expiration_date: Optional[datetime]
     ├─ source: str (e.g., "sam_entity", "canada_contracts")
     └─ discovery_metadata: dict (query used, confidence score)

FILTERING & DEDUPLICATION
├─ Input:  discovered_vendors (list[Vendor])
├─ Filter Steps:
│   1. Duplicate detection (UEI/DUNS + fuzzy name matching) → 50% reduction
│   2. Eligibility check (active SAM, not on exclusions list) → 20% reduction
│   3. Geographic matching (state/region requirements) → 30% reduction
│   4. NAICS alignment (primary/secondary codes) → 10% reduction
│   5. Preliminary ranking (contract history, revenue) → top 300
└─ Output: filtered_vendors (list[Vendor], ~300 items)
     ├─ (Same schema as discovered_vendors)
     ├─ filter_metadata: dict
     │   ├─ duplicate_cluster_id: Optional[str]
     │   ├─ eligibility_flags: dict (active_sam, not_excluded)
     │   ├─ geographic_match_score: float
     │   ├─ naics_match_score: float
     │   └─ preliminary_rank: int
     └─ filter_reason: Optional[str] (if excluded)

CONTACT ENRICHMENT
├─ Input:  filtered_vendors (list[Vendor])
├─ Provider Calls: Apollo → Serper → DuckDuckGo → Static fallback
└─ Output: enriched_vendors (list[Vendor], ~300 items)
     ├─ (All fields from filtered_vendors)
     ├─ email: Optional[str]
     ├─ phone: Optional[str]
     ├─ website: Optional[str]
     ├─ website_content: Optional[str] (first 2,000 chars)
     ├─ contact_confidence: float (0-1, max across providers)
     ├─ enrichment_metadata: dict
     │   ├─ providers_used: list[str]
     │   ├─ provider_scores: dict[str, float]
     │   ├─ last_enriched: datetime
     │   └─ cache_hit: bool
     └─ enrichment_flags: dict (high_value_supplier, frequent_supplier)

CAPABILITY MATCHING
├─ Input:  TenderProfile + enriched_vendors (list[Vendor])
├─ LLM Scoring: GPT-4o per-vendor capability analysis
└─ Output: vendor_matches (list[VendorMatchResult], ~300 items)
     ├─ vendor: Vendor (full enriched data)
     ├─ overall_score: float (0-100)
     ├─ capability_score: float (0-30)
     ├─ experience_score: float (0-30)
     ├─ certification_score: float (0-20)
     ├─ geographic_score: float (0-20)
     ├─ rationale: str (2-3 sentences from LLM)
     ├─ contract_references: list[str] (specific past contracts cited)
     ├─ confidence: float (LLM confidence 0-1)
     └─ matching_metadata: dict
         ├─ model_used: str (e.g., "gpt-4o-2024-11-20")
         ├─ tokens_used: int
         ├─ match_timestamp: datetime
         └─ llm_reasoning_tokens: int

OUTPUT GENERATION
├─ Input:  vendor_matches (list[VendorMatchResult])
├─ Sorting: By overall_score descending
└─ Output: Files
     ├─ tender_vendors.xlsx (3 sheets: Rankings, Rationales, Summary)
     ├─ tender_vendors.csv (flattened structure)
     └─ tender_vendors.json (full nested structure)
```

### Key Transformations

**1. NAICS Code Normalization**
```
SAM.gov API → "541330 - Engineering Services"
CKAN API    → "541330"
LLM Extract → "Engineering (541330)"
                    ↓
          Normalized: ["541330"]
```

**2. Address Standardization**
```
SAM.gov:  {"addressLine1": "123 Main St", "city": "San Francisco", ...}
CKAN:     {"address": "123 Main St, San Francisco, CA"}
Apollo:   {"street": "123 Main St", "city": "San Francisco", ...}
                    ↓
          Unified: {"street": "123 Main St", "city": "San Francisco", 
                   "state": "CA", "zip": "94102", "country": "US"}
```

**3. Certification Mapping**
```
SAM.gov:  ["Small Business", "8(a)", "HUBZone"]
CKAN:     ["Indigenous-owned", "Small Business"]
LLM:      ["minority-owned", "veteran-owned"]
                    ↓
          Normalized: ["8(a)", "HUBZone", "SDVOSB", "Small Business"]
```

**4. Contact Confidence Aggregation**
```
Apollo:      email (confidence=0.9), phone (confidence=0.85)
Serper:      email (confidence=0.5), no phone
DuckDuckGo:  no email, phone (confidence=0.6)
Static:      email (confidence=0.1), no phone
                    ↓
          Final: email (confidence=0.9), phone (confidence=0.85)
          (max confidence across providers)
```

### Data Persistence

**Database Integration Points:**

| Stage | Database Operation | Tables Affected |
|-------|-------------------|-----------------|
| Ingestion | INSERT tender record | `tenders` |
| Parsing | INSERT sections | `tender_sections` |
| Extraction | UPDATE tender with profile | `tenders.profile_data` (JSONB) |
| Discovery | UPSERT vendors | `vendors`, `vendor_sources` |
| Filtering | INSERT filter results | `vendor_filtering_results` |
| Enrichment | UPDATE vendor contacts | `vendors.contact_data` (JSONB) |
| Matching | INSERT match results | `vendor_matches` |

**Caching Strategy:**

| Data Type | Cache Duration | Cache Key |
|-----------|----------------|-----------|
| API metadata | 24 hours | `tender:{tender_id}:metadata` |
| Document sections | 7 days | `tender:{tender_id}:sections` |
| Requirement extraction | 30 days | `tender:{tender_id}:profile` |
| Vendor discovery | 7 days | `vendor:{uei}:discovery` |
| Enrichment data | 7 days | `vendor:{uei}:contacts` |
| Capability scores | 30 days | `match:{tender_id}:{vendor_id}` |

**Cache Invalidation:**
- Manual: CLI command `python -m vendor_ai_agent.cli clear-cache --tender <id>`
- Automatic: Tender document upload triggers cache clear for that tender
- Time-based: TTL expiration (see table above)

### Data Flow Diagram

**Detailed Flow with Confidence Scores:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CONFIDENCE SCORE PROPAGATION                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  API Metadata          Document Parsing        LLM Extraction            │
│  (confidence=1.0)      (confidence=0.95)       (confidence=0.85)         │
│         │                     │                       │                  │
│         └──────────┬──────────┘                       │                  │
│                    ↓                                  ↓                  │
│             TenderProfile                                                │
│             (confidence = weighted avg = 0.92)                           │
│                    │                                                     │
│                    ↓                                                     │
│          ┌─────────┴─────────┐                                          │
│          ↓                   ↓                                          │
│   Vendor Discovery      Vendor Discovery                                │
│   Source 1 (SAM)        Source 2 (Apollo)                               │
│   confidence=0.95       confidence=0.75                                 │
│          │                   │                                          │
│          └─────────┬─────────┘                                          │
│                    ↓                                                     │
│             Merged Vendor Records                                       │
│             (confidence = max per field)                                │
│                    │                                                     │
│                    ↓                                                     │
│              Filtering                                                  │
│              (no confidence change)                                     │
│                    │                                                     │
│                    ↓                                                     │
│          ┌─────────┴─────────┐                                          │
│          ↓                   ↓                                          │
│   Enrichment Provider 1  Enrichment Provider 2                          │
│   Apollo (conf=0.9)      Serper (conf=0.5)                             │
│          │                   │                                          │
│          └─────────┬─────────┘                                          │
│                    ↓                                                     │
│         Enriched Vendor (contact_confidence = max = 0.9)                │
│                    │                                                     │
│                    ↓                                                     │
│         Capability Matching (LLM confidence=0.8)                        │
│                    │                                                     │
│                    ↓                                                     │
│     VendorMatchResult (final_confidence = 0.8 × 0.9 = 0.72)            │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Extensibility Points

The system is designed for **plug-and-play extensibility** at every pipeline stage. New implementations can be added without modifying existing code.

### 1. Protocol-Based Design

All extensibility points are defined via Python `Protocol` classes in `contracts.py`:

```python
from typing import Protocol

class VendorSource(Protocol):
    def search(self, profile: TenderProfile) -> list[Vendor]:
        """Discover vendors matching tender requirements."""
    
    @property
    def source_name(self) -> str:
        """Unique identifier for this source."""
    
    @property
    def priority(self) -> int:
        """Execution order (lower = earlier)."""

class EnrichmentProvider(Protocol):
    def enrich(self, vendor: Vendor) -> Vendor:
        """Augment vendor with contacts/metadata."""
    
    @property
    def provider_name(self) -> str:
        """Unique identifier for this provider."""
    
    def should_skip(self, vendor: Vendor) -> bool:
        """Skip if vendor already has sufficient data."""

class CapabilityMatcher(Protocol):
    def score(self, profile: TenderProfile, vendors: list[Vendor]) -> list[VendorMatchResult]:
        """Score vendor-tender fit."""
```

**Benefits:**
- **Type safety:** Static type checkers validate implementations
- **No inheritance required:** Duck typing via structural subtyping
- **Runtime polymorphism:** Swap implementations without pipeline changes

### 2. Adding a New Vendor Source

**Step 1: Implement the Protocol**

```python
from vendor_ai_agent.contracts import VendorSource
from vendor_ai_agent.models import TenderProfile, Vendor

class LinkedInVendorSource:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def search(self, profile: TenderProfile) -> list[Vendor]:
        results = []
        for naics in profile.naics_codes:
            response = self._query_linkedin_api(naics, profile.geographic_requirements)
            for company in response['companies']:
                results.append(Vendor(
                    vendor_id=company['id'],
                    name=company['name'],
                    naics_codes=[naics],
                    address=self._parse_address(company),
                    source="linkedin_search"
                ))
        return results
    
    @property
    def source_name(self) -> str:
        return "linkedin_search"
    
    @property
    def priority(self) -> int:
        return 30  # After SAM (10), before web search (50)
    
    def _query_linkedin_api(self, naics: str, geo: dict):
        pass  # Implementation details
```

**Step 2: Register with Pipeline**

```python
from vendor_ai_agent.pipeline import TenderVendorPipeline, PipelineContext
from vendor_ai_agent.modules.vendor_discovery import VendorDiscovery

linkedin_source = LinkedInVendorSource(api_key="...")

context = PipelineContext(
    vendor_discovery=VendorDiscovery(sources=[
        sam_source,
        canada_source,
        linkedin_source,  # New source added
        apollo_source
    ])
)

pipeline = TenderVendorPipeline(config=..., context=context)
```

**Step 3: No Other Changes Required**
- Filtering stage automatically processes new vendors
- Enrichment stage applies to all vendors
- Output generation includes new source attribution

### 3. Adding a New Enrichment Provider

**Step 1: Implement the Protocol**

```python
from vendor_ai_agent.contracts import EnrichmentProvider
from vendor_ai_agent.models import Vendor

class ClearbitEnrichmentProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def enrich(self, vendor: Vendor) -> Vendor:
        if not vendor.website:
            return vendor  # Can't enrich without website
        
        response = self._query_clearbit_api(vendor.website)
        
        if response.get('email'):
            vendor.email = response['email']
            vendor.contact_confidence = max(vendor.contact_confidence or 0, 0.85)
        
        if response.get('phone'):
            vendor.phone = response['phone']
        
        vendor.enrichment_metadata['clearbit'] = {
            'confidence': 0.85,
            'timestamp': datetime.now().isoformat()
        }
        
        return vendor
    
    @property
    def provider_name(self) -> str:
        return "clearbit"
    
    def should_skip(self, vendor: Vendor) -> bool:
        return (vendor.email and 
                vendor.contact_confidence and 
                vendor.contact_confidence > 0.9)
    
    def _query_clearbit_api(self, domain: str):
        pass  # API call implementation
```

**Step 2: Register with Pipeline**

```python
from vendor_ai_agent.modules.enrichment import VendorEnricher

clearbit_provider = ClearbitEnrichmentProvider(api_key="...")

context = PipelineContext(
    vendor_enricher=VendorEnricher(providers=[
        apollo_provider,
        clearbit_provider,  # New provider added
        serper_provider,
        static_fallback
    ])
)
```

**Provider Execution Order:**
- Providers run sequentially in list order
- `should_skip()` prevents redundant API calls
- Confidence scores automatically aggregate (max per field)

### 4. Adding a Custom Capability Matcher

**Example: Embedding-Based Matcher**

```python
from vendor_ai_agent.contracts import CapabilityMatcher
from vendor_ai_agent.models import TenderProfile, Vendor, VendorMatchResult
import openai

class EmbeddingCapabilityMatcher:
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.cache = {}
    
    def score(self, profile: TenderProfile, vendors: list[Vendor]) -> list[VendorMatchResult]:
        tender_embedding = self._get_embedding(self._profile_to_text(profile))
        
        results = []
        for vendor in vendors:
            vendor_embedding = self._get_embedding(self._vendor_to_text(vendor))
            similarity = self._cosine_similarity(tender_embedding, vendor_embedding)
            
            results.append(VendorMatchResult(
                vendor=vendor,
                overall_score=similarity * 100,
                capability_score=similarity * 30,
                experience_score=self._experience_score(vendor),
                certification_score=self._cert_score(vendor, profile),
                geographic_score=self._geo_score(vendor, profile),
                rationale=f"Semantic similarity: {similarity:.2%}",
                contract_references=[],
                confidence=0.7  # Embedding-based confidence
            ))
        
        return sorted(results, key=lambda r: r.overall_score, reverse=True)
    
    def _get_embedding(self, text: str):
        if text in self.cache:
            return self.cache[text]
        response = openai.Embedding.create(input=text, model=self.model)
        embedding = response['data'][0]['embedding']
        self.cache[text] = embedding
        return embedding
    
    def _cosine_similarity(self, a, b):
        pass  # Vector math implementation
```

**Hybrid Matcher (LLM + Embeddings):**

```python
class HybridCapabilityMatcher:
    def __init__(self, llm_matcher: CapabilityMatcher, embedding_matcher: CapabilityMatcher):
        self.llm = llm_matcher
        self.embedding = embedding_matcher
    
    def score(self, profile: TenderProfile, vendors: list[Vendor]) -> list[VendorMatchResult]:
        embedding_results = self.embedding.score(profile, vendors[:50])
        top_50 = [r.vendor for r in embedding_results]
        
        llm_results = self.llm.score(profile, top_50)
        
        return llm_results
```

**Cost Optimization:** Embedding-based pre-filtering (50 vendors) → LLM scoring (top 50 only)

### 5. Adding Custom Filters

**Step 1: Implement Filter Logic**

```python
from vendor_ai_agent.models import Vendor, TenderProfile

class ITARComplianceFilter:
    def filter(self, profile: TenderProfile, vendors: list[Vendor]) -> list[Vendor]:
        if not self._is_itar_contract(profile):
            return vendors  # No ITAR restrictions
        
        compliant_vendors = []
        for vendor in vendors:
            if self._is_us_vendor(vendor) and self._no_foreign_ownership(vendor):
                compliant_vendors.append(vendor)
            else:
                vendor.filter_metadata['itar_compliant'] = False
                vendor.filter_reason = "ITAR: Non-US or foreign-owned"
        
        return compliant_vendors
    
    def _is_itar_contract(self, profile: TenderProfile) -> bool:
        keywords = ["defense", "munitions", "classified", "security clearance"]
        return any(kw in profile.description.lower() for kw in keywords)
    
    def _is_us_vendor(self, vendor: Vendor) -> bool:
        return vendor.address.get('country') == 'US'
    
    def _no_foreign_ownership(self, vendor: Vendor) -> bool:
        pass  # Check SAM.gov foreign ownership flags
```

**Step 2: Add to Filter Chain**

```python
from vendor_ai_agent.modules.filtering import VendorFilter

filter_config = FilterConfig(...)

vendor_filter = VendorFilter(
    config=filter_config,
    custom_filters=[
        ITARComplianceFilter(),
        MyCustomFilter()
    ]
)
```

### 6. Adding Output Formats

**Example: PowerPoint Presentation**

```python
from pptx import Presentation
from vendor_ai_agent.models import VendorMatchResult

class PowerPointOutputGenerator:
    def generate(self, matches: list[VendorMatchResult], output_path: Path):
        prs = Presentation()
        
        title_slide = prs.slides.add_slide(prs.slide_layouts[0])
        title_slide.shapes.title.text = "Top Vendor Matches"
        
        for i, match in enumerate(matches[:10], 1):
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = f"{i}. {match.vendor.name}"
            
            content = slide.placeholders[1].text_frame
            content.text = f"Score: {match.overall_score:.0f}/100\n"
            content.text += f"Location: {match.vendor.address['city']}, {match.vendor.address['state']}\n"
            content.text += f"NAICS: {', '.join(match.vendor.naics_codes)}\n\n"
            content.text += f"Rationale: {match.rationale}"
        
        prs.save(output_path)
```

**Register with OutputGenerator:**

```python
from vendor_ai_agent.modules.output_generator import OutputGenerator

output_gen = OutputGenerator(
    config=output_config,
    custom_generators=[
        PowerPointOutputGenerator()
    ]
)
```

### 7. Plugin Architecture (Future)

**Planned Plugin System:**

```python
from vendor_ai_agent.plugins import Plugin, PluginManager

class MyCustomPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    
    def on_pipeline_start(self, context: PipelineContext):
        pass  # Hook into pipeline start
    
    def on_stage_complete(self, stage_name: str, data: Any):
        pass  # Hook into stage completion
    
    def on_pipeline_complete(self, results: list[VendorMatchResult]):
        pass  # Hook into pipeline completion

plugin_manager = PluginManager()
plugin_manager.register(MyCustomPlugin())

pipeline = TenderVendorPipeline(config=..., context=..., plugins=plugin_manager)
```

**Plugin Use Cases:**
- Custom logging/monitoring (send metrics to Datadog)
- Real-time notifications (Slack alerts on stage completion)
- Data export (push results to external CRM)
- Custom validation (business-specific rules)

### 8. Configuration-Driven Extensibility

**Dynamic Source Loading:**

```yaml
vendor_sources:
  - type: sam_entity
    priority: 10
    config:
      api_key: ${SAM_API_KEY}
  
  - type: apollo_search
    priority: 20
    config:
      api_key: ${APOLLO_API_KEY}
      max_results: 500
  
  - type: custom.linkedin_source
    priority: 30
    module: my_company.sources.linkedin
    class: LinkedInVendorSource
    config:
      api_key: ${LINKEDIN_API_KEY}
```

**Runtime Loading:**

```python
from importlib import import_module

def load_sources_from_config(config: dict) -> list[VendorSource]:
    sources = []
    for source_config in config['vendor_sources']:
        if '.' in source_config['type']:
            module_path, class_name = source_config['type'].rsplit('.', 1)
            module = import_module(module_path)
            source_class = getattr(module, class_name)
        else:
            source_class = BUILTIN_SOURCES[source_config['type']]
        
        source = source_class(**source_config['config'])
        sources.append(source)
    
    return sources
```

---

## Configuration System

The configuration system uses **nested dataclasses** with environment variable injection, precedence rules, and validation.

### Configuration Architecture

**Hierarchy:**

```
RuntimeConfig (top-level)
├── LLMConfig
│   ├── primary_model: str
│   ├── fallback_model: str
│   ├── temperature: float
│   ├── max_tokens: int
│   └── timeout: int
├── DiscoveryConfig
│   ├── target_vendor_count: int
│   ├── enabled_sources: list[str]
│   ├── source_priorities: dict[str, int]
│   └── parallel_requests: int
├── EnrichmentConfig
│   ├── max_vendors_to_enrich: int
│   ├── enabled_providers: list[str]
│   ├── provider_order: list[str]
│   ├── cache_ttl_days: int
│   └── rate_limit_seconds: dict[str, float]
├── FilterConfig
│   ├── max_vendors_after_filtering: int
│   ├── enable_strict_geographic: bool
│   ├── require_active_sam_registration: bool
│   ├── allow_international_vendors: bool
│   ├── min_naics_match_confidence: float
│   └── enable_preliminary_ranking: bool
├── OutputConfig
│   ├── generate_excel: bool
│   ├── generate_csv: bool
│   ├── generate_json: bool
│   ├── default_filename: str
│   └── output_dir: Path
├── API Keys
│   ├── sam_api_key: Optional[str]
│   ├── apollo_api_key: Optional[str]
│   ├── hunter_api_key: Optional[str]
│   ├── serper_api_key: Optional[str]
│   └── openai_api_key: str
└── System Settings
    ├── database_url: str
    ├── log_level: str
    ├── log_file: Path
    └── cache_dir: Path
```

### Configuration Sources (Precedence Order)

**1. Explicit Constructor Arguments (Highest)**
```python
config = RuntimeConfig(
    llm=LLMConfig(primary_model="gpt-4o-mini"),
    discovery=DiscoveryConfig(target_vendor_count=500)
)
```

**2. Environment Variables**
```bash
export OPENAI_API_KEY="sk-..."
export SAM_API_KEY="..."
export TENDER_AGENT_LLM_MODEL="gpt-4o"
export TENDER_AGENT_TARGET_VENDORS=300
export TENDER_AGENT_LOG_LEVEL="DEBUG"
```

**3. Configuration File (.env or config.yaml)**
```yaml
llm:
  primary_model: gpt-4o
  fallback_model: gpt-4o-mini
  temperature: 0.3
  max_tokens: 2000

discovery:
  target_vendor_count: 300
  enabled_sources:
    - sam_entity
    - canada_contracts
    - apollo_search
  
enrichment:
  max_vendors_to_enrich: 300
  enabled_providers:
    - apollo_enrichment
    - serper_search
    - static_fallback
  cache_ttl_days: 7
  rate_limit_seconds:
    duckduckgo: 3.0
    serper: 0.5

filtering:
  max_vendors_after_filtering: 300
  enable_strict_geographic: true
  min_naics_match_confidence: 0.6

output:
  generate_excel: true
  generate_csv: true
  generate_json: true
  output_dir: ./output

database_url: postgresql://localhost/vendor_ai_agent
log_level: INFO
```

**4. Defaults (Lowest)**
```python
@dataclass
class LLMConfig:
    primary_model: str = "gpt-4o-2024-11-20"
    fallback_model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 30
```

### Configuration Loading

**Automatic Loading:**
```python
from vendor_ai_agent.config import load_config

config = load_config()
```

**Load Order:**
1. Load defaults from dataclass definitions
2. Load `.env` file if present (using python-dotenv)
3. Load `config.yaml` if present (overrides .env)
4. Apply environment variables (overrides config.yaml)
5. Apply constructor arguments (overrides everything)

**Validation:**
```python
from vendor_ai_agent.config import RuntimeConfig, ConfigurationError

try:
    config = RuntimeConfig(
        llm=LLMConfig(temperature=1.5),  # Invalid
        openai_api_key=""  # Missing
    )
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

**Validation Rules:**
- `openai_api_key` required if LLM-based stages enabled
- `temperature` must be 0-2
- `target_vendor_count` must be > 0
- `cache_ttl_days` must be > 0
- `output_dir` must be writable

### Configuration Profiles

**Conservative Profile (Production Default):**
```python
CONSERVATIVE_CONFIG = RuntimeConfig(
    llm=LLMConfig(
        primary_model="gpt-4o",
        temperature=0.2  # Low randomness
    ),
    discovery=DiscoveryConfig(
        target_vendor_count=300,
        enabled_sources=["sam_entity", "canada_contracts"]  # Government only
    ),
    enrichment=EnrichmentConfig(
        enabled_providers=["apollo_enrichment", "static_fallback"],
        max_vendors_to_enrich=300
    ),
    filtering=FilterConfig(
        enable_strict_geographic=True,
        require_active_sam_registration=True,
        allow_international_vendors=False
    )
)
```

**Aggressive Profile (Maximum Discovery):**
```python
AGGRESSIVE_CONFIG = RuntimeConfig(
    llm=LLMConfig(
        primary_model="gpt-4o",
        temperature=0.5  # Higher creativity
    ),
    discovery=DiscoveryConfig(
        target_vendor_count=1000,
        enabled_sources=[
            "sam_entity", "canada_contracts", "apollo_search",
            "serper", "duckduckgo"  # Include web search
        ]
    ),
    enrichment=EnrichmentConfig(
        enabled_providers=[
            "apollo_enrichment", "hunter", "serper_search",
            "duckduckgo_scrape", "website_scraper", "static_fallback"
        ],
        max_vendors_to_enrich=1000
    ),
    filtering=FilterConfig(
        enable_strict_geographic=False,
        allow_international_vendors=True,
        min_naics_match_confidence=0.4  # More permissive
    )
)
```

**Offline Profile (No API Calls):**
```python
OFFLINE_CONFIG = RuntimeConfig(
    discovery=DiscoveryConfig(
        enabled_sources=["database"]  # Previously cached vendors only
    ),
    enrichment=EnrichmentConfig(
        enabled_providers=["static_fallback"]  # No external API calls
    ),
    filtering=FilterConfig(
        max_vendors_after_filtering=100
    )
)
```

### Dynamic Configuration

**CLI Overrides:**
```bash
python -m vendor_ai_agent.cli \
  --tender data/tender.pdf \
  --config-profile aggressive \
  --target-vendors 500 \
  --enable-web-search \
  --output-dir ./custom_output
```

**Programmatic Overrides:**
```python
config = load_config(profile="conservative")

config.discovery.target_vendor_count = 500
config.enrichment.enabled_providers.append("clearbit")
config.output.generate_excel = False

pipeline = TenderVendorPipeline(config=config)
```

### Configuration Validation Examples

**Invalid Temperature:**
```python
LLMConfig(temperature=2.5)  # Raises: ConfigurationError("temperature must be 0-2")
```

**Missing API Key:**
```python
RuntimeConfig(
    openai_api_key=None,
    llm=LLMConfig(primary_model="gpt-4o")
)  # Raises: ConfigurationError("openai_api_key required for LLM-based extraction")
```

**Conflicting Settings:**
```python
RuntimeConfig(
    enrichment=EnrichmentConfig(
        enabled_providers=["apollo_enrichment"],
        max_vendors_to_enrich=500
    ),
    filtering=FilterConfig(
        max_vendors_after_filtering=300
    )
)  # Raises: ConfigurationError("max_vendors_to_enrich must be <= max_vendors_after_filtering")
```

### Environment Variable Mapping

| Environment Variable | Config Path | Type | Example |
|---------------------|-------------|------|---------|
| `OPENAI_API_KEY` | `openai_api_key` | str | `sk-...` |
| `SAM_API_KEY` | `sam_api_key` | str | `abc123` |
| `APOLLO_API_KEY` | `apollo_api_key` | str | `xyz789` |
| `TENDER_AGENT_LLM_MODEL` | `llm.primary_model` | str | `gpt-4o` |
| `TENDER_AGENT_TEMPERATURE` | `llm.temperature` | float | `0.3` |
| `TENDER_AGENT_TARGET_VENDORS` | `discovery.target_vendor_count` | int | `300` |
| `TENDER_AGENT_MAX_ENRICHMENT` | `enrichment.max_vendors_to_enrich` | int | `300` |
| `TENDER_AGENT_DATABASE_URL` | `database_url` | str | `postgresql://...` |
| `TENDER_AGENT_LOG_LEVEL` | `log_level` | str | `DEBUG` |
| `TENDER_AGENT_OUTPUT_DIR` | `output.output_dir` | Path | `/tmp/output` |

**Nested Path Convention:** Use dot notation for nested configs (e.g., `llm.primary_model`)

### Configuration Best Practices

**1. Use Profiles for Environments**
```python
if os.getenv("ENVIRONMENT") == "production":
    config = load_config(profile="conservative")
elif os.getenv("ENVIRONMENT") == "staging":
    config = load_config(profile="aggressive")
else:
    config = load_config(profile="offline")
```

**2. Validate Early**
```python
config = load_config()
config.validate()  # Raises ConfigurationError if invalid

pipeline = TenderVendorPipeline(config=config)
```

**3. Log Configuration on Startup**
```python
logger.info(f"Loaded configuration: {config.to_dict()}")
logger.info(f"Enabled sources: {config.discovery.enabled_sources}")
logger.info(f"Enabled providers: {config.enrichment.enabled_providers}")
```

**4. Never Commit API Keys**
- Use `.env` for local development (add to `.gitignore`)
- Use environment variables in production
- Use secret management (AWS Secrets Manager, HashiCorp Vault) for cloud deployments

---

## Field Extraction Strategy

### `project_type` Evolution (Nov 2025)

**Previous Approach:** Hardcoded keyword matching via `SECTOR_KEYWORDS` dictionary → resulted in misclassification (e.g., DHS Uniforms tender classified as "Vehicle project" due to "utility vehicle" mention in document).

**Current Approach:** LLM-based descriptive extraction via `project_summary` field in requirements prompt:
- **Cost:** ~50 tokens marginal cost = $0.00000075 per document (extends existing LLM call)
- **Latency:** 0ms additional (same API call)
- **Output Style:** Descriptive phrases (e.g., "law enforcement uniform supply and delivery") instead of categories
- **Fallback:** Hardcoded `_infer_project_type()` preserved if LLM extraction fails
- **Usage:** Primarily prose contexts (vendor rationales: "for {project_type} requirements", LLM prompts)

**Rationale:** Human-like semantic understanding vs keyword matching; aligns with existing LLM-based extraction for all other structured fields (min_years, licenses, certifications); no UI filtering/categorization dependencies found.

**Migration Path:** SECTOR_KEYWORDS retained as fallback only; monitor fallback usage via logging; deprecate if rarely used in production.

## Database Architecture

The system uses **PostgreSQL** with SQLAlchemy ORM for persistent storage, caching, and audit trails.

### Database Schema Overview

**9 Primary Tables:**

```
tenders                 Core tender records
├── tender_sections     Parsed document sections (text, tables)
├── tender_profiles     Extracted requirements (JSONB)
└── execution_logs      Pipeline execution history

vendors                 Vendor master records
├── vendor_sources      Discovery metadata per source
├── vendor_contacts     Enrichment history (emails, phones)
└── vendor_matches      Capability matching results

canada_contracts        Historical Canadian contract data
├── naics_mappings      NAICS code descriptions
└── gsin_mappings       Canadian GSIN → NAICS mappings
```

### Core Tables

**1. `tenders`**
```sql
CREATE TABLE tenders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id VARCHAR(255) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source VARCHAR(50),  -- 'sam', 'canada', 'manual'
    
    api_metadata JSONB,  -- Raw API response
    profile_data JSONB,  -- Extracted TenderProfile
    
    posted_date TIMESTAMP,
    response_deadline TIMESTAMP,
    estimated_value DECIMAL(15,2),
    
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tender_source ON tenders(source);
CREATE INDEX idx_tender_deadline ON tenders(response_deadline);
CREATE INDEX idx_tender_profile ON tenders USING GIN(profile_data);
```

**Key Features:**
- `api_metadata` stores raw SAM.gov/CKAN JSON (immutable source of truth)
- `profile_data` stores extracted `TenderProfile` as JSONB (queryable)
- GIN index on `profile_data` for fast JSON queries (e.g., NAICS filtering)

**2. `tender_sections`**
```sql
CREATE TABLE tender_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    
    section_type VARCHAR(50),  -- 'text', 'table', 'header', 'footer'
    content TEXT,
    table_data JSONB,  -- For section_type='table'
    
    page_number INTEGER,
    metadata JSONB,  -- Font size, position, etc.
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_section_tender ON tender_sections(tender_id);
CREATE INDEX idx_section_type ON tender_sections(section_type);
```

**3. `vendors`**
```sql
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uei VARCHAR(12) UNIQUE,  -- SAM.gov Unique Entity Identifier
    duns VARCHAR(9),
    cage_code VARCHAR(5),
    
    legal_name VARCHAR(255) NOT NULL,
    dba_name VARCHAR(255),
    
    address_street VARCHAR(255),
    address_city VARCHAR(100),
    address_state VARCHAR(2),
    address_zip VARCHAR(10),
    address_country VARCHAR(2) DEFAULT 'US',
    
    primary_naics VARCHAR(6),
    all_naics_codes TEXT[],  -- Array of NAICS codes
    
    sam_registration_status VARCHAR(50),
    sam_expiration_date DATE,
    
    certifications TEXT[],  -- ['8(a)', 'HUBZone', 'WOSB']
    business_types TEXT[],  -- ['Small Business', 'Minority-Owned']
    
    annual_revenue DECIMAL(15,2),
    employee_count INTEGER,
    year_established INTEGER,
    
    website VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_vendor_uei ON vendors(uei);
CREATE INDEX idx_vendor_duns ON vendors(duns);
CREATE INDEX idx_vendor_location ON vendors(address_state, address_city);
CREATE INDEX idx_vendor_naics ON vendors USING GIN(all_naics_codes);
CREATE INDEX idx_vendor_certs ON vendors USING GIN(certifications);
```

**Deduplication Strategy:**
1. Lookup by UEI (unique government identifier)
2. If no UEI, lookup by DUNS
3. If no DUNS, fuzzy match on name + address
4. Merge data from multiple sources (confidence scoring)

**4. `vendor_sources`**
```sql
CREATE TABLE vendor_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    
    source_name VARCHAR(100),  -- 'sam_entity', 'apollo_search', etc.
    source_confidence DECIMAL(3,2),  -- 0.0-1.0
    
    discovery_query JSONB,  -- Query parameters used
    source_metadata JSONB,  -- Raw response data
    
    discovered_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_source_vendor ON vendor_sources(vendor_id);
CREATE INDEX idx_source_name ON vendor_sources(source_name);
```

**Purpose:** Track which sources discovered each vendor (audit trail + confidence scoring)

**5. `vendor_contacts`**
```sql
CREATE TABLE vendor_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    
    email VARCHAR(255),
    phone VARCHAR(20),
    contact_name VARCHAR(255),
    contact_title VARCHAR(255),
    
    provider_name VARCHAR(100),  -- 'apollo_enrichment', 'serper_search', etc.
    confidence DECIMAL(3,2),  -- 0.0-1.0
    
    website_content TEXT,  -- First 2,000 chars from website
    enrichment_metadata JSONB,
    
    enriched_at TIMESTAMP DEFAULT NOW(),
    cache_expires_at TIMESTAMP  -- TTL for cache invalidation
);

CREATE INDEX idx_contact_vendor ON vendor_contacts(vendor_id);
CREATE INDEX idx_contact_expiry ON vendor_contacts(cache_expires_at);
```

**Caching Logic:**
- Cache hit: Return if `cache_expires_at > NOW()`
- Cache miss: Query provider, insert new record
- TTL: 7 days (configurable via `EnrichmentConfig.cache_ttl_days`)

**6. `vendor_matches`**
```sql
CREATE TABLE vendor_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    
    overall_score DECIMAL(5,2),  -- 0.00-100.00
    capability_score DECIMAL(4,2),  -- 0.00-30.00
    experience_score DECIMAL(4,2),  -- 0.00-30.00
    certification_score DECIMAL(4,2),  -- 0.00-20.00
    geographic_score DECIMAL(4,2),  -- 0.00-20.00
    
    rationale TEXT,
    contract_references TEXT[],
    
    llm_model VARCHAR(100),
    llm_confidence DECIMAL(3,2),
    tokens_used INTEGER,
    
    matched_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(tender_id, vendor_id)
);

CREATE INDEX idx_match_tender ON vendor_matches(tender_id);
CREATE INDEX idx_match_vendor ON vendor_matches(vendor_id);
CREATE INDEX idx_match_score ON vendor_matches(overall_score DESC);
```

**Query Performance:**
- Composite index on `(tender_id, overall_score DESC)` for fast top-N retrieval
- Unique constraint prevents duplicate scoring

**7. `canada_contracts`**
```sql
CREATE TABLE canada_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_number VARCHAR(100) UNIQUE NOT NULL,
    
    vendor_name VARCHAR(255),
    vendor_address TEXT,
    
    contract_date DATE,
    contract_value DECIMAL(15,2),
    
    gsin_codes TEXT[],  -- Canadian procurement codes
    naics_codes TEXT[],  -- Mapped NAICS codes
    
    description TEXT,
    commodity_type VARCHAR(255),
    
    source_dataset VARCHAR(100),  -- 'award_notices', 'standing_offers', etc.
    raw_data JSONB,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_canada_vendor ON canada_contracts(vendor_name);
CREATE INDEX idx_canada_date ON canada_contracts(contract_date);
CREATE INDEX idx_canada_gsin ON canada_contracts USING GIN(gsin_codes);
CREATE INDEX idx_canada_naics ON canada_contracts USING GIN(naics_codes);
```

**Purpose:** 
- Historical contract data for Canadian vendors
- Used by `canada_source.py` for vendor discovery
- Enrichment flags (`high_value_supplier`, `frequent_supplier`) computed from aggregate queries

### Database Operations

**Vendor Deduplication Query:**
```sql
SELECT v.id, v.uei, v.legal_name, v.address_city, v.address_state
FROM vendors v
WHERE 
    v.uei = :uei
    OR v.duns = :duns
    OR (
        LOWER(v.legal_name) SIMILAR TO :fuzzy_name_pattern
        AND v.address_state = :state
        AND v.address_zip = :zip
    )
LIMIT 1;
```

**Cached Enrichment Lookup:**
```sql
SELECT email, phone, website_content, confidence, provider_name
FROM vendor_contacts
WHERE 
    vendor_id = :vendor_id
    AND cache_expires_at > NOW()
ORDER BY confidence DESC
LIMIT 1;
```

**Top Vendors for Tender:**
```sql
SELECT 
    vm.overall_score,
    v.legal_name,
    v.address_city,
    v.address_state,
    vm.rationale
FROM vendor_matches vm
JOIN vendors v ON v.id = vm.vendor_id
WHERE vm.tender_id = :tender_id
ORDER BY vm.overall_score DESC
LIMIT 50;
```

**Canadian Vendor Discovery:**
```sql
SELECT 
    vendor_name,
    COUNT(*) as contract_count,
    SUM(contract_value) as total_value,
    MAX(contract_date) as last_contract_date
FROM canada_contracts
WHERE 
    :naics_code = ANY(naics_codes)
    AND contract_date > NOW() - INTERVAL '5 years'
GROUP BY vendor_name
HAVING COUNT(*) >= 3  -- Frequent supplier threshold
ORDER BY total_value DESC;
```

### Migration Management

**Alembic Setup:**
```
alembic/
├── versions/
│   ├── 6b4ee64b05c3_initial_schema_with_vendors_naics_.py
│   └── d8dfe206ccc1_add_canada_contracts_support_gsin_.py
├── env.py
└── script.py.mako
```

**Create Migration:**
```bash
alembic revision --autogenerate -m "Add vendor_certifications table"
```

**Apply Migration:**
```bash
alembic upgrade head
```

**Rollback Migration:**
```bash
alembic downgrade -1
```

### Database Performance Tuning

**Connection Pooling (SQLAlchemy):**
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,  # Max connections
    max_overflow=20,  # Overflow connections
    pool_pre_ping=True,  # Verify connections before use
    echo=False  # Disable SQL logging in production
)
```

**Query Optimization:**
- **Batch inserts:** Use `bulk_insert_mappings()` for large vendor imports
- **JSONB indexes:** GIN indexes on `profile_data` and `source_metadata` for fast JSON queries
- **Array indexes:** GIN indexes on `naics_codes`, `certifications` for set membership queries
- **Partial indexes:** Index only active tenders (`WHERE status = 'active'`)

**Caching Strategy:**
- **Application-level:** 7-day TTL for enrichment data
- **Query-level:** PostgreSQL query cache for repeated queries
- **Result-level:** Cache top 50 vendors per tender (expires on new match)

### Database Backup & Recovery

**Automated Backups (Production):**
```bash
pg_dump vendor_ai_agent | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Restore from Backup:**
```bash
gunzip -c backup_20251125_120000.sql.gz | psql vendor_ai_agent
```

**Point-in-Time Recovery:**
- Enable WAL archiving in PostgreSQL
- Continuous backup to S3 or equivalent
- Restore to any timestamp within retention period

---

## Pipeline Optimization: Enrichment After Filtering (Nov 2025)

**Problem:** Enrichment (website scraping, Apollo/Hunter API calls) was performed on all discovered vendors before filtering, resulting in 94% wasted resources.

**Previous Flow:**
```
Discovery (5000) → Enrichment (5000) → Filtering (→300) → Capability Matching
```

**Optimized Flow:**
```
Discovery (5000) → Filtering (→300) → Enrichment (300) → Capability Matching
```

**Key Insights:**
- `enrichment_flags` (high_value_supplier, frequent_supplier) come from **source data** (canada_contracts.py), not enrichment providers
- `website_content` is only used by **LLM capability matching** (after filtering)
- Filtering stages (duplicate detection, eligibility, geographic, preliminary ranking) **do not use** enrichment data (email, phone, website_content)

**Impact:**
- Time: 7 hours → 25 minutes (94% reduction)
- Cost: $300 → $18 per run (94% reduction for Apollo/Hunter API calls)
- Implementation: Single reorder in `pipeline.py:140-144`

**Implementation:** `src/vendor_ai_agent/pipeline.py:140-144`
```python
discovered_vendors = self.context.vendor_discovery.discover(tender_profile)
filtered_vendors = self.context.vendor_filter.filter(tender_profile, discovered_vendors)
enriched_vendors = self.context.vendor_enricher.enrich(filtered_vendors)  # Only top candidates
matches = self.context.capability_matcher.score(tender_profile, enriched_vendors)
```

---

## Error Handling Strategy

The system implements **multi-layer error handling** with graceful degradation at each pipeline stage.

### Error Handling Principles

**1. Fail-Safe Execution**
- Pipeline continues even if individual stages fail
- Partial results are better than complete failure
- Users always get actionable output (even if degraded)

**2. Explicit Logging**
- All errors logged with full context (stage, input data, stack trace)
- Warning-level logs for degraded performance
- Error-level logs for failures that impact results

**3. Automatic Retries**
- Transient failures (API timeouts, rate limits) trigger exponential backoff
- Max 3 retry attempts per operation
- Circuit breaker pattern for persistent failures

**4. Fallback Strategies**
- LLM extraction → keyword-based extraction
- Paid enrichment → free enrichment → static fallback
- Primary model → fallback model (GPT-4o → GPT-4o-mini)

### Stage-Specific Error Handling

**1. Ingestion Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| API Timeout | SAM.gov connection timeout | Retry 3x with exponential backoff; skip if all fail |
| Invalid Tender ID | SAM-99999 (not found) | Log warning; proceed with document parsing only |
| Rate Limit | 429 Too Many Requests | Wait (Retry-After header); exponential backoff |
| Network Error | DNS resolution failure | Retry 3x; skip ingestion if persistent |
| Malformed Response | Invalid JSON from API | Log error; use partial data if parseable |

**Error Handler Example:**
```python
def ingest(self, tender_id: str) -> dict:
    for attempt in range(3):
        try:
            response = requests.get(
                f"https://api.sam.gov/opportunities/v2/{tender_id}",
                headers={"X-Api-Key": self.api_key},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            logger.warning(f"SAM.gov timeout (attempt {attempt+1}/3)")
            time.sleep(2 ** attempt)  # Exponential backoff
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                raise TenderNotFoundError(f"Tender {tender_id} not found")
            elif e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited; waiting {retry_after}s")
                time.sleep(retry_after)
            else:
                raise
    
    raise IngestionError(f"Failed to ingest {tender_id} after 3 attempts")
```

**2. Document Parsing Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| Corrupted PDF | Malformed PDF structure | Fall back to raw text extraction (pdfplumber → PyPDF2 → OCR) |
| Password-Protected | Encrypted PDF | Raise error; prompt user for password |
| Unsupported Format | .tif image file | Raise error; list supported formats |
| Large File | 500 MB PDF | Apply page limit (first 100 pages); log warning |
| Missing Tables | No table structure | Continue with text-only extraction |

**Fallback Chain:**
```python
def parse(self, file_path: Path) -> list[TenderSection]:
    parsers = [
        ("pdfplumber", self._parse_with_pdfplumber),
        ("PyPDF2", self._parse_with_pypdf2),
        ("OCR", self._parse_with_ocr)
    ]
    
    for parser_name, parser_func in parsers:
        try:
            sections = parser_func(file_path)
            logger.info(f"Successfully parsed with {parser_name}")
            return sections
        except Exception as e:
            logger.warning(f"{parser_name} failed: {e}")
            continue
    
    raise ParsingError(f"All parsers failed for {file_path}")
```

**3. Requirement Extraction Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| LLM Timeout | OpenAI API timeout | Retry with fallback model (GPT-4o → GPT-4o-mini) |
| Invalid JSON | Malformed LLM response | Parse partial JSON; fill missing fields with None |
| Rate Limit | 429 from OpenAI | Exponential backoff (max 3 retries) |
| Content Filter | Moderation flag | Log warning; extract what's possible |
| Empty Response | LLM returns empty | Fall back to keyword extraction |

**Retry with Fallback:**
```python
def extract(self, doc_sections: list[TenderSection]) -> TenderProfile:
    models = [self.config.primary_model, self.config.fallback_model]
    
    for model in models:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=self._build_prompt(doc_sections),
                temperature=0.3,
                timeout=30
            )
            profile = self._parse_response(response)
            return profile
        except openai.Timeout:
            logger.warning(f"{model} timed out; trying fallback")
        except openai.RateLimitError as e:
            retry_after = int(e.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited; waiting {retry_after}s")
            time.sleep(retry_after)
    
    logger.error("LLM extraction failed; falling back to keyword extraction")
    return self._keyword_extraction_fallback(doc_sections)
```

**4. Vendor Discovery Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| Source API Failure | Apollo API down | Skip failed source; continue with available sources |
| Empty Results | No vendors found | Log warning; proceed with 0 vendors (will fail later with clear message) |
| Partial Results | 2/5 sources succeed | Use partial results; log which sources failed |
| Malformed Vendor Data | Missing required fields | Skip malformed records; log validation errors |

**Partial Success Handling:**
```python
def discover(self, profile: TenderProfile) -> list[Vendor]:
    all_vendors = []
    failed_sources = []
    
    for source in self.sources:
        try:
            vendors = source.search(profile)
            all_vendors.extend(vendors)
            logger.info(f"{source.source_name}: {len(vendors)} vendors")
        except Exception as e:
            logger.error(f"{source.source_name} failed: {e}")
            failed_sources.append(source.source_name)
    
    if failed_sources:
        logger.warning(f"Discovery completed with failures: {failed_sources}")
    
    if not all_vendors:
        raise DiscoveryError("No vendors discovered from any source")
    
    return all_vendors
```

**5. Filtering Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| Invalid Vendor Data | Missing address fields | Skip specific filter (e.g., geographic); continue with other filters |
| Filter Exception | Bug in custom filter | Log error; skip that filter; continue pipeline |
| Database Error | Connection lost during dedup | Retry connection; fall back to in-memory dedup |

**Filter Exception Isolation:**
```python
def filter(self, profile: TenderProfile, vendors: list[Vendor]) -> list[Vendor]:
    filtered = vendors
    
    for filter_stage in self.filter_stages:
        try:
            filtered = filter_stage.apply(profile, filtered)
            logger.info(f"{filter_stage.name}: {len(filtered)} vendors remain")
        except Exception as e:
            logger.error(f"Filter {filter_stage.name} failed: {e}")
            if filter_stage.critical:
                raise  # Re-raise if critical filter
            continue  # Skip non-critical filter
    
    return filtered
```

**6. Enrichment Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| Provider Failure | Apollo API error | Skip to next provider in chain |
| Rate Limit | DuckDuckGo throttling | Exponential backoff; skip if max retries exceeded |
| Invalid Email | Malformed email address | Validate; skip if invalid |
| Network Timeout | Website scraping timeout | Set 10s timeout; skip if exceeded |

**Provider Chain with Skip Logic:**
```python
def enrich(self, vendors: list[Vendor]) -> list[Vendor]:
    enriched = []
    
    for vendor in vendors:
        for provider in self.providers:
            if provider.should_skip(vendor):
                continue
            
            try:
                vendor = provider.enrich(vendor)
            except ProviderError as e:
                logger.warning(f"{provider.provider_name} failed for {vendor.name}: {e}")
                continue  # Try next provider
            except Exception as e:
                logger.error(f"Unexpected error in {provider.provider_name}: {e}")
                continue
        
        enriched.append(vendor)
    
    return enriched
```

**7. Capability Matching Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| LLM Timeout | OpenAI timeout | Retry with exponential backoff; skip vendor if max retries exceeded |
| Malformed Score | LLM returns non-numeric | Default to score=0; log warning |
| Rate Limit | 429 from OpenAI | Batch retry with exponential backoff |
| Empty Rationale | LLM returns no explanation | Use default rationale: "Scored based on NAICS and location match" |

**Batch Retry Logic:**
```python
def score_batch(self, profile: TenderProfile, vendors: list[Vendor]) -> list[VendorMatchResult]:
    results = []
    
    for batch in self._batch_vendors(vendors, batch_size=10):
        for attempt in range(3):
            try:
                batch_results = self._score_llm_batch(profile, batch)
                results.extend(batch_results)
                break
            except openai.RateLimitError:
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited; waiting {wait_time}s")
                time.sleep(wait_time)
        else:
            logger.error(f"Failed to score batch after 3 attempts; skipping {len(batch)} vendors")
    
    return results
```

**8. Output Generation Stage**

| Error Type | Example | Handling Strategy |
|------------|---------|-------------------|
| File Write Error | Disk full | Retry with temp directory; raise error if persistent |
| Permission Denied | Read-only output dir | Raise clear error with suggested fix |
| Excel Format Error | Malformed data for XLSX | Fall back to CSV output |

### Global Error Recovery

**Pipeline-Level Exception Handler:**
```python
def run(self, tender_files: list[Path], tender_id: Optional[str] = None):
    try:
        self._run_pipeline(tender_files, tender_id)
    except CriticalPipelineError as e:
        logger.error(f"Pipeline failed: {e}")
        self._save_error_report(e)
        raise
    except Exception as e:
        logger.exception("Unexpected pipeline error")
        self._save_error_report(e)
        raise PipelineError(f"Unexpected error: {e}") from e
    finally:
        self._cleanup_temp_files()
```

**Error Report Generation:**
```python
def _save_error_report(self, error: Exception):
    report = {
        "timestamp": datetime.now().isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "pipeline_stage": self.state.current_stage,
        "input_data": self.state.input_summary,
        "stack_trace": traceback.format_exc(),
        "system_info": self._get_system_info()
    }
    
    report_path = self.config.output_dir / "error_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Error report saved to {report_path}")
```

### Monitoring and Alerting

**Logging Configuration:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("vendor_ai_agent")
```

**Error Metrics:**
- **Error Rate:** Errors per pipeline run
- **Stage Success Rate:** % of successful stage completions
- **Retry Rate:** Average retries per API call
- **Fallback Rate:** % of times fallback strategy used

**Alerting Thresholds (Production):**
- Error rate > 10% → alert
- Stage success rate < 90% → alert
- LLM fallback rate > 20% → investigate
- Enrichment provider failure rate > 50% → check API status

---

## Performance Architecture

The system is optimized for **cost, latency, and throughput** across all pipeline stages. This section documents caching strategies, batch processing, resource management, and profiling.

### Performance Principles

**1. Cache Aggressively**
- Multi-layer caching (Redis, PostgreSQL, file-based)
- TTL-based invalidation (7-30 days depending on data type)
- Cache-aside pattern for API responses

**2. Batch When Possible**
- LLM requests batched (10 vendors/request)
- Database inserts batched (500 records/transaction)
- API calls parallelized within rate limits

**3. Defer Expensive Operations**
- Enrichment after filtering (94% cost/time savings)
- LLM scoring only on filtered candidates
- Website scraping on-demand only

**4. Optimize Hot Paths**
- NAICS matching uses indexed queries
- Deduplication uses UEI/DUNS hash lookups
- Geographic filtering uses spatial indexes

### Caching Strategies

**Multi-Layer Cache Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│                                                                   │
│  ┌───────────────┐    ┌───────────────┐    ┌──────────────┐    │
│  │  In-Memory    │───▶│  PostgreSQL   │───▶│  External    │    │
│  │  Cache (LRU)  │    │  JSONB Cache  │    │  API Call    │    │
│  │  (1 hour TTL) │    │  (7-30 day)   │    │              │    │
│  └───────────────┘    └───────────────┘    └──────────────┘    │
│                                                                   │
│  Examples:                                                        │
│  - TenderProfile extraction: PostgreSQL (30 days)                │
│  - Vendor contacts: PostgreSQL (7 days)                          │
│  - LLM capability scores: PostgreSQL (30 days) + in-memory       │
│  - Website content: PostgreSQL (7 days)                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Cache Implementation:**

**1. In-Memory Cache (Python `functools.lru_cache`):**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_naics_description(naics_code: str) -> str:
    """Cache NAICS code lookups (rarely changes)."""
    return naics_db.query(naics_code)

@lru_cache(maxsize=100)
def get_tender_profile(tender_id: str) -> TenderProfile:
    """Cache tender profiles within pipeline run."""
    return db.query(TenderProfile).filter_by(tender_id=tender_id).first()
```

**2. PostgreSQL JSONB Cache:**
```sql
-- Enrichment cache
SELECT 
    email, phone, website_content, confidence
FROM vendor_contacts
WHERE 
    vendor_id = :vendor_id
    AND cache_expires_at > NOW()
ORDER BY confidence DESC
LIMIT 1;

-- Match cache
SELECT 
    overall_score, capability_score, rationale
FROM vendor_matches
WHERE 
    tender_id = :tender_id
    AND vendor_id = :vendor_id
    AND matched_at > NOW() - INTERVAL '30 days';
```

**3. File-Based Cache (PDF Parsing):**
```python
def parse_with_cache(self, file_path: Path) -> list[TenderSection]:
    cache_key = hashlib.sha256(file_path.read_bytes()).hexdigest()
    cache_path = self.cache_dir / f"{cache_key}.json"
    
    if cache_path.exists():
        cache_age = time.time() - cache_path.stat().st_mtime
        if cache_age < 7 * 24 * 3600:  # 7 days
            logger.info(f"Cache hit for {file_path.name}")
            return json.loads(cache_path.read_text())
    
    sections = self._parse_pdf(file_path)
    cache_path.write_text(json.dumps([s.__dict__ for s in sections]))
    return sections
```

**Cache Invalidation Strategy:**

| Data Type | TTL | Invalidation Trigger |
|-----------|-----|---------------------|
| NAICS descriptions | Never | Manual (rare code updates) |
| Tender profiles | 30 days | Document re-upload |
| Vendor discovery | 7 days | None (age-out) |
| Vendor contacts | 7 days | Manual refresh command |
| Capability scores | 30 days | Tender profile change |
| Website content | 7 days | None (age-out) |

**Manual Cache Clear:**
```bash
python -m vendor_ai_agent.cli clear-cache --tender SAM-12345
python -m vendor_ai_agent.cli clear-cache --all
```

### Batch Processing Optimization

**1. LLM Batch Scoring:**

**Problem:** Scoring 300 vendors sequentially = 300 API calls × 3s latency = 15 minutes

**Solution:** Batch 10 vendors per prompt + parallel requests (5 concurrent)

```python
async def score_batch_parallel(self, profile: TenderProfile, vendors: list[Vendor]):
    batches = [vendors[i:i+10] for i in range(0, len(vendors), 10)]
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for batch in batches:
            tasks.append(self._score_batch_async(session, profile, batch))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return [r for r in results if not isinstance(r, Exception)]
```

**Performance:**
- **Sequential:** 300 vendors × 3s = 900s (15 minutes)
- **Batched (10/request):** 30 requests × 3s = 90s (1.5 minutes)
- **Batched + Parallel (5 concurrent):** 30 requests / 5 × 3s = 18s

**Cost:** Same (~$4.50 for 300 vendors)

**2. Database Batch Inserts:**

**Problem:** Inserting 5,000 vendors sequentially = 5,000 × 10ms = 50 seconds

**Solution:** Use `bulk_insert_mappings()` with transactions

```python
def batch_insert_vendors(self, vendors: list[Vendor]):
    session = self.get_session()
    
    try:
        vendor_dicts = [v.__dict__ for v in vendors]
        
        # Batch size 500 to avoid memory issues
        for i in range(0, len(vendor_dicts), 500):
            batch = vendor_dicts[i:i+500]
            session.bulk_insert_mappings(VendorModel, batch)
            session.commit()
            logger.info(f"Inserted batch {i//500 + 1} ({len(batch)} vendors)")
    except Exception as e:
        session.rollback()
        raise DatabaseError(f"Batch insert failed: {e}")
```

**Performance:**
- **Sequential inserts:** 5,000 × 10ms = 50s
- **Batch inserts (500/batch):** 10 batches × 500ms = 5s (10x speedup)

**3. Parallel Vendor Discovery:**

```python
def discover_parallel(self, profile: TenderProfile) -> list[Vendor]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(source.search, profile): source 
            for source in self.sources
        }
        
        all_vendors = []
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            try:
                vendors = future.result(timeout=60)
                all_vendors.extend(vendors)
                logger.info(f"{source.source_name}: {len(vendors)} vendors")
            except Exception as e:
                logger.error(f"{source.source_name} failed: {e}")
        
        return all_vendors
```

**Performance:**
- **Sequential:** 5 sources × 20s avg = 100s
- **Parallel (5 workers):** max(source_latencies) = ~25s (4x speedup)

### Connection Pooling and Resource Management

**SQLAlchemy Connection Pool:**
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,  # Normal connections
    max_overflow=20,  # Overflow connections
    pool_timeout=30,  # Wait 30s for connection
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connection before use
    echo=False  # Disable SQL logging in production
)
```

**Benefits:**
- Reuses connections (avoids TCP handshake overhead)
- Pre-ping prevents "connection already closed" errors
- Auto-recycle prevents stale connections
- Pool overflow handles burst traffic

**HTTP Connection Pooling (requests):**
```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

retry_strategy = Retry(
    total=3,
    backoff_factor=1,  # 1s, 2s, 4s
    status_forcelist=[429, 500, 502, 503, 504]
)

adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=retry_strategy
)

session.mount("http://", adapter)
session.mount("https://", adapter)
```

**API Rate Limiting:**
```python
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=10, period=60)  # 10 calls per minute
def query_apollo_api(self, query: str):
    response = requests.get(
        "https://api.apollo.io/search",
        headers={"Authorization": f"Bearer {self.api_key}"},
        params=query
    )
    return response.json()
```

### Memory Management

**Problem:** Large PDFs (500+ pages) consume 2-4 GB RAM during parsing

**Solution 1: Streaming PDF Parsing**
```python
def parse_large_pdf(self, file_path: Path) -> list[TenderSection]:
    sections = []
    
    with pdfplumber.open(file_path) as pdf:
        page_limit = 100  # Process first 100 pages only
        
        for i, page in enumerate(pdf.pages[:page_limit]):
            text = page.extract_text()
            sections.append(TenderSection(
                section_type="text",
                content=text,
                page_number=i+1
            ))
            
            # Force garbage collection every 10 pages
            if i % 10 == 0:
                import gc
                gc.collect()
    
    return sections
```

**Solution 2: Chunked Vendor Processing**
```python
def process_vendors_chunked(self, vendors: list[Vendor], chunk_size: int = 100):
    for i in range(0, len(vendors), chunk_size):
        chunk = vendors[i:i+chunk_size]
        enriched_chunk = self.enrich(chunk)
        self.save_to_db(enriched_chunk)
        
        del chunk, enriched_chunk  # Free memory
        gc.collect()
```

**Solution 3: Generator Pattern for Large Queries**
```python
def get_vendors_generator(self, tender_id: str):
    """Yield vendors in batches to avoid loading all into memory."""
    offset = 0
    batch_size = 500
    
    while True:
        vendors = session.query(Vendor).filter_by(
            tender_id=tender_id
        ).offset(offset).limit(batch_size).all()
        
        if not vendors:
            break
        
        yield from vendors
        offset += batch_size
```

### Query Optimization

**1. Index Usage:**
```sql
-- EXPLAIN ANALYZE to verify index usage
EXPLAIN ANALYZE
SELECT v.legal_name, v.address_city
FROM vendors v
WHERE v.uei = 'ABC123456789';

-- Expected: Index Scan using idx_vendor_uei (cost=0.29..8.31)
```

**2. JSONB Indexing:**
```sql
-- GIN index for JSONB containment queries
CREATE INDEX idx_tender_profile_naics 
ON tenders USING GIN((profile_data -> 'naics_codes'));

-- Query with index
SELECT tender_id, title
FROM tenders
WHERE profile_data -> 'naics_codes' ? '541330';
```

**3. Array Indexing:**
```sql
-- GIN index for array membership
CREATE INDEX idx_vendor_naics 
ON vendors USING GIN(all_naics_codes);

-- Query with index
SELECT legal_name, all_naics_codes
FROM vendors
WHERE '541330' = ANY(all_naics_codes);
```

**4. Partial Indexes:**
```sql
-- Index only active tenders (reduces index size by 80%)
CREATE INDEX idx_active_tenders 
ON tenders(response_deadline) 
WHERE status = 'active';
```

**5. Query Plan Analysis:**
```python
def analyze_query(self, query: str):
    result = session.execute(f"EXPLAIN ANALYZE {query}")
    plan = result.fetchall()
    
    for line in plan:
        print(line[0])
    
    # Look for:
    # - Seq Scan (bad, should use index)
    # - Index Scan (good)
    # - Execution time < 100ms (good)
```

### Profiling and Monitoring

**1. Stage Timing:**
```python
import time

class PipelineProfiler:
    def __init__(self):
        self.stage_times = {}
    
    def time_stage(self, stage_name: str):
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                
                self.stage_times[stage_name] = elapsed
                logger.info(f"{stage_name}: {elapsed:.2f}s")
                
                return result
            return wrapper
        return decorator

profiler = PipelineProfiler()

@profiler.time_stage("document_parsing")
def parse_documents(self, files):
    pass
```

**2. Memory Profiling:**
```python
from memory_profiler import profile

@profile
def discover_vendors(self, profile: TenderProfile):
    """Monitors memory usage line-by-line."""
    pass
```

**3. API Cost Tracking:**
```python
class CostTracker:
    def __init__(self):
        self.costs = {
            "openai": 0.0,
            "apollo": 0.0,
            "serper": 0.0
        }
    
    def track_llm_call(self, model: str, input_tokens: int, output_tokens: int):
        if model == "gpt-4o":
            cost = (input_tokens / 1_000_000 * 2.50) + (output_tokens / 1_000_000 * 10.00)
        elif model == "gpt-4o-mini":
            cost = (input_tokens / 1_000_000 * 0.15) + (output_tokens / 1_000_000 * 0.60)
        
        self.costs["openai"] += cost
        logger.info(f"LLM call cost: ${cost:.4f} (total: ${self.costs['openai']:.2f})")
    
    def track_apollo_call(self, credits_used: int):
        cost = credits_used * 0.01
        self.costs["apollo"] += cost
        logger.info(f"Apollo call cost: ${cost:.2f} (total: ${self.costs['apollo']:.2f})")
    
    def get_total_cost(self):
        return sum(self.costs.values())
```

**4. Performance Metrics Dashboard:**
```python
{
    "pipeline_run_id": "abc123",
    "total_time_seconds": 1523,
    "stage_times": {
        "ingestion": 3.2,
        "parsing": 45.6,
        "extraction": 12.3,
        "discovery": 120.4,
        "filtering": 8.7,
        "enrichment": 1200.5,
        "matching": 125.8,
        "output": 6.5
    },
    "costs": {
        "openai": 7.82,
        "apollo": 4.50,
        "serper": 0.15,
        "total": 12.47
    },
    "vendor_counts": {
        "discovered": 4523,
        "filtered": 300,
        "enriched": 300,
        "scored": 300
    },
    "cache_hits": {
        "tender_profile": true,
        "vendor_contacts": 87,
        "capability_scores": 0
    }
}
```

### Performance Benchmarks

**Typical Pipeline Performance (300-vendor output):**

| Stage | Time | Cost | Optimization |
|-------|------|------|-------------|
| Ingestion | 3s | $0 | Cache API responses (24h) |
| Parsing | 45s | $0 | Cache parsed sections (7d) |
| Extraction | 12s | $0.003 | Cache TenderProfile (30d) |
| Discovery | 120s | $0.50 | Parallel source queries |
| Filtering | 9s | $0 | Indexed database queries |
| Enrichment | 20min | $6-18 | Cache contacts (7d) + skip logic |
| Matching | 10min | $4.50 | Batch + parallel LLM calls |
| Output | 7s | $0 | Async file writes |
| **Total** | **~25min** | **~$11-22** | **94% cost/time savings post-optimization** |

**Pre-Optimization (Enrichment before filtering):**
- Time: 7-8 hours
- Cost: $300+
- Bottleneck: Enriching 5,000 vendors instead of 300

**Optimization Impact:**
- **Time:** 7h → 25min (94% reduction)
- **Cost:** $300 → $18 avg (94% reduction)
- **Implementation:** Single stage reorder in pipeline

---
