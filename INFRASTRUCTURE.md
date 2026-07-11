# HireCred — Infrastructure & Scaling Guide

**Last updated: 2026-07-11**

> How this system works at 100 users, why it survives 1,000,000 users, exactly
> where the free/local stack stops being enough, and what replaces each piece in
> production. Written so you can defend every design decision under hard
> questioning — each section states the problem, the naive approach that fails,
> what we actually do, and the production upgrade path.

---

## 1. The One-Paragraph Pitch

HireCred is a three-tier system: a **stateless FastAPI backend**, a
**PostgreSQL database that does the heavy lifting** (filtering, ranking,
full-text search — all inside the DB with indexes), and a **local LLM
(Ollama)** used only for judgment tasks, never in a hot path a user waits on.
Everything expensive — AI scoring, URL verification, fraud analysis — runs in a
**deduplicated background queue**, so user-facing requests stay under ~100 ms
regardless of how slow the AI is. That separation — *fast synchronous reads,
slow asynchronous intelligence* — is the single architectural idea everything
else hangs off.

---

## 2. Architecture Diagram

### Current (local, free)

```
Browser (React SPA, Vite)
   │  HTTPS / JSON
   ▼
FastAPI (uvicorn, async)  ──────────────┐
   │                                    │
   │  asyncpg pool (10 + 20 overflow)   │  task_manager.py
   ▼                                    │  (in-process queue:
Neon PostgreSQL                         │   debounce, dedup,
   • GIN index on search_tsv (FTS)      │   semaphore=2)
   • pg_trgm index on title (fuzzy)     │        │
   • trigger-maintained tsvector        │        ▼
                                        │  Ollama (qwen2.5:3b)
Local disk: server/uploads/             │  httpx shared pool
  (CVs, screenshots, message images)    │  URL checker (bounded LRU cache)
```

### Target production (1M+ users)

```
CDN (CloudFront/Cloudflare) ── static SPA + uploaded media
   │
Load balancer (ALB / nginx)
   │
API tier: N stateless FastAPI pods (Kubernetes / ECS, autoscaled)
   │            │
   │            ├── Redis: cache (leaderboard, URL results), rate limits,
   │            │          Celery/arq broker, sorted-set leaderboard
   │            ▼
   │       Worker tier: Celery/arq workers (scoring, URL checks, fraud)
   │            │
   │            ▼
   │       LLM tier: vLLM on GPU (or Claude/OpenAI API) behind its own queue
   ▼
PostgreSQL primary (writes) + read replicas (search, profiles, leaderboard)
   • same schema, same indexes — nothing about the data model changes
S3/GCS + CDN for all uploads   •   OpenTelemetry → Grafana/Datadog
```

The key claim: **moving from the left diagram to the right one requires almost
no application-logic changes**, because every scaling seam already exists in
the code (documented per-section below).

---

## 3. The Request Path — Why Reads Are Fast

### 3.1 Stateless API

No session state lives in the API process. Auth is a signed JWT the client
presents on every request; any pod can serve any request. This is what makes
horizontal scaling trivial: add pods behind a load balancer, done. The only
in-process state is *caches* (leaderboard, URL results) and the *task queue* —
both are explicitly marked as "replace with Redis when multi-instance" and are
correctness-safe if lost (they rebuild themselves).

### 3.2 Connection pooling

`database.py` keeps an asyncpg pool (`pool_size=10, max_overflow=20,
pool_pre_ping=True, pool_recycle=1800`). Why it matters: a Postgres connection
costs ~1.5–5 MB of server memory and a TCP+TLS+auth handshake. Without a pool,
1,000 concurrent requests would try to open 1,000 connections and crush the
database. With the pool, requests *queue briefly for a connection* instead —
the DB sees at most 30 connections per API pod. At 1M users you add
**PgBouncer** (transaction-level pooling) in front of Postgres so 50 pods × 30
connections doesn't become 1,500 server connections.

