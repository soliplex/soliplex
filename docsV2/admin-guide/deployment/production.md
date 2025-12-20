# Production Deployment

Checklist and best practices for deploying Soliplex in production.

## Pre-Deployment Checklist

- [ ] Configure OIDC authentication
- [ ] Set up secrets management
- [ ] Enable HTTPS via reverse proxy
- [ ] Configure persistent database
- [ ] Set appropriate logging level
- [ ] Set resource limits
- [ ] Back up RAG databases
- [ ] Configure monitoring

## Security

### Authentication

Never use `--no-auth-mode` in production. Configure OIDC:

```yaml
# oidc/config.yaml
auth_systems:
  - id: "corporate"
    title: "Corporate SSO"
    server_url: "https://sso.company.com"
    client_id: "soliplex-prod"
    client_secret: "secret:SSO_CLIENT_SECRET"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A...
      -----END PUBLIC KEY-----
```

### Secrets Management

Use external secret stores:

```yaml
secrets:
  # Docker secrets
  - secret_name: "API_KEY"
    sources:
      - kind: "file_path"
        file_path: "/run/secrets/api_key"

  # AWS Secrets Manager (via subprocess)
  - secret_name: "DB_PASSWORD"
    sources:
      - kind: "subprocess"
        command: "aws"
        args: ["secretsmanager", "get-secret-value", "--secret-id", "soliplex/db"]
```

### HTTPS

Always use HTTPS in production. Configure via reverse proxy:

```nginx
server {
    listen 443 ssl http2;
    server_name soliplex.example.com;

    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### MCP Token Security

Configure token expiration:

```yaml
environment:
  - name: "MCP_TOKEN_MAX_AGE"
    value: 3600  # 1 hour (seconds)

secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "subprocess"
        command: "aws"
        args: ["secretsmanager", "get-secret-value", "--secret-id", "soliplex/mcp-secret"]
```

## Database

### Persistent Thread Storage

Use PostgreSQL for production:

```yaml
thread_persistence_dburi:
  sync: "postgresql+psycopg2://soliplex:secret:DB_PASSWORD@postgres:5432/soliplex"
  async: "postgresql+asyncpg://soliplex:secret:DB_PASSWORD@postgres:5432/soliplex"
```

### Database Backup

```bash
# Backup PostgreSQL
pg_dump -h postgres -U soliplex soliplex > backup.sql

# Backup RAG databases
tar -czf rag_backup.tar.gz ./db/rag/
```

## Logging

### Production Log Level

Set via CLI option:

```bash
soliplex-cli serve installation.yaml --log-level WARNING
```

Available levels: CRITICAL, ERROR, WARNING (recommended for production), INFO, DEBUG, TRACE

### Structured Logging with Logfire

Set Logfire environment variables (these are OS environment variables, not installation config):

```bash
export LOGFIRE_TOKEN="your-logfire-token"
export LOGFIRE_ENVIRONMENT="production"
export LOGFIRE_SERVICE_NAME="soliplex"
soliplex-cli serve installation.yaml
```

Soliplex automatically activates Logfire when `LOGFIRE_TOKEN` is set.

## Resource Limits

### Docker Resource Limits

```yaml
services:
  soliplex:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Uvicorn Workers

```bash
soliplex-cli serve installation.yaml --workers 4
```

## High Availability

### Multiple Instances

```yaml
services:
  soliplex:
    deploy:
      replicas: 3

  nginx:
    # Load balance across instances
```

**Requirements:**
- Shared PostgreSQL database
- Shared RAG database storage (NFS, EFS, etc.)
- Sticky sessions for SSE streams

### Health Checks

```yaml
services:
  soliplex:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/installation"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

## Monitoring

### Endpoints to Monitor

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/installation` | Basic health check |
| `GET /api/v1/rooms` | API availability |

### Metrics

Enable Logfire for:
- Request latency
- Error rates
- LLM usage
- Tool execution times

### Alerting

Set up alerts for:
- High error rates
- Slow response times
- Database connection failures
- LLM provider errors

## Deployment Commands

### Validate Configuration

```bash
soliplex-cli check-config installation.yaml
soliplex-cli list-secrets installation.yaml
soliplex-cli list-environment installation.yaml
```

### Start Server

```bash
# Production with multiple workers
soliplex-cli serve installation.yaml --host 0.0.0.0 --port 8000 --workers 4
```

### Docker Deployment

```bash
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml logs -f soliplex
```

## Rollback Plan

1. Keep previous version images tagged
2. Maintain database migrations
3. Test rollback procedure
4. Document recovery steps

```bash
# Rollback to previous version
docker-compose -f docker-compose.prod.yml down
docker tag soliplex:latest soliplex:rollback
docker tag soliplex:v1.2.3 soliplex:latest
docker-compose -f docker-compose.prod.yml up -d
```

## Post-Deployment Verification

1. **Health check:** `curl https://soliplex.example.com/api/v1/installation`
2. **Auth flow:** Complete login with OIDC
3. **Room access:** List rooms and enter one
4. **Chat:** Send a message and verify response
5. **RAG:** Test document search
6. **Logs:** Check for errors in logs
