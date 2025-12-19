# Soliplex Backend Code Review Specification & Refactoring Plan

## Executive Summary

This document provides a comprehensive code review specification for the `src/soliplex` Python backend, with particular focus on async/await patterns. It identifies subsystems, categorizes issues by severity, and presents a progressive refactoring roadmap from quick fixes to architectural improvements.

---

## Table of Contents

1. [Subsystem Categorization](#1-subsystem-categorization)
2. [Async/Await Analysis](#2-asyncawait-analysis)
3. [Code Review Specification](#3-code-review-specification)
4. [Progressive Refactoring Plan](#4-progressive-refactoring-plan)
5. [Priority Matrix](#5-priority-matrix)

---

## 1. Subsystem Categorization

### 1.1 Core Application Layer

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **Application Bootstrap** | `main.py`, `cli.py` | FastAPI app factory, middleware, CLI interface |
| **Configuration System** | `config.py` (2220 lines) | YAML-based configuration for installations, rooms, agents, tools, secrets |
| **Installation Management** | `installation.py` | Lifespan management, dependency injection, runtime config access |

### 1.2 Agent Execution Subsystem

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **Agent Factory** | `agents.py` | Pydantic-AI agent creation, caching, tool integration |
| **Tool System** | `tools.py` | Agent tools (RAG search, datetime, user profile, state access) |
| **MCP Client** | `mcp_client.py` | MCP toolset clients (stdio subprocess, HTTP streaming) |
| **MCP Server** | `mcp_server.py` | MCP server exposure for rooms |
| **Completions** | `completions.py` | OpenAI-compatible streaming completions |

### 1.3 AG-UI Protocol Subsystem (Primary UX)

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **Core Abstractions** | `agui/__init__.py` | Abstract base classes for threads, runs, storage |
| **Persistence Layer** | `agui/persistence.py` | SQLAlchemy async models for AG-UI entities |
| **Event Stream Parser** | `agui/parser.py` | Event stream parsing and state management |
| **Stream Multiplexer** | `agui/mpx.py` | Async stream multiplexing for combined event sources |
| **Utilities** | `agui/util.py` | UUID generation, timestamps |

### 1.4 Authentication & Security Subsystem

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **OIDC Authentication** | `auth.py` | OAuth2/OIDC login, callback, session management |
| **MCP Authentication** | `mcp_auth.py` | URL-safe token generation/validation for MCP |
| **Secret Management** | `secrets.py` | Multi-source secret resolution (env, file, subprocess, random) |

### 1.5 API Layer (Views)

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **Health Check** | `views/__init__.py` | Basic health endpoint |
| **AG-UI Endpoints** | `views/agui.py` | Thread/run CRUD, streaming execution |
| **Room Management** | `views/rooms.py` | Room listing, documents, MCP tokens |
| **Conversations (Deprecated)** | `views/convos.py`, `convos.py` | Legacy in-memory conversation storage |
| **Auth Endpoints** | `views/auth.py` | OIDC login/callback/logout |
| **Completions Endpoint** | `views/completions.py` | OpenAI-compatible API |
| **Quiz Endpoints** | `views/quizzes.py` | Quiz submission and checking |
| **Installation Info** | `views/installation.py` | Installation metadata endpoint |

### 1.6 Utility Layer

| Subsystem | Files | Purpose |
|-----------|-------|---------|
| **General Utilities** | `util.py` | Git hash, URL manipulation, Logfire spans |
| **API Models** | `models.py` | Pydantic models for request/response |
| **Examples** | `examples.py` | Example agent factories |
| **Quiz Logic** | `quizzes.py` | LLM-based quiz answer checking |

---

## 2. Async/Await Analysis

### 2.1 Async Usage Statistics

| Metric | Count |
|--------|-------|
| Total async functions | 104 |
| Total await calls | 111+ |
| Files with async code | 23 |
| asyncio.Lock usage | 2 (convos.py, potentially missing in agents.py) |
| asyncio.Queue usage | 1 (agui/mpx.py) |
| asyncio.create_task usage | 1 (agui/mpx.py) |

### 2.2 Async Patterns Analysis

#### GOOD PATTERNS

**1. Async Context Managers (agui/persistence.py:408-411)**
```python
@property
@contextlib.asynccontextmanager
async def session(self):
    async with self._session.begin():
        yield self._session
```
Status: Correct use of async context manager for database sessions.

**2. Async Generators for Streaming (views/agui.py)**
```python
async def tee_events(event_stream, event_list, on_done):
    async for event in event_stream:
        event_list.append(event)
        yield event
    await on_done(events=event_list)
```
Status: Proper streaming pattern using async generators.

**3. Async Locks for Thread Safety (convos.py:186-188)**
```python
def __init__(self):
    self._lock = asyncio.Lock()
    self._convos = {}
```
Status: Correct use of asyncio.Lock() for concurrent access protection.

**4. Stream Multiplexing (agui/mpx.py:8-54)**
```python
def multiplex_streams(*streams):
    queue = asyncio.Queue(1)
    # ... proper drain/merged pattern
    tasks = [asyncio.create_task(drain(stream)) for stream in streams]
    return merged()
```
Status: Sophisticated async stream merging with proper cancellation handling.

**5. SQLAlchemy Async Awaitable Attributes (agui/persistence.py)**
```python
for run in await self.awaitable_attrs.runs:
    await run.awaitable_attrs.run_agent_input
```
Status: Correct use of SQLAlchemy's async ORM patterns.

#### PROBLEMATIC PATTERNS

**1. CRITICAL: Race Condition in Agent Cache (agents.py:101-124)**
```python
_agent_cache: dict[str, pydantic_ai.Agent] = {}  # Line 47

def get_agent_from_configs(...):  # Sync function!
    if agent_config.id not in _agent_cache:  # TOCTTOU race
        agent = _get_default_agent_from_configs(...)
        _agent_cache[agent_config.id] = agent  # Race condition
    return _agent_cache[agent_config.id]
```
Issues:
- No lock protection on cache access
- Time-of-check-to-time-of-use (TOCTTOU) vulnerability
- Concurrent requests may create duplicate agents
- Sync function called from async context

**2. CRITICAL: Blocking I/O in Config Loading (config.py)**
```python
# Line ~1531, ~1888 - called during async lifespan
with config_path.open() as stream:
    config_yaml = yaml.load(stream, yaml.Loader)
```
Issues:
- Synchronous file I/O blocks event loop
- Called during FastAPI lifespan (async context)
- Large configs will cause startup delays

**3. CRITICAL: Blocking Subprocess Calls (secrets.py:99-117)**
```python
def get_subprocess_secret(source: config.SubprocessSecretSource):
    found = subprocess.check_output(  # BLOCKS EVENT LOOP!
        [source.command, *source.args],
        encoding="utf8",
    )
```
Issues:
- `subprocess.check_output` is blocking
- Called during async startup via `resolve_secrets()`
- Should use `asyncio.create_subprocess_exec()`

**4. HIGH: Blocking File Read in Secrets (secrets.py:80-91)**
```python
def get_file_path_secret(source: config.FilePathSecretSource):
    return file_path.read_text()  # Blocking I/O
```
Issues:
- `pathlib.Path.read_text()` is blocking
- Should use `aiofiles` for async file operations

**5. MEDIUM: Blocking Git Subprocess (util.py:46-55)**
```python
def get_git_hash(repo_dir):
    subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"])
```
Issues:
- Blocking subprocess, though only called once at startup
- Lower priority but should be async for consistency

**6. MEDIUM: No Timeout Handling on External Calls**
- No explicit timeouts on MCP client operations
- No timeouts on agent.run() calls
- LLM API calls could hang indefinitely

**7. LOW: Sync JSON Operations**
```python
json.loads(), json.dumps()  # 10+ occurrences
```
Issues:
- Generally fast, but large payloads could block
- Consider async JSON for very large data

---

## 3. Code Review Specification

### 3.1 Critical Issues (Must Fix)

#### CRT-001: Agent Cache Race Condition
- **Location**: `agents.py:47, 101-124`
- **Type**: Concurrency Bug
- **Risk**: Duplicate agent creation, memory leaks, inconsistent state
- **Detection**: Multiple concurrent requests for same room
- **Fix**: Add asyncio.Lock or use functools.lru_cache with lock

#### CRT-002: Blocking Secret Resolution
- **Location**: `secrets.py:99-117` (subprocess), `secrets.py:80-91` (file)
- **Type**: Event Loop Blocking
- **Risk**: Startup delays, unresponsive server during config reload
- **Detection**: Profile startup time, check for event loop warnings
- **Fix**: Convert to async with `asyncio.create_subprocess_exec()`, `aiofiles`

#### CRT-003: Blocking Config File Loading
- **Location**: `config.py:~1531, ~1888`
- **Type**: Event Loop Blocking
- **Risk**: Slow startup, blocked requests during config loading
- **Detection**: Profile startup, check event loop
- **Fix**: Use `aiofiles` for async YAML loading

#### CRT-004: Missing CORS Restrictions
- **Location**: `main.py` - `allow_origins=["*"]`
- **Type**: Security
- **Risk**: Cross-origin attacks in production
- **Detection**: Security audit
- **Fix**: Configure allowed origins per environment

### 3.2 High Priority Issues

#### HGH-001: No Rate Limiting
- **Location**: All view endpoints
- **Type**: Security/Availability
- **Risk**: DoS attacks on expensive LLM operations
- **Fix**: Add FastAPI rate limiting middleware

#### HGH-002: Session Secret Key Regeneration
- **Location**: `auth.py:18`
- **Type**: Security/UX
- **Risk**: All sessions invalidated on restart
- **Fix**: Persist session secret key

#### HGH-003: No Timeout on LLM Calls
- **Location**: Agent execution paths
- **Type**: Reliability
- **Risk**: Hung requests, resource exhaustion
- **Fix**: Add configurable timeouts

#### HGH-004: Missing Input Validation
- **Location**: Secret subprocess commands from config
- **Type**: Security
- **Risk**: Command injection if config is malicious
- **Fix**: Validate/sanitize subprocess arguments

### 3.3 Medium Priority Issues

#### MED-001: God Object - Config System
- **Location**: `config.py` (2220 lines)
- **Type**: Maintainability
- **Risk**: Hard to test, understand, modify
- **Fix**: Split into config_agents.py, config_secrets.py, etc.

#### MED-002: Deprecated Code Not Removed
- **Location**: `convos.py`, `views/convos.py`
- **Type**: Technical Debt
- **Risk**: Confusion, maintenance burden
- **Fix**: Remove or put behind feature flag

#### MED-003: Inconsistent Error Handling
- **Location**: Throughout codebase
- **Type**: Consistency
- **Risk**: Unpredictable error responses
- **Fix**: Standardize on HTTPException or custom exception handlers

#### MED-004: Agent Cache Never Cleared
- **Location**: `agents.py:47`
- **Type**: Memory Management
- **Risk**: Memory growth in long-running process
- **Fix**: Add TTL-based cache eviction

#### MED-005: Missing Type Hints
- **Location**: Various functions
- **Type**: Maintainability
- **Risk**: Runtime type errors, harder to understand
- **Fix**: Add comprehensive type hints

### 3.4 Low Priority Issues

#### LOW-001: Magic Strings
- **Location**: Event types, tool names, config keys
- **Type**: Maintainability
- **Fix**: Replace with enums/constants

#### LOW-002: Large Functions
- **Location**: `agui/parser.py:EventStreamParser.__call__()` (~220 lines)
- **Type**: Maintainability
- **Fix**: Extract helper methods

#### LOW-003: Commented-Out Code
- **Location**: `completions.py:76-77`
- **Type**: Code Cleanliness
- **Fix**: Remove or document why preserved

#### LOW-004: Pragma NO COVER Overuse
- **Location**: Multiple files
- **Type**: Test Coverage
- **Fix**: Review and reduce exclusions

---

## 4. Progressive Refactoring Plan

### Phase 1: Critical Async Fixes (Immediate)

**Goal**: Eliminate blocking operations and race conditions in async context.

#### 1.1 Fix Agent Cache Race Condition
```python
# agents.py - Before
_agent_cache: dict[str, pydantic_ai.Agent] = {}

def get_agent_from_configs(...):
    if agent_config.id not in _agent_cache:
        agent = _get_default_agent_from_configs(...)
        _agent_cache[agent_config.id] = agent
    return _agent_cache[agent_config.id]

# After
import asyncio
from functools import lru_cache

_agent_cache_lock = asyncio.Lock()
_agent_cache: dict[str, pydantic_ai.Agent] = {}

async def get_agent_from_configs(...):
    async with _agent_cache_lock:
        if agent_config.id not in _agent_cache:
            agent = _get_default_agent_from_configs(...)
            _agent_cache[agent_config.id] = agent
        return _agent_cache[agent_config.id]
```

#### 1.2 Convert Blocking Secret Resolution to Async
```python
# secrets.py - Before
def get_subprocess_secret(source):
    found = subprocess.check_output([source.command, *source.args])
    return found.strip()

# After
async def get_subprocess_secret(source):
    proc = await asyncio.create_subprocess_exec(
        source.command, *source.args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise SecretSubprocessError(source.secret_name, source.command_line)
    return stdout.decode().strip()
```

```python
# File secret - Before
def get_file_path_secret(source):
    return file_path.read_text()

# After
import aiofiles

async def get_file_path_secret(source):
    async with aiofiles.open(file_path, 'r') as f:
        return await f.read()
```

#### 1.3 Make Secret Resolution Async
```python
# secrets.py - make resolve_secrets async
async def resolve_secrets(secret_configs: list[config.SecretConfig]) -> None:
    failed_names = []
    excs = []

    for secret_config in secret_configs:
        try:
            await get_secret(secret_config)  # Now async
        except SecretError as exc:
            failed_names.append(secret_config.secret_name)
            excs.append(exc)

    if failed_names:
        raise SecretsNotFound(",".join(failed_names), excs)
```

### Phase 2: Security Hardening (Short-term)

**Goal**: Address security vulnerabilities and add production safeguards.

#### 2.1 CORS Configuration
```python
# main.py
def create_app(config: InstallationConfig):
    allowed_origins = config.cors_origins or ["http://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # Not ["*"]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

#### 2.2 Rate Limiting
```python
# Add slowapi or custom rate limiter
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
@limiter.limit("10/minute")
async def post_room_agui_thread_id_run_id(...):
    ...
```

#### 2.3 Persistent Session Secret
```python
# auth.py
def get_session_secret_key(config: InstallationConfig) -> bytes:
    if config.session_secret_file:
        secret_path = Path(config.session_secret_file)
        if secret_path.exists():
            return secret_path.read_bytes()
        else:
            secret = os.urandom(32)
            secret_path.write_bytes(secret)
            return secret
    return os.urandom(32)  # Fallback for dev
```

#### 2.4 Timeout Configuration
```python
# config.py - add timeout configs
@dataclasses.dataclass
class AgentConfig:
    ...
    request_timeout: float = 120.0  # seconds

# agents.py - apply timeout
async def run_agent_with_timeout(agent, deps, timeout):
    async with asyncio.timeout(timeout):
        return await agent.run(deps=deps)
```

### Phase 3: Configuration System Refactoring (Medium-term)

**Goal**: Break up the monolithic config.py into manageable modules.

#### 3.1 New Configuration Package Structure
```
src/soliplex/config/
├── __init__.py          # Re-export all public config classes
├── base.py              # Base classes, common utilities
├── secrets.py           # SecretConfig, SecretSource classes
├── agents.py            # AgentConfig, LLMProviderType
├── tools.py             # ToolConfig, ToolRequirement
├── mcp.py               # MCP_ClientToolsetConfig
├── rooms.py             # RoomConfig
├── completions.py       # CompletionConfig
├── oidc.py              # OIDCConfig
├── installation.py      # InstallationConfig (now thin orchestrator)
└── loaders.py           # YAML loading, async loading utilities
```

#### 3.2 Async Config Loading
```python
# config/loaders.py
import aiofiles
import yaml

async def load_yaml_config(config_path: Path) -> dict:
    async with aiofiles.open(config_path, 'r') as f:
        content = await f.read()
    return yaml.safe_load(content)

async def load_installation_config(config_path: Path) -> InstallationConfig:
    raw_config = await load_yaml_config(config_path)
    return InstallationConfig.from_yaml(raw_config, config_path)
```

### Phase 4: Deprecated Code Removal (Medium-term)

**Goal**: Remove deprecated conversation system, clean up technical debt.

#### 4.1 Remove Deprecated Files
- Delete `convos.py`
- Delete `views/convos.py`
- Remove conversation-related imports

#### 4.2 Feature Flag for Transition (if needed)
```python
# config.py
@dataclasses.dataclass
class InstallationConfig:
    enable_legacy_convos: bool = False

# main.py
if config.enable_legacy_convos:
    from soliplex.views import convos as convos_views
    app.include_router(convos_views.router)
```

### Phase 5: Architecture Improvements (Long-term)

**Goal**: Improve overall architecture for scalability and maintainability.

#### 5.1 Dependency Injection Container
```python
# di.py - Proper DI container
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Database
    db_engine = providers.Singleton(
        create_async_engine,
        config.database_url,
    )

    # Agent cache with proper lifecycle
    agent_cache = providers.Singleton(
        AgentCache,
        ttl=config.agent_cache_ttl,
    )

    # Thread storage
    thread_storage = providers.Factory(
        ThreadStorage,
        session=db_session,
    )
```

#### 5.2 Event-Driven Architecture for Observability
```python
# events.py - Event bus for decoupled observability
class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable):
        self._handlers[event_type].append(handler)

    async def publish(self, event_type: str, data: dict):
        for handler in self._handlers[event_type]:
            await handler(data)

# Usage
event_bus.subscribe("agent.run.started", log_to_logfire)
event_bus.subscribe("agent.run.completed", update_metrics)
```

#### 5.3 Repository Pattern for Data Access
```python
# repositories/base.py
from abc import ABC, abstractmethod

class ThreadRepository(ABC):
    @abstractmethod
    async def get_by_id(self, thread_id: str) -> Thread: ...

    @abstractmethod
    async def list_for_user(self, user_name: str) -> list[Thread]: ...

    @abstractmethod
    async def create(self, thread: Thread) -> Thread: ...

# repositories/sqlalchemy.py
class SQLAlchemyThreadRepository(ThreadRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, thread_id: str) -> Thread:
        query = select(ThreadModel).where(ThreadModel.thread_id == thread_id)
        result = await self._session.scalars(query)
        return result.first()
```

#### 5.4 Service Layer
```python
# services/agent_service.py
class AgentService:
    def __init__(
        self,
        agent_cache: AgentCache,
        thread_repo: ThreadRepository,
        event_bus: EventBus,
    ):
        self._agent_cache = agent_cache
        self._thread_repo = thread_repo
        self._event_bus = event_bus

    async def execute_run(
        self,
        room_id: str,
        thread_id: str,
        run_input: RunAgentInput,
    ) -> AsyncIterator[Event]:
        await self._event_bus.publish("agent.run.started", {...})
        try:
            agent = await self._agent_cache.get(room_id)
            async for event in agent.run_stream(...):
                yield event
        finally:
            await self._event_bus.publish("agent.run.completed", {...})
```

### Phase 6: Testing Infrastructure (Ongoing)

**Goal**: Improve testability and test coverage.

#### 6.1 Async Test Fixtures
```python
# conftest.py
import pytest_asyncio

@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

@pytest_asyncio.fixture
async def thread_storage(async_session):
    return ThreadStorage(async_session)
```

#### 6.2 Mock Agents for Testing
```python
# tests/mocks.py
class MockAgent:
    async def run_stream(self, *args, **kwargs):
        yield TextMessageStartEvent(...)
        yield TextMessageContentEvent(delta="Hello")
        yield TextMessageEndEvent(...)
```

---

## 5. Priority Matrix

| Phase | Priority | Effort | Impact | Dependencies |
|-------|----------|--------|--------|--------------|
| Phase 1: Critical Async | P0 | Low | High | None |
| Phase 2: Security | P0 | Medium | High | Phase 1 |
| Phase 3: Config Refactor | P1 | High | Medium | Phase 1 |
| Phase 4: Deprecation | P1 | Low | Low | None |
| Phase 5: Architecture | P2 | High | High | Phase 1-3 |
| Phase 6: Testing | P1 | Medium | Medium | Ongoing |

### Recommended Implementation Order

1. **Week 1**: Phase 1 - Critical async fixes (agent cache lock, async secrets)
2. **Week 2**: Phase 2.1-2.2 - CORS and rate limiting
3. **Week 3**: Phase 2.3-2.4 - Session secrets and timeouts
4. **Week 4**: Phase 4 - Remove deprecated code
5. **Month 2**: Phase 3 - Config system refactoring
6. **Month 3+**: Phase 5 - Architecture improvements
7. **Ongoing**: Phase 6 - Testing improvements

---

## Appendix A: Files Changed Per Phase

### Phase 1
- `agents.py` - Add lock, make async
- `secrets.py` - Convert to async
- `config.py` - Update to call async secrets
- `installation.py` - Update lifespan to use async config

### Phase 2
- `main.py` - CORS config
- `auth.py` - Session secret persistence
- `config.py` - Timeout configs
- New: `middleware/rate_limit.py`

### Phase 3
- Delete: `config.py`
- New: `config/__init__.py`
- New: `config/base.py`
- New: `config/secrets.py`
- New: `config/agents.py`
- New: `config/tools.py`
- New: `config/mcp.py`
- New: `config/rooms.py`
- New: `config/completions.py`
- New: `config/oidc.py`
- New: `config/installation.py`
- New: `config/loaders.py`

### Phase 4
- Delete: `convos.py`
- Delete: `views/convos.py`
- Update: `main.py` (remove convos router)
- Update: `installation.py` (remove convos dependency)

### Phase 5
- New: `di.py` or `containers.py`
- New: `events.py`
- New: `repositories/` package
- New: `services/` package
- Update: All views to use services

---

## Appendix B: Async Best Practices Checklist

- [ ] All I/O operations use async versions
- [ ] No `subprocess.run/check_output` - use `asyncio.create_subprocess_exec`
- [ ] No `open()` for file I/O - use `aiofiles`
- [ ] No `time.sleep()` - use `asyncio.sleep()`
- [ ] Shared mutable state protected by `asyncio.Lock()`
- [ ] External calls have timeout handling
- [ ] Long-running operations support cancellation
- [ ] Async generators used for streaming
- [ ] No CPU-bound operations blocking event loop (use `run_in_executor`)
- [ ] Database sessions properly scoped with async context managers