### 3.3 No N+1 queries

Every list endpoint batch-loads its aggregates:
- Search loads appreciation averages for all ≤200 candidates in **one**
  `GROUP BY` query (`_load_appreciation_map`), not one query per candidate.
- Leaderboard joins appreciation and proof-signal aggregates as subqueries in
  a single statement.
- Profile responses use `selectinload` (2 queries total) instead of lazy
  per-row loads.

N+1 is the classic silent killer: a page that runs 1 + 200 queries feels fine
in dev with 10 rows and takes 4 seconds in production. Grep test: no query
ever appears inside a `for` loop over DB rows.

### 3.4 Atomic counters

Profile view counting is `UPDATE profiles SET profile_views = profile_views + 1`
— a single atomic statement executed by the database. The naive
`obj.views += 1; commit()` reads a value, increments it in Python, writes it
back; two concurrent viewers both read 41 and both write 42, losing a count.
At scale this class of read-modify-write race also causes deadlocks. Rule:
counters are incremented *in the database*, never in application memory.

---

## 4. Search at 1M Profiles — SQL-First, Python-Rank

**The rule: the database filters, Python only ranks a bounded set.**

1. **Stored `tsvector` column** (`profiles.search_tsv`) maintained by a DB
   trigger, indexed with GIN. A query like "python django developer" becomes
   `search_tsv @@ to_tsquery('python & django')` — an index lookup, not a scan.
   Why a *stored* column instead of computing `to_tsvector()` per query: the
   computation happens once per profile write, not once per profile per search.
2. **Three-stage fallback**, each with a hard LIMIT:
   FTS (≤200 rows) → `pg_trgm` trigram fuzzy on title (≤50, catches typos like
   "develoer") → ILIKE (≤100, last resort).
3. **Python ranks only the pre-filtered ≤200 rows**: 40% credibility +
   35% skill match + 15% appreciation + 10% views + FTS-rank bonus. Ranking
   200 dicts is microseconds; the design guarantees Python never sees an
   unbounded result set.
4. **Intent parsing is heuristics-first**: profession/skill extraction from
   static tables answers most queries instantly; the LLM is only consulted
   (3.5 s timeout) for queries the heuristics can't classify — and its failure
   falls back to the heuristic parse. Search never *depends* on the LLM.

**At 1M+:** identical architecture. Postgres FTS with GIN comfortably handles
low millions of rows. Beyond that, or for semantic matching, add
**Elasticsearch/OpenSearch or pgvector embeddings** as a dedicated search tier
fed by change-data-capture — the API contract doesn't change.

---

## 5. Leaderboard at 1M Users

**The bug we fixed (worth remembering):** the old implementation selected
*every* eligible candidate into Python and sorted there — O(N) rows over the
wire per cache miss. Works at 1k users, is an outage at 1M.

**Now:** the composite score
(`credibility×0.65 + appreciation×weight + proof_bonus + views_bonus`) is an
SQL expression; Postgres joins the aggregate subqueries, sorts, and returns
**exactly 20 rows** (`server/src/routers/leaderboard.py`). A 2-minute
in-process cache (with an asyncio lock to prevent cache-stampede — N
simultaneous cache misses triggering N identical heavy queries) absorbs
repeat traffic.

**At 1M:** even the SQL sort gets expensive if run per cache-miss over a huge
eligible set. Two standard fixes, both trivial from here:
- **Materialized view** refreshed every N minutes (`REFRESH MATERIALIZED VIEW
  CONCURRENTLY`) — the view's definition is literally the query already in the
  code.
- **Redis sorted set (`ZADD`/`ZREVRANGE`)** updated whenever a score changes —
  O(log N) updates, O(20) reads, and it's shared across all API pods (the
  in-process cache is per-pod).

---

## 6. The Background Job System — The Most Important Seam

### The problem

