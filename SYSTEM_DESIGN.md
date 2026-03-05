# System Design — Slack Data Bot

## 1. Problem Statement

Enable non-technical users to query a Postgres analytics database using natural language, entirely from within Slack — with no SQL knowledge required.

---

## 2. Functional Requirements

### User-Facing
- Type a natural language question via `/ask-data <question>` in any Slack channel
- Receive a formatted result table with row count and SQL preview within ~5 seconds
- Click **Export CSV** on any result to receive the data as a downloadable Slack file attachment
- Results served from cache when the same question is repeated

### System-Facing
- Translate natural language → valid PostgreSQL `SELECT` statement using an LLM
- Execute the SQL against Postgres using a read-only connection
- Cache question+result pairs in Redis with a 2-hour TTL
- Handle SQL errors with one automatic LLM-assisted retry
- Upload CSV files directly to the Slack channel on demand

---

## 3. Non-Functional Requirements

| Concern | Target | Notes |
|---|---|---|
| **Latency** | ≤ 5s cold, ≤ 1s cached | Groq ~1-2s, DB ~0.3s, Slack API ~0.3s |
| **Availability** | Best-effort (no SLA) | Single instance; downtime acceptable for MVP |
| **Throughput** | 1–5 concurrent users | Single FastAPI process sufficient |
| **Scalability** | Horizontal-ready | Stateless app; Redis and Postgres are shared state |
| **Consistency** | Session-level | Cache miss on Redis restart is acceptable; not a financial system |
| **Cost** | Near-zero | Groq free tier, local Postgres + Redis |

---

## 4. Constraints and Assumptions

- Users ask valid, data-related questions (no adversarial input for MVP)
- LLM API (Groq) is externally hosted; we do not self-host the model
- Single table (`public.sales_daily`) for MVP; schema is stable and known at deploy time
- Slack is the only UI; no web frontend

---

## 5. Data Flow (Sequence)

```
User                   Slack            FastAPI          Redis       LangGraph        Postgres
 │                       │                 │                │              │               │
 │  /ask-data <q>        │                 │                │              │               │
 │──────────────────────▶│                 │                │              │               │
 │                       │  POST /command  │                │              │               │
 │                       │────────────────▶│                │              │               │
 │                       │   HTTP 200 ACK  │                │              │               │
 │                       │◀────────────────│                │              │               │
 │                       │                 │   GET(key)     │              │               │
 │                       │                 │───────────────▶│              │               │
 │                       │                 │                │              │               │
 │  ── CACHE HIT ──────────────────────────────────────────────────────────────────────    │
 │                       │                 │◀──────────────│ {sql, rows}   │               │
 │                       │                 │                │              │               │
 │  ── CACHE MISS ─────────────────────────────────────────────────────────────────────    │
 │                       │                 │   null         │              │               │
 │                       │                 │◀───────────────│              │               │
 │                       │                 │    invoke(q)   │              │               │
 │                       │                 │───────────────────────────────▶               │
 │                       │                 │                │  Groq API call               │
 │                       │                 │                │  → SQL string                │
 │                       │                 │                │              │  execute SQL  │
 │                       │                 │                │              │──────────────▶│
 │                       │                 │                │              │◀──────────────│
 │                       │                 │◀──────────────────────────────│ {sql, rows}   │
 │                       │                 │   SET(key, TTL=2hr)           │               │
 │                       │                 │───────────────▶│              │               │
 │                       │  post_message   │                │              │               │
 │                       │◀────────────────│                │              │               │
 │  sees result table    │                 │                │              │               │
 │◀──────────────────────│                 │                │              │               │
```

---

## 6. Component Design

### 6.1 FastAPI App (`src/api/`)

Two endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /slack/command` | Receives `/ask-data` slash commands |
| `POST /slack/interactions` | Receives button click callbacks (CSV export) |

Both endpoints verify the Slack request signature (HMAC-SHA256) before processing. Both return HTTP 200 immediately and delegate work to `BackgroundTasks` to avoid Slack's 3-second timeout.

### 6.2 LangGraph Agent (`src/services/llm_service.py`)

Three-node state machine:

```
[generate_sql]
      │
      ▼
