# SynQubi AI Hedge Fund — Project Specification

> **Purpose**: This document is the authoritative implementation spec for the project.
> It defines every entity, every endpoint, every processing boundary, and every eval
> criterion precisely enough that an engineer (or agent) can implement any module cold.
>
> **Scope**: `agents/ai-hedge-fund/` — backend, frontend, agents, backtester, evals.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Domain Model](#2-domain-model)
3. [API Contract](#3-api-contract)
4. [Processing Architecture](#4-processing-architecture)
5. [Agent System](#5-agent-system)
6. [Eval Framework](#6-eval-framework)
7. [Deployment & Infrastructure](#7-deployment--infrastructure)
8. [Constraints & Conventions](#8-constraints--conventions)

---

## 1. System Overview

SynQubi is a multi-agent AI hedge fund that simulates investment decisions using 22 LLM-powered
analyst agents modelled after real-world investors (Buffett, Burry, Druckenmiller, etc.).
Users configure a portfolio of tickers and an agent graph through a React frontend; the backend
runs the graph, streams progress events, and persists results to SQLite.

**User types**

| User | Goal |
|---|---|
| Researcher | Runs backtests to evaluate agent strategy quality |
| Analyst | Runs live hedge fund sessions to get current trading signals |
| API Consumer | Sends tweets for sentiment/clustering analysis via `/api/v1/conversations` |
| CI / eval runner | Runs `evals/model_comparison.py` to benchmark Grok model variants |

**Tech stack**

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind + shadcn/ui |
| Backend | Python 3.11 + FastAPI + SQLAlchemy + SQLite |
| Agents | LangGraph + LangChain (22 investor agents) |
| LLM default | `grok-3-fast` via `langchain-xai` (`XAI_API_KEY`) |
| Deployment | AWS Amplify (frontend) + AWS App Runner via ECR (backend) |

---

## 2. Domain Model

### 2.1 Persistent entities (SQLite tables)

#### `hedge_fund_flows`

Stores React Flow graph configurations (the "strategy template").

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, autoincrement | |
| `name` | VARCHAR(200) | NOT NULL | Display name |
| `description` | TEXT | nullable | |
| `nodes` | JSON | NOT NULL | React Flow node array |
| `edges` | JSON | NOT NULL | React Flow edge array |
| `viewport` | JSON | nullable | Zoom / pan state |
| `data` | JSON | nullable | Node internal states (tickers, models) |
| `is_template` | BOOLEAN | default false | |
| `tags` | JSON | nullable | List of string tags |
| `created_at` | DATETIME | server default now | |
| `updated_at` | DATETIME | onupdate now | |

#### `hedge_fund_flow_runs`

One row per execution of a flow.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `flow_id` | INTEGER | FK → `hedge_fund_flows.id` | |
| `status` | VARCHAR(50) | NOT NULL, default `IDLE` | `IDLE \| IN_PROGRESS \| COMPLETE \| ERROR` |
| `trading_mode` | VARCHAR(50) | NOT NULL, default `one-time` | `one-time \| continuous \| advisory` |
| `schedule` | VARCHAR(50) | nullable | `hourly \| daily \| weekly` |
| `duration` | VARCHAR(50) | nullable | `1day \| 1week \| 1month` |
| `request_data` | JSON | nullable | Original request parameters |
| `initial_portfolio` | JSON | nullable | Portfolio at run start |
| `final_portfolio` | JSON | nullable | Portfolio at run end |
| `results` | JSON | nullable | Full output from all agents |
| `error_message` | TEXT | nullable | |
| `run_number` | INTEGER | NOT NULL, default 1 | Sequential within flow |
| `started_at` | DATETIME | nullable | |
| `completed_at` | DATETIME | nullable | |
| `created_at` | DATETIME | server default now | |
| `updated_at` | DATETIME | onupdate now | |

#### `hedge_fund_flow_run_cycles`

One row per analysis cycle within a run (for continuous trading mode).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `flow_run_id` | INTEGER | FK → `hedge_fund_flow_runs.id` | |
| `cycle_number` | INTEGER | NOT NULL | 1-indexed within run |
| `analyst_signals` | JSON | nullable | All agent signal outputs |
| `trading_decisions` | JSON | nullable | Portfolio manager orders |
| `executed_trades` | JSON | nullable | Paper trades executed |
| `portfolio_snapshot` | JSON | nullable | Cash + positions after cycle |
| `performance_metrics` | JSON | nullable | Sharpe, drawdown, etc. |
| `status` | VARCHAR(50) | NOT NULL, default `IN_PROGRESS` | `IN_PROGRESS \| COMPLETED \| ERROR` |
| `error_message` | TEXT | nullable | |
| `llm_calls_count` | INTEGER | nullable, default 0 | |
| `api_calls_count` | INTEGER | nullable, default 0 | |
| `estimated_cost` | VARCHAR(20) | nullable | USD string |
| `trigger_reason` | VARCHAR(100) | nullable | `scheduled \| manual \| market_event` |
| `market_conditions` | JSON | nullable | Price snapshot at cycle start |
| `started_at` | DATETIME | NOT NULL | |
| `completed_at` | DATETIME | nullable | |
| `created_at` | DATETIME | server default now | |

#### `api_keys`

Encrypted (plain in dev) per-provider API key store.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `provider` | VARCHAR(100) | NOT NULL, UNIQUE | e.g. `XAI_API_KEY` |
| `key_value` | TEXT | NOT NULL | The raw key |
| `is_active` | BOOLEAN | default true | |
| `description` | TEXT | nullable | |
| `last_used` | DATETIME | nullable | |
| `created_at` | DATETIME | server default now | |
| `updated_at` | DATETIME | onupdate now | |

#### `threads`

Tracks the async processing status of a conversation thread (xAI challenge).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `thread_id` | VARCHAR | PK | Caller-supplied ID |
| `status` | VARCHAR(20) | NOT NULL, default `queued` | `queued \| processing \| done \| failed` |
| `created_at` | DATETIME | server default now | |
| `updated_at` | DATETIME | onupdate now | |

**Status machine**: `queued → processing → done` or `processing → failed` (after 3 retries).

#### `tweets`

Individual messages belonging to a thread.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `tweet_id` | VARCHAR | PK | Caller-supplied ID |
| `thread_id` | VARCHAR | FK → `threads.thread_id`, index | |
| `user_id` | VARCHAR | nullable | |
| `text` | TEXT | NOT NULL | Raw content |
| `timestamp` | DATETIME(tz) | nullable | Source timestamp |
| `created_at` | DATETIME | server default now | |

#### `analysis`

Grok-generated output for a thread (one row per thread).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `thread_id` | VARCHAR | FK → `threads.thread_id`, UNIQUE | |
| `sentiment_score` | FLOAT | nullable | −1.0 (negative) → 1.0 (positive) |
| `clusters` | JSON | nullable | `list[str]` of topic tags |
| `confidence` | FLOAT | nullable | 0.0 → 1.0 |
| `reasoning` | TEXT | nullable | One-sentence explanation |
| `created_at` | DATETIME | server default now | |

### 2.2 In-memory / transient state

| Name | Location | Type | Description |
|---|---|---|---|
| `AgentState` | `src/graph/state.py` | `TypedDict` | LangGraph message + data + metadata |
| `job_store` | `app/backend/services/job_store.py` | in-process dict | Maps job_id → `JobStatus` for streaming runs |
| `_queue` | `app/backend/routes/conversations.py` | `asyncio.Queue[str]` | thread_ids awaiting Grok analysis |
| `_inbound_bucket` | `app/backend/routes/conversations.py` | `_TokenBucket(100/s)` | Rate limiter for POST /conversations |
| `_outbound_bucket` | `app/backend/routes/conversations.py` | `_TokenBucket(10/s)` | Rate limiter for Grok API calls |

---

## 3. API Contract

Base URL (local): `http://localhost:8000`
Base URL (prod): `https://3k23thsjhf.us-east-2.awsapprunner.com`

All request/response bodies are JSON. All datetimes are ISO 8601.

### 3.1 Health

#### `GET /`
Returns welcome message.
```json
{ "message": "Welcome to AI Hedge Fund API" }
```

#### `GET /ping`
SSE stream of 5 ping events (1 second apart), for connectivity testing.
```
Content-Type: text/event-stream
data: {"ping": "ping 1/5", "timestamp": 1}
```

### 3.2 Hedge Fund

#### `POST /hedge-fund/run`
Run the agent graph against current market data. Streams SSE progress events.

**Request**
```json
{
  "tickers": ["AAPL", "NVDA"],
  "graph_nodes": [{ "id": "warren_buffett_agent_1", "type": "agent", "data": {}, "position": {} }],
  "graph_edges": [{ "id": "e1", "source": "warren_buffett_agent_1", "target": "portfolio_manager_agent_1" }],
  "agent_models": [{ "agent_id": "warren_buffett_agent_1", "model_name": "grok-3-fast", "model_provider": "xAI" }],
  "model_name": "grok-3-fast",
  "model_provider": "xAI",
  "initial_cash": 100000.0,
  "margin_requirement": 0.0,
  "portfolio_positions": null,
  "api_keys": { "XAI_API_KEY": "xai-..." },
  "end_date": "2025-04-24",
  "start_date": null
}
```

**SSE event types**

| Event type | Payload fields |
|---|---|
| `start` | `job_id`, `timestamp` |
| `progress` | `agent_id`, `ticker`, `status`, `analysis` (optional) |
| `complete` | `decisions`, `analyst_signals` |
| `error` | `message`, `error` |

#### `POST /hedge-fund/backtest`
Run a backtest over a date range. Returns JSON (not streaming).

**Request** — same as `/run` plus:
```json
{ "start_date": "2024-01-01", "end_date": "2025-01-01", "initial_capital": 100000.0 }
```

**Response**
```json
{
  "results": [
    {
      "date": "2024-01-02",
      "portfolio_value": 100500.0,
      "cash": 98000.0,
      "decisions": {},
      "executed_trades": { "AAPL": 10 },
      "analyst_signals": {},
      "current_prices": { "AAPL": 185.2 },
      "long_exposure": 0.02,
      "short_exposure": 0.0,
      "gross_exposure": 0.02,
      "net_exposure": 0.02,
      "long_short_ratio": null
    }
  ],
  "performance_metrics": {
    "sharpe_ratio": 1.42,
    "sortino_ratio": 2.1,
    "max_drawdown": -0.08,
    "max_drawdown_date": "2024-03-15",
    "gross_exposure": 0.45,
    "net_exposure": 0.45,
    "long_short_ratio": null
  },
  "final_portfolio": {}
}
```

#### `POST /hedge-fund/chat`
Single-turn Dexter AI assistant query.

**Request**
```json
{ "prompt": "What is NVDA's P/E?", "tickers": ["NVDA"], "model_name": "grok-3-fast", "model_provider": "xAI", "api_keys": {} }
```
**Response**
```json
{ "response": "NVDA's trailing P/E is ..." }
```

#### `GET /hedge-fund/agents`
Returns list of all available analyst agents.

### 3.3 Flows

#### `GET /flows` → `list[FlowSummaryResponse]`
#### `POST /flows` body: `FlowCreateRequest` → `FlowResponse` (201)
#### `GET /flows/{flow_id}` → `FlowResponse`
#### `PUT /flows/{flow_id}` body: `FlowUpdateRequest` → `FlowResponse`
#### `DELETE /flows/{flow_id}` → 204

**`FlowCreateRequest`**
```json
{
  "name": "Buffett + Munger Strategy",
  "description": null,
  "nodes": [],
  "edges": [],
  "viewport": null,
  "data": null,
  "is_template": false,
  "tags": ["value"]
}
```

### 3.4 Flow Runs

#### `GET /flows/{flow_id}/runs` → `list[FlowRunSummaryResponse]`
#### `POST /flows/{flow_id}/runs` → `FlowRunResponse` (201)
#### `GET /flows/{flow_id}/runs/{run_id}` → `FlowRunResponse`
#### `PATCH /flows/{flow_id}/runs/{run_id}` body: `FlowRunUpdateRequest` → `FlowRunResponse`

**Status values**: `IDLE | IN_PROGRESS | COMPLETE | ERROR`

### 3.5 Conversations (xAI Challenge)

#### `POST /api/v1/conversations`

Accept a tweet/conversation for async Grok analysis.

**Rate limit**: 100 req/s (token bucket). Excess → `429` with `Retry-After: 1`.

**Request**
```json
{
  "tweet_id": "t_001",
  "thread_id": "thread_42",
  "user_id": "u_99",
  "text": "My order hasn't arrived after 3 weeks. This is unacceptable!",
  "timestamp": "2025-04-24T10:00:00Z"
}
```

**202 Response**
```json
{ "thread_id": "thread_42", "status": "queued", "message": "Conversation queued for analysis" }
```

**429 Response** (`Retry-After: 1` header)
```json
{ "detail": "Rate limit exceeded" }
```

#### `GET /api/v1/conversations/{thread_id}`

**200 Response** (while processing)
```json
{ "thread_id": "thread_42", "status": "processing", "analysis": null }
```

**200 Response** (done)
```json
{
  "thread_id": "thread_42",
  "status": "done",
  "analysis": {
    "sentiment_score": -0.75,
    "clusters": ["delivery_problems", "product_issues"],
    "confidence": 0.91,
    "reasoning": "Strong negative sentiment due to delayed delivery complaint."
  }
}
```

**404 Response**
```json
{ "detail": "Thread not found" }
```

### 3.6 API Keys

#### `GET /api-keys` → `list[ApiKeySummaryResponse]` (keys redacted)
#### `POST /api-keys` body: `ApiKeyCreateRequest` → `ApiKeyResponse` (201)
#### `PUT /api-keys/{provider}` body: `ApiKeyUpdateRequest` → `ApiKeyResponse`
#### `DELETE /api-keys/{provider}` → 204
#### `POST /api-keys/bulk` body: `ApiKeyBulkUpdateRequest` → `list[ApiKeyResponse]`

### 3.7 Language Models

#### `GET /language-models` → list of `{ display_name, model_name, provider }` for all configured LLMs.

### 3.8 Ollama (local models)

#### `GET /ollama/status` → `{ installed: bool, running: bool, server_url: str, available_models: list[str] }`
#### `GET /ollama/models` → list of available Ollama models
#### `POST /ollama/pull` body: `{ model: str }` → SSE stream of pull progress

### 3.9 Storage (file-based)

#### `GET /storage/outputs` → list of saved run output files
#### `GET /storage/outputs/{filename}` → file download
#### `DELETE /storage/outputs/{filename}` → 204

---

## 4. Processing Architecture

### 4.1 Hedge fund run (streaming)

```
Client                Backend                    LangGraph
  │                      │                           │
  ├─POST /hedge-fund/run─►│                           │
  │                      ├─create job_id             │
  │                      ├─create_graph()─────────────►│
  │◄─SSE stream open─────┤                           │
  │                      ├─run_graph_async()─────────►│
  │◄─progress events──────┤◄──agent callbacks─────────┤
  │◄─complete event───────┤◄──final state─────────────┤
```

- `progress.update_status(agent_id, ticker, status)` emits to SSE via `job_store`
- Client disconnect detected via `request.receive()` loop; cancels the graph task
- Each agent node calls `call_llm()` → retries 3× with exponential backoff on failure

### 4.2 Conversations worker (async)

```
POST /api/v1/conversations
  │
  ├─ token bucket check (100/s) → 429 if exceeded
  ├─ upsert Thread (status=queued), upsert Tweet
  ├─ asyncio.Queue.put(thread_id)
  └─ return 202

Background worker (started at app startup via asyncio.create_task):
  loop:
    thread_id = await queue.get()
    Thread.status = processing
    tweets = SELECT * FROM tweets WHERE thread_id = ?
    prompt = GROK_PROMPT.format(text=joined_tweets)
    for attempt in 0..2:
      wait for outbound token bucket (10/s)
      response = grok_llm.invoke(prompt)
      parsed = json.loads(response.content)
      upsert Analysis row
      Thread.status = done
      break
    else:
      Thread.status = failed
```

**Retry policy**: attempts 0, 1, 2 → sleep `2^attempt` seconds between retries (1s, 2s, 4s).

**Grok prompt contract**:
```
Analyze the following customer support conversation and return a JSON object with these exact fields:
- sentiment_score: float from -1.0 (very negative) to 1.0 (very positive)
- clusters: list of strings from: ["product_issues", "delivery_problems", "billing",
  "praise", "refund_request", "technical_support", "account_issues", "shipping"]
- confidence: float from 0.0 to 1.0
- reasoning: one sentence explaining the classification

Conversation:
{text}

Respond with valid JSON only, no markdown.
```

### 4.3 Backtester

```
BacktestRequest
  │
  ├─ BacktestService.run_backtest()
  │   ├─ for each date in [start_date, end_date]:
  │   │   ├─ compile LangGraph
  │   │   ├─ run all agents with historical data up to date (no look-ahead)
  │   │   ├─ portfolio_manager makes decisions
  │   │   ├─ BacktestTrader executes paper trades
  │   │   └─ record BacktestDayResult
  │   └─ compute_performance_metrics(day_results)
  └─ return BacktestResponse
```

Performance metrics computed:

| Metric | Formula |
|---|---|
| Sharpe ratio | `mean(daily_excess_returns) / std(daily_excess_returns) × √252` |
| Sortino ratio | `mean(daily_excess_returns) / std(negative_returns) × √252` |
| Max drawdown | `min((value - running_max) / running_max)` |
| Gross exposure | `(long_value + abs(short_value)) / portfolio_value` |
| Net exposure | `(long_value - abs(short_value)) / portfolio_value` |

### 4.4 Agent graph wiring

Each flow is a directed graph of LangGraph nodes:

```
analyst_agent_1 ──┐
analyst_agent_2 ──┤
analyst_agent_N ──► risk_manager_agent ──► portfolio_manager_agent
```

- Node IDs in React Flow are `{agent_key}_{index}` (e.g. `warren_buffett_agent_1`)
- `extract_base_agent_key()` strips the index suffix to map to the Python agent function
- `AgentState.data.analyst_signals[agent_id]` accumulates all signals
- Portfolio manager reads `analyst_signals` to produce final `decisions`

---

## 5. Agent System

### 5.1 Investor agents (22 total)

| Agent key | Investor | Style |
|---|---|---|
| `aswath_damodaran_agent` | Aswath Damodaran | Story + numbers valuation |
| `ben_graham_agent` | Benjamin Graham | Deep value, margin of safety |
| `bill_ackman_agent` | Bill Ackman | Activist, concentrated positions |
| `cathie_wood_agent` | Cathie Wood | Disruptive growth |
| `charlie_munger_agent` | Charlie Munger | Quality at fair price |
| `devils_advocate_agent` | — | Contrarian stress-tester |
| `fundamentals_agent` | — | Financial statement analysis |
| `growth_agent` | — | Growth metrics |
| `michael_burry_agent` | Michael Burry | Contrarian deep value |
| `mohnish_pabrai_agent` | Mohnish Pabrai | Dhandho, doubles at low risk |
| `news_sentiment_agent` | — | LLM-classified news sentiment |
| `peter_lynch_agent` | Peter Lynch | Ten-baggers from everyday life |
| `phil_fisher_agent` | Phil Fisher | Scuttlebutt growth research |
| `portfolio_manager_agent` | — | Final decision maker |
| `rakesh_jhunjhunwala_agent` | Rakesh Jhunjhunwala | Indian growth + value |
| `risk_manager_agent` | — | Position sizing + risk limits |
| `sentiment_agent` | — | Insider trades + news signals |
| `stanley_druckenmiller_agent` | Stanley Druckenmiller | Macro + asymmetric upside |
| `technicals_agent` | — | Technical indicators |
| `valuation_agent` | — | DCF + multiples |
| `warren_buffett_agent` | Warren Buffett | Wonderful companies, fair price |
| `dexter_agent` | — | Autonomous research + chat |

### 5.2 Signal output schema

Every analyst agent writes to `state["data"]["analyst_signals"][agent_id]`:

```json
{
  "AAPL": {
    "signal": "bullish | bearish | neutral",
    "confidence": 72.5,
    "reasoning": { ... }
  }
}
```

`confidence` is a float 0–100. `reasoning` is agent-specific structured JSON.

### 5.3 LLM call conventions

All agents call `call_llm(prompt, PydanticModel, agent_name, state)` from `src/utils/llm.py`.

- Model resolved from `state.metadata.request.get_agent_model_config(agent_id)`, falling back to `AIF_DEFAULT_MODEL` / `AIF_DEFAULT_PROVIDER` env vars (default: `grok-3-fast` / `xAI`)
- 3 retries with progress status updates
- Structured output via `llm.with_structured_output(model, method="json_mode")` for JSON-mode models; manual JSON extraction for DeepSeek / Gemini

---

## 6. Eval Framework

Location: `agents/ai-hedge-fund/evals/`

### 6.1 Model comparison (`evals/model_comparison.py`)

Compares `grok-3` vs `grok-3-fast` on 5 financial analyst test cases.

**Scoring dimensions**

| Dimension | Method | Weight | Max pts |
|---|---|---|---|
| Reasoning coherence | LLM judge (0–10 scale, grok-3-fast judge) | ×0.6 | 6 |
| Look-ahead bias | Regex pattern detection (0/1: clean/biased) | ×2 | 2 |
| Math accuracy | Required term presence check (0/1) | ×2 | 2 |
| **Composite** | | | **10** |

**Composite formula**: `coherence × 0.6 + bias_clean × 2 + math_correct × 2`

**Test cases**

| ID | Category | What it tests |
|---|---|---|
| `tc01_mean_reversion_strategy` | strategy_design | Z-score formula + look-ahead proof + correct rolling window code |
| `tc02_sharpe_ratio` | math | Annualised Sharpe implementation + correct unit tests |
| `tc03_bias_detection` | bias_detection | Identify 3 look-ahead bias instances in provided code |
| `tc04_portfolio_optimisation` | math | Markowitz mean-variance + scipy max-Sharpe implementation |
| `tc05_reasoning_sandbox` | strategy_design | Identify ≥4 statistical flaws in an overfit Sharpe claim |

**Output**: `evals/results/comparison_<timestamp>.json` + stdout table.

**Run command**:
```bash
cd agents/ai-hedge-fund
XAI_API_KEY=<key> poetry run python evals/model_comparison.py
```

### 6.2 Adding a new eval

1. Add a `TestCase` instance to `TEST_CASES` in `evals/model_comparison.py`
2. Set `bias_patterns` (regex list) if the task generates code that could have look-ahead bias
3. Set `required_math_terms` if the task requires specific mathematical constructs
4. Set `judge_criteria` to a one-sentence rubric for the LLM judge

---

## 7. Deployment & Infrastructure

### 7.1 Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `XAI_API_KEY` | Yes (prod) | — | xAI / Grok API key |
| `FINANCIAL_DATASETS_API_KEY` | Yes (prod) | — | Financial data API |
| `AIF_DEFAULT_MODEL` | No | `grok-3-fast` | Default LLM model name |
| `AIF_DEFAULT_PROVIDER` | No | `xAI` | Default LLM provider |
| `FRONTEND_URL` | No | — | Amplify URL added to CORS allow-list |
| `OPENAI_API_KEY` | Optional | — | For OpenAI models |
| `ANTHROPIC_API_KEY` | Optional | — | For Claude models |
| `GROQ_API_KEY` | Optional | — | For Groq models |
| `OLLAMA_HOST` | No | `localhost` | Ollama host (Docker: `host.docker.internal`) |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Full Ollama URL override |

### 7.2 Build + deploy backend

```bash
cd agents/ai-hedge-fund
docker build --platform linux/amd64 -f docker/Dockerfile -t synqubi-backend .
docker tag synqubi-backend:latest 193577458182.dkr.ecr.us-east-2.amazonaws.com/synqubi-backend:latest
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 193577458182.dkr.ecr.us-east-2.amazonaws.com
docker push 193577458182.dkr.ecr.us-east-2.amazonaws.com/synqubi-backend:latest
# App Runner auto-deploys on new ECR push
```

### 7.3 Local development

```bash
# Backend (from agents/ai-hedge-fund/)
poetry run uvicorn app.backend.main:app --reload --port 8000

# Frontend (from agents/ai-hedge-fund/app/frontend/)
npm run dev   # http://localhost:5173
```

### 7.4 Infrastructure IDs

| Resource | ID / URL |
|---|---|
| AWS region | `us-east-2` |
| AWS account | `193577458182` |
| ECR repo | `193577458182.dkr.ecr.us-east-2.amazonaws.com/synqubi-backend` |
| App Runner URL | `https://3k23thsjhf.us-east-2.awsapprunner.com` |
| Amplify app ID | `d1y5s8pvr1s6aw` |
| Amplify URL | `https://d1y5s8pvr1s6aw.amplifyapp.com` |

---

## 8. Constraints & Conventions

### File layout

```
agents/ai-hedge-fund/
├── app/
│   ├── backend/
│   │   ├── main.py                  # FastAPI app, startup hooks
│   │   ├── routes/                  # One file per route group
│   │   ├── services/                # Business logic (no DB access)
│   │   ├── repositories/            # DB access layer
│   │   ├── database/
│   │   │   ├── connection.py        # engine, SessionLocal, get_db
│   │   │   └── models.py            # All SQLAlchemy table classes
│   │   └── models/
│   │       └── schemas.py           # All Pydantic request/response models
│   └── frontend/                    # React + Vite
├── src/
│   ├── agents/                      # 22 investor agent functions
│   ├── backtesting/                 # Backtest engine + metrics
│   ├── data/                        # Data models + fetchers
│   ├── graph/                       # LangGraph state + wiring
│   ├── llm/                         # Model registry, get_model()
│   ├── tools/                       # Financial data API tools
│   └── utils/                       # llm.py, progress.py, etc.
├── evals/
│   └── model_comparison.py          # grok-3 vs grok-3-fast benchmark
├── dexter/                          # Autonomous research agent (Bun + TS)
├── docker/
│   └── Dockerfile                   # linux/amd64 target for App Runner
└── SPEC.md                          # ← this file
```

### Coding conventions

- **New routes**: add file to `app/backend/routes/`, register in `routes/__init__.py`
- **New DB tables**: append to `app/backend/database/models.py`; `Base.metadata.create_all()` runs at startup
- **New Pydantic schemas**: append to `app/backend/models/schemas.py`
- **Docker builds**: always use `--platform linux/amd64` (Mac builds arm64 by default)
- **Frontend env vars**: `VITE_API_URL` is build-time; must be set in Amplify + triggers rebuild
- **Model defaults**: never hardcode model names; read from `AIF_DEFAULT_MODEL` / `AIF_DEFAULT_PROVIDER`
- **LLM calls**: always go through `call_llm()` in `src/utils/llm.py` for retry + structured output handling
- **CORS**: add new origins via `FRONTEND_URL` env var, not by hardcoding in `main.py`