Scoring one profile = 1 LLM call (~5–10 s on CPU) + up to ~10 outbound URL
checks + heuristics. You cannot do that inside an HTTP request: the user's
save would hang for 15 seconds, and 100 concurrent saves would open 100
simultaneous LLM generations against a machine that can process ~1 at a time.

### The naive approach that fails

`asyncio.create_task(compute_score(...))` — what the code used to do. Three
production-grade defects:
1. **Silent task loss** — asyncio holds only a *weak* reference to tasks; a
   fire-and-forget task can be garbage-collected mid-run. Scores just
   silently never appear, unreproducibly.
2. **No deduplication** — editing a profile fires 4–5 saves in a burst; each
   spawned a full pipeline run. 5× the LLM load for zero benefit.
3. **Unbounded concurrency** — nothing limited how many pipelines ran at
   once, so load spikes turned into Ollama queueing, 10 s timeouts, and
   everything degrading to the rule-based fallback.

### What runs now (`server/src/services/task_manager.py`)

- **Strong task references** held until completion (fixes GC loss), with
  logged failure accounting.
- **Debounce (2 s) + coalescing**: a burst of saves collapses into one run;
  a save arriving *mid-run* sets a dirty flag that triggers exactly one
  follow-up run against the latest data. Invariant: at most one run in
  flight + one queued per user.
- **Semaphore (2)** bounds concurrent pipelines to what local Ollama can
  actually serve.
- **Ordering guarantee**: fraud detection (which applies a penalty *on top*
  of the score row) waits for the pending rescore to finish, because the
  rescore UPSERTs the whole row and would otherwise erase the fraud result.
- **Observability**: `GET /health/queue` → scheduled / coalesced / in-flight /
  failed counts.

### Honest limitation + production upgrade

An in-process queue **dies with the process** — jobs scheduled but not run are
lost on restart (acceptable here: every job is re-triggerable and a manual
"Refresh score" button exists). At 1M users you swap the *body* of
`schedule_rescore()` for `queue.enqueue(...)` against **Redis + Celery/arq**
(or SQS): durable jobs, retries with exponential backoff, dead-letter queues,
horizontally scaled workers, per-queue rate limits. **Call sites don't change**
— that one function is the seam. Idempotency already holds: scoring is an
UPSERT keyed on `user_id`, so a retried job is harmless.

---

## 7. The LLM Tier

| Concern | How it's handled |
|---|---|
| LLM is slow | Never in a user-facing hot path except appreciation analysis (product choice: the AI ratings are shown in the response). Everything else is background. |
| LLM is down | Every AI call has a deterministic fallback: rule-based completeness scoring, heuristic search parsing, neutral appreciation ratings, conservative fraud default. **The platform functions with Ollama switched off** — scores are just less nuanced. |
| LLM is wrong | Structured-JSON prompts + `extract_json` parsing + sanity check (zero score with no strengths ⇒ treated as failure ⇒ fallback). Post-LLM clamps: score ∈ [0,100], hard ceilings under high fraud risk. Deterministic penalties (authenticity, dead URLs) are applied *outside* the LLM so they can't be prompt-engineered away. |
| LLM overload | Semaphore in task manager + 10 s `wait_for` ceiling per scoring call. |
| Connection churn | One shared `httpx.AsyncClient` to Ollama (was: new client + handshake per call). |

**Local reality check:** qwen2.5:3b on CPU ≈ 5–15 s per scoring call ⇒ roughly
4–10 scorings/minute/machine. Fine for hundreds of active users; **not** for
1M. This is the one tier the free/local stack genuinely cannot scale — see §12.

**Production:** vLLM serving a 7–8B model on one A10/L4 GPU (≈ 50–200
generations/min with continuous batching), or a hosted API (Claude Haiku-class
for cost). Either slots behind the same worker queue; prompts don't change.

---

## 8. Trust & Safety Pipeline (order matters)