[execute_sql] ──── success ──▶ END
      │
      │ error + retry_count < 1
      ▼
   [retry]  (increments counter, re-enters generate_sql with error context)
      │
      ▼
[generate_sql]  ◀── error fed back in prompt
      │
      ▼
[execute_sql] ──── success/fail ──▶ END
```

The retry node passes the SQL error message back to the LLM in the next prompt, allowing it to self-correct (e.g. wrong column name, type mismatch). Max one retry to bound latency.

**Prompt design:**
- System prompt: hardcoded schema + strict rules ("output SQL only, SELECT only, always qualify table")
- User prompt: `Question: <q>\nSQL:` — the stop token pattern guides the LLM to complete only the SQL
- Temperature: 0 for deterministic output

### 6.3 Cache Layer (`src/services/cache_service.py`)

- **Store:** Redis key-value, value = JSON `{sql, rows}`
- **Key:** `slack_bot:query:<sha256(lowercase(question))>`
- **TTL:** 7200 seconds (2 hours), configurable via env
- **Failure mode:** cache errors are logged and silently skipped (graceful degradation; app continues without cache)

### 6.4 Database (`src/utils/db.py`)

- SQLAlchemy `QueuePool` with `pool_size=5`, `max_overflow=10`
- Connects as `analytics_ro` — a Postgres role with `GRANT SELECT` only
- `pool_pre_ping=True` — validates connections before use (avoids stale connection errors)

### 6.5 Slack Service (`src/services/slack_service.py`)

- `post_ack()` — fires immediately to `response_url` so users see a spinner
- `post_message()` — posts Block Kit blocks to the channel
- `upload_csv()` — uses `files_upload_v2` (newer Slack API, supports large files)

---

## 7. Caching Strategy

```
Cache Key:   md5("show revenue by region for 2025-09-01")
Cache Value: {"sql": "SELECT region...", "rows": [{...}, ...]}
TTL:         7200s

Same question rephrased differently → MISS (acceptable; LLM will generate same SQL)
Same question, same case → HIT
CSV export button → reads from cache, no re-query (unless expired)
```

**Why not cache by SQL?**
The LLM generates slightly different SQL whitespace/formatting across calls. Caching by normalized question is more reliable and skips the LLM cost on a hit.

---

## 8. Error Handling

| Scenario | Behavior |
|---|---|
| Empty `/ask-data` text | Ephemeral error message to user, no LLM call |
| LLM generates invalid SQL | Retry once with error context; post error block if still failing |
| Postgres connection failure | Error block in Slack; logged |
| Redis unavailable | Logged warning; continues without cache (graceful degradation) |
| Slack API failure | Logged error; no user-visible retry (acceptable for MVP) |
| Invalid Slack signature | HTTP 403; request dropped |

---

## 9. Scalability Path

The current single-instance design handles 1–5 users comfortably. Scaling path:

1. **More users (10–50):** Increase `pool_size`, add Uvicorn workers (`--workers 4`)
2. **High throughput:** Replace `BackgroundTasks` with Celery + Redis as a proper job queue
3. **Multi-table:** Replace hardcoded schema prompt with dynamic introspection via `information_schema.columns`
4. **Multiple workspaces:** Add workspace-aware token store (Postgres table), route by `team_id`

---

## 10. Known Limitations (MVP Scope)

| Limitation | Mitigation in Production |
|---|---|
| No SQL injection guardrail | Read-only DB user; add LLM output validation layer |
| Single table only | Dynamic schema introspection |
| No per-user rate limiting | Redis counter keyed by `user_id` |
| No audit log | `INSERT` to audit table on every query |
| Cache never invalidated on data change | Add cache invalidation hook on DB writes, or reduce TTL |
| LLM prompt is static | Move to DB-driven prompt templates for multi-tenant use |
