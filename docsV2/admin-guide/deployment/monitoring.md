# Monitoring

Configure logging, metrics, and observability for Soliplex.

## Logging

### Log Levels

Configure via environment:

```yaml
environment:
  - name: "LOG_LEVEL"
    value: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

| Level | Use Case |
|-------|----------|
| `DEBUG` | Development, troubleshooting |
| `INFO` | Standard operation |
| `WARNING` | Production (recommended) |
| `ERROR` | Minimal logging |

### Log Output

Logs are written to stdout by default:

```bash
# View logs
docker-compose logs -f soliplex

# View recent logs
soliplex-cli serve installation.yaml 2>&1 | tee app.log
```

## Logfire Integration

[Logfire](https://logfire.dev) provides structured logging and observability.

### Configuration

```yaml
secrets:
  - "LOGFIRE_TOKEN"

environment:
  - name: "LOGFIRE_ENVIRONMENT"
    value: "production"
  - name: "LOGFIRE_SERVICE_NAME"
    value: "soliplex"
```

### Features

- **Structured logging:** JSON log format with context
- **Distributed tracing:** Track requests across services
- **Error tracking:** Automatic exception capture
- **Performance monitoring:** Request latency, slow queries

### Dashboard

Logfire provides dashboards for:
- Request throughput
- Error rates
- Response times
- LLM token usage

## Request Tracing

Soliplex uses `@util.logfire_span` decorators for request tracing:

```python
@util.logfire_span("GET /v1/rooms")
@router.get("/v1/rooms")
async def get_rooms():
    ...
```

This creates spans visible in Logfire for:
- Request duration
- Parameters
- Response status
- Errors

## Health Checks

### Basic Health Check

```bash
curl http://localhost:8000/api/v1/installation
```

Expected response:
```json
{
  "id": "my-installation"
}
```

### Comprehensive Health Check

```bash
# Check rooms are accessible
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/rooms

# Check specific room
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/rooms/research
```

### Docker Health Check

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

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /api/v1/installation
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /api/v1/installation
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Metrics

### Custom Metrics

Key metrics to track:

| Metric | Description |
|--------|-------------|
| Request count | Total API requests |
| Request latency | Response time distribution |
| Error rate | 4xx/5xx responses |
| LLM tokens | Input/output token usage |
| Tool calls | Tool execution count |

### Prometheus (Optional)

If using Prometheus, expose metrics:

```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('soliplex_requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('soliplex_request_latency_seconds', 'Request latency')
```

## Alerting

### Alert Conditions

| Condition | Threshold | Action |
|-----------|-----------|--------|
| High error rate | > 5% errors | Investigate immediately |
| Slow responses | p95 > 30s | Check LLM provider |
| Database errors | Any | Check connection |
| Memory usage | > 80% | Scale or investigate leak |

### Alert Examples

**PagerDuty/Slack:**
```yaml
# Alert rule example
- alert: SoliplexHighErrorRate
  expr: rate(soliplex_errors_total[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "High error rate in Soliplex"
```

## Debugging

### Enable Debug Logging

```yaml
environment:
  - name: "LOG_LEVEL"
    value: "DEBUG"
```

### View SSE Streams

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
    -H "Accept: text/event-stream" \
    "http://localhost:8000/api/v1/rooms/research/agui/$THREAD/$RUN"
```

### Database Queries

Enable SQLAlchemy logging:

```python
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
```

### LLM Requests

Log LLM requests via Logfire spans to see:
- Prompt content
- Model parameters
- Response tokens
- Latency

## Performance Monitoring

### Key Performance Indicators

| KPI | Target |
|-----|--------|
| API response time | < 200ms (non-LLM) |
| LLM response time | < 30s first token |
| Error rate | < 1% |
| Availability | 99.9% |

### Performance Dashboard

Create dashboards showing:
- Request throughput over time
- Response time percentiles (p50, p95, p99)
- Error counts by type
- LLM token usage

## Log Aggregation

### ELK Stack

```yaml
services:
  soliplex:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  filebeat:
    image: elastic/filebeat
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
```

### CloudWatch

```yaml
services:
  soliplex:
    logging:
      driver: awslogs
      options:
        awslogs-region: us-east-1
        awslogs-group: soliplex
        awslogs-stream: production
```

## Troubleshooting

### Common Issues

| Issue | Check |
|-------|-------|
| No logs | LOG_LEVEL setting, stdout capture |
| Missing traces | LOGFIRE_TOKEN configured |
| Health check fails | Port binding, firewall |
| Slow responses | LLM provider, database |

### Debug Checklist

1. Check log level is appropriate
2. Verify Logfire token if using
3. Check container/service health
4. Review recent error logs
5. Check LLM provider status
6. Verify database connectivity