```
profile save → (debounced) task_manager
  1. 16-point authenticity heuristics   (pure Python, free, deterministic)
  2. URL verification                    (bounded-concurrency HTTP, cached)
  3. LLM evaluation                      (with all evidence in the prompt)
  4. Deterministic post-adjustments      (authenticity −≤60, dead URLs, caps)
  5. Atomic UPSERT of score row          (no read-modify-write)
  6. Leaderboard cache invalidation
appreciation → AI ratings in-path → background: rescore, THEN fraud analysis
report → admin approve → −12 + suspicious flag
```

Design principle: **cheap deterministic checks gate expensive AI checks**, and
deterministic penalties are applied after the LLM so adversarial profile text
can't talk its way past them.

URL checker hardening: shared connection pool, semaphore of 5 concurrent
checks, 4 s timeouts, trusted-domain skip list (github.com etc. — avoids rate
bans), title-based dead/parked-page detection, and a **bounded LRU cache**
(512 entries, 5 min TTL) — an unbounded cache dict on a long-running server is
a slow memory leak.

---

## 9. Security Posture

| Layer | Measure |
|---|---|
| Passwords | bcrypt (adaptive cost) |
| Auth | JWT HS256, 7-day expiry; role claims; admin = DB flag checked per request |
| SQL injection | SQLAlchemy bound parameters everywhere; FTS terms sanitized to word-chars before `to_tsquery` |
| Uploads | Size cap (5 MB) + MIME allowlist + **magic-byte verification** (`%PDF-` for PDFs, Pillow decode for images) + **server-generated filenames** (client filename never touches the filesystem — kills path-trickery and stored-XSS-via-extension) |
| Rate limits | login 10/min, register 5/min, search 30/min, appreciation 10/min, rescore 5/min (slowapi, per-IP) |
| CORS | Explicit origin/method/header allowlist, no `*` |
| Enumeration | Emails hidden from public profile responses; uniform 401 on login |
| SSRF (URL checker fetches user-supplied URLs) | Known residual risk — production must block private IP ranges (RFC1918, 169.254.169.254 metadata endpoints) before fetching. Documented in §13 gaps. |

Production additions: rate limits keyed in Redis (per-user + per-IP, shared
across pods), refresh-token rotation, WAF at the edge, upload malware scanning
(ClamAV lambda on the S3 bucket).

---

## 10. Failure Modes — "What Happens When X Dies?"

| Failure | Behavior |
|---|---|
| Ollama down | `/health/ai` reports it; scoring falls back to rule-based; search falls back to heuristic parsing; appreciations get neutral ratings. No user-facing errors. |
| DB down / cold start (Neon free tier suspends) | Startup warm-up ping with exponential backoff (6 retries); global exception handler walks the exception chain and converts asyncpg/timeout errors to **503 + human message** instead of a 500 crash; `pool_pre_ping` discards dead pooled connections. |
| API process restarts | JWTs stay valid (stateless); caches rebuild; queued-but-unrun scoring jobs are lost (re-triggerable; durable queue is the production fix). |
| External URL slow/dead | 4 s timeout, 5-check semaphore — one dead link can't stall the pipeline. |
| Cache stampede | Leaderboard lock: first request computes, the rest wait and reuse. |
| Duplicate/concurrent score writes | UPSERT (`ON CONFLICT DO UPDATE`) — last write wins, no unique-violation crashes. |

---

## 11. Capacity Math (defend the numbers)

Assume 1M registered users, ~5% daily active = 50k DAU, ~20 requests/user/day
⇒ 1M requests/day ≈ **12 req/s average, ~60 req/s peak**.

- **API**: async FastAPI does hundreds of req/s per process for I/O-bound
  work ⇒ 2–4 small pods cover peak with headroom.
- **Postgres**: reads are indexed point/limit queries; a single modest
  instance (4 vCPU / 16 GB) handles this read load; replicas are for
  isolation and failover more than raw throughput at this level.
