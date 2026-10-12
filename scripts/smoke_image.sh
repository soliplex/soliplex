#!/usr/bin/env bash
# Check that a release image runs its intended target (#1439).
#
# Usage, from a checkout (the server check serves 'example/minimal.yaml'):
#
#   scripts/smoke_image.sh <target> <image>
#
# where '<target>' is one of the 'Dockerfile' targets:  'soliplex',
# 'soliplex-postgres', or 'soliplex-tui'.
set -euo pipefail

target=$1
image=$2
port=${SMOKE_PORT:-18000}
name="smoke-${target}-$$"

run() {
    echo "+ $*"
    docker run --rm "$image" "$@"
}

cleanup() {
    docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Every image must serve.  No LLM is needed to start, nor to answer
# '/api/ok'.
run soliplex-cli --help >/dev/null
docker run -d --name "$name" -p "127.0.0.1:${port}:8000" \
    -v "$PWD/example:/example:ro" \
    -e OLLAMA_BASE_URL=http://localhost:11434 \
    "$image" \
    sh -c 'mkdir -p db/sqlite && exec soliplex-cli serve \
           --host=0.0.0.0 --no-auth-mode /example/minimal.yaml' \
    >/dev/null
for _ in $(seq 60); do
    if curl -fsS "http://127.0.0.1:${port}/api/ok" >/dev/null 2>&1; then
        echo "+ GET /api/ok: OK"
        break
    fi
    sleep 1
done
if ! curl -fsS "http://127.0.0.1:${port}/api/ok" >/dev/null 2>&1; then
    docker logs "$name"
    echo "smoke_image: ${target}: server did not answer /api/ok" >&2
    exit 1
fi

# Nothing used to build the image may be left in it.
run sh -c '! command -v uv && ! ls /app/pyproject.toml /app/uv.lock' \
    >/dev/null 2>&1 || {
    echo "smoke_image: ${target}: build tooling left in the image" >&2
    exit 1
}

# Each image adds only its own extra / group to the base wheel.
absent() {
    run python -c 'import importlib.util, sys
found = [m for m in sys.argv[1:] if importlib.util.find_spec(m)]
assert not found, f"unexpected: {found}"' "$@"
}

case "$target" in
    soliplex)
        absent psycopg textual
        ;;
    soliplex-postgres)
        absent textual
        # The pure-Python implementation, loading the system 'libpq'.
        run python -c 'import psycopg
assert psycopg.pq.__impl__ == "python", psycopg.pq.__impl__
print("libpq", psycopg.pq.version())'
        ;;
    soliplex-tui)
        absent psycopg
        run soliplex-tui --help >/dev/null
        run soliplex-tui-serve --help >/dev/null
        ;;
    *)
        echo "smoke_image: unknown target: ${target}" >&2
        exit 2
        ;;
esac

echo "smoke_image: ${target}: OK"
