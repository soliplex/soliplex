#!/bin/bash
# Health check for Soliplex and Hermes Event Server
SOLIPLEX="${SOLIPLEX_URL:-http://localhost:8000/api}"
HERMES="${HERMES_URL:-http://localhost:8642}"

echo "=== Soliplex Backend ==="
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$SOLIPLEX/ok" 2>/dev/null)
if [ "$STATUS" = "200" ]; then
    echo "  OK ($SOLIPLEX)"
else
    echo "  FAILED (HTTP $STATUS at $SOLIPLEX)"
fi

echo ""
echo "=== Hermes Event Server ==="
RESULT=$(curl -s "$HERMES/health" 2>/dev/null)
if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
    echo "  OK ($HERMES)"

    # Tool count
    TOOLS=$(curl -s "$HERMES/v1/agent/tools" | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('summary',{}); print(f'{s.get(\"available_tools\",0)}/{s.get(\"total_tools\",0)} tools available')" 2>/dev/null)
    echo "  Tools: $TOOLS"

    # Skills count
    SKILLS=$(curl -s "$HERMES/v1/agent/skills" | python3 -c "import sys,json; print(f'{json.load(sys.stdin).get(\"count\",0)} skills')" 2>/dev/null)
    echo "  Skills: $SKILLS"

    # Memory
    MEM=$(curl -s "$HERMES/v1/agent/memory" | python3 -c "
import sys,json
d=json.load(sys.stdin)
user_entries = len(d.get('user',{}).get('entries',[]))
mem_entries = len(d.get('memory',{}).get('entries',[]))
print(f'{mem_entries} memory entries, {user_entries} user entries')
" 2>/dev/null)
    echo "  Memory: $MEM"
else
    echo "  FAILED or not running ($HERMES)"
fi