- **Writes**: profile saves are low-frequency human actions — trivial.
- **The bottleneck is the LLM**, always: 50k DAU × even 0.2 scoring events/day
  = 10k LLM jobs/day ≈ 7/min average with bursts — already above a CPU-only
  Ollama box (~4–10/min). This is why the queue exists and why the LLM tier is
  the first thing to move off free/local.

---

## 12. What Free/Local Genuinely Cannot Do (honest limits)

| Capability | Local/free status | Production replacement |
|---|---|---|
| LLM throughput | ~4–10 scorings/min (CPU qwen2.5:3b). Fine to ~1–2k active users with the queue smoothing bursts. | vLLM + 1 GPU (~$0.5–1/hr) or hosted API (Haiku-class ≈ $0.001–0.01/eval) |
| Multi-instance API | In-process caches/queue/rate-limits are per-process. One uvicorn process only. | Redis for all shared state |
| Durable jobs | Lost on restart | Celery/arq + Redis, or SQS |
| File storage | Local disk dies with the machine, doesn't scale, no CDN | S3/GCS/R2 + CDN, presigned upload URLs |
| Neon free tier | ~0.5 GB, cold suspends, 1 connection pool budget | Neon Pro / RDS / Cloud SQL + PgBouncer + replicas |
| Observability | Log lines + `/health/*` endpoints | OpenTelemetry traces, Prometheus/Grafana, Sentry, pg_stat_statements |
| Email/notifications | None | SES/SendGrid via worker queue |

Everything **else** — schema, indexes, query patterns, scoring pipeline,
search architecture, security model — is already built the way the production
system would be. That's deliberate: the expensive-to-change decisions (data
model, query strategy, async boundaries) are production-shaped; the
easy-to-swap parts (cache store, queue broker, file store) are behind seams.

---

## 13. Known Gaps / Next Steps

1. **SSRF guard** in the URL checker (block private/metadata IPs) — required
   before any public deployment.
2. **Durable queue** (arq is the lightest lift for an asyncio codebase).
3. **Redis leaderboard + shared rate limits** when going multi-pod.
4. **Refresh tokens** (current: single 7-day JWT, no revocation).
5. **Pagination** on admin users list and appreciation lists.
6. **Postgres partitioning** of `messages` by month if messaging volume grows.
7. **Automated test suite** in CI (current tests are manual scripts).

---

## 14. Interview Drill — Likely Hard Questions, Short Answers

**"Why Postgres FTS instead of Elasticsearch?"**
One less system to operate, transactionally consistent with the source data,
and GIN-indexed FTS handles low-millions of rows easily. ES earns its
operational cost only when you need semantic relevance tuning, faceting, or
>10M documents — and the SQL-first design means swapping the search backend
touches one service file.

**"What's your single point of failure?"**
Locally: everything (one process, one machine) — accepted for dev. The
production diagram has no SPOF: stateless API pods, DB primary with replica
failover, Redis with sentinel, queue workers redundant by count.

**"How do you keep the LLM from being a denial-of-service vector?"**
It's never on an unbounded path: rate-limited endpoints → deduplicated
debounced queue → semaphore → 10 s timeout → deterministic fallback. Worst
case under flood: scores compute slower and fall back to rule-based; the API
never blocks.

**"How do you know the score is trustworthy if an LLM computes it?"**
The LLM only judges *quality*; all *integrity* signals (authenticity
heuristics, dead-link detection, fraud penalties, admin reports) are
deterministic code applied after the LLM, with hard caps. A profile can't
prompt-inject its way past a −60 authenticity penalty.

**"What breaks first at 10× traffic?"**
The LLM tier (see capacity math), which is why it's isolated behind a queue
whose depth is observable (`/health/queue`) — you scale workers/GPUs without
touching the API. Second: Neon free-tier connection limits → PgBouncer.

**"Why not microservices?"**
At this scale a modular monolith is strictly better: one deploy, no network
partitions between "services" that share one database anyway. The seams
(search service, scoring pipeline, queue) are module boundaries today and can
become service boundaries when team size — not traffic — demands it.
