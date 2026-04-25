"""
POST /api/v1/conversations  — queue a tweet/conversation for Grok sentiment analysis
GET  /api/v1/conversations/{thread_id} — poll for results

Rate limits:
  Inbound:  100 req/s  (token bucket) → 429 + Retry-After: 1
  Outbound: 10 calls/s to Grok (token bucket)

Processing flow:
  1. POST saves tweet + thread (status=queued) → returns 202
  2. Background worker picks up thread_id from asyncio.Queue
  3. Worker fetches all tweets for thread → calls Grok → stores Analysis
  4. Thread status → done (or failed after 3 retries with exponential backoff)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.backend.database.connection import get_db
from app.backend.database.models import Analysis, Thread, Tweet

# ── LLM import (path relative to repo root: agents/ai-hedge-fund/) ──────────
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.llm.models import ModelProvider, get_model  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Token-bucket rate limiters ────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe async token bucket."""

    def __init__(self, rate: float, capacity: float):
        self._rate = rate          # tokens added per second
        self._capacity = capacity  # max tokens
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: float = 1.0) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


_inbound_bucket = _TokenBucket(rate=100, capacity=100)   # 100 req/s
_outbound_bucket = _TokenBucket(rate=10, capacity=10)     # 10 Grok calls/s

# ── Async processing queue ────────────────────────────────────────────────────

_queue: asyncio.Queue[str] = asyncio.Queue()
_GROK_PROMPT = """\
Analyze the following customer support conversation and return a JSON object with these exact fields:
- sentiment_score: float from -1.0 (very negative) to 1.0 (very positive)
- clusters: list of strings, topic tags from: ["product_issues", "delivery_problems", "billing", "praise", "refund_request", "technical_support", "account_issues", "shipping"]
- confidence: float from 0.0 to 1.0
- reasoning: one sentence explaining the classification

Conversation:
{text}

Respond with valid JSON only, no markdown."""


def _get_grok_llm():
    """Instantiate Grok model (lazy, so import errors surface at call time)."""
    return get_model("grok-3-fast", ModelProvider.XAI)


def _parse_grok_response(content: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def _process_thread(thread_id: str, db: Session, max_retries: int = 3):
    """Fetch tweets for thread, call Grok, store Analysis, update Thread status."""
    # Mark processing
    thread = db.query(Thread).filter(Thread.thread_id == thread_id).first()
    if not thread:
        logger.warning("Worker: thread %s not found in DB", thread_id)
        return

    thread.status = "processing"
    db.commit()

    tweets = db.query(Tweet).filter(Tweet.tweet_id == thread_id).all()
    # Also fetch by thread_id (tweets whose thread_id matches)
    thread_tweets = db.query(Tweet).filter(Tweet.thread_id == thread_id).all()
    all_texts = [t.text for t in thread_tweets]
    if not all_texts:
        # Fallback: the submitted tweet itself may have tweet_id == thread_id
        single = db.query(Tweet).filter(Tweet.tweet_id == thread_id).first()
        if single:
            all_texts = [single.text]

    conversation_text = "\n".join(all_texts) if all_texts else "(no text)"
    prompt = _GROK_PROMPT.format(text=conversation_text)

    last_error = None
    for attempt in range(max_retries):
        # Wait for outbound rate limit slot
        while not await _outbound_bucket.consume():
            await asyncio.sleep(0.1)

        try:
            llm = _get_grok_llm()
            response = await asyncio.get_event_loop().run_in_executor(
                None, llm.invoke, prompt
            )
            parsed = _parse_grok_response(response.content)

            # Validate required fields
            sentiment_score = float(parsed["sentiment_score"])
            clusters = parsed.get("clusters", [])
            confidence = float(parsed.get("confidence", 0.0))
            reasoning = str(parsed.get("reasoning", ""))

            # Upsert Analysis row
            existing = db.query(Analysis).filter(Analysis.thread_id == thread_id).first()
            if existing:
                existing.sentiment_score = sentiment_score
                existing.clusters = clusters
                existing.confidence = confidence
                existing.reasoning = reasoning
            else:
                db.add(Analysis(
                    thread_id=thread_id,
                    sentiment_score=sentiment_score,
                    clusters=clusters,
                    confidence=confidence,
                    reasoning=reasoning,
                ))

            thread.status = "done"
            db.commit()
            logger.info("Worker: thread %s → done", thread_id)
            return

        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                "Worker: thread %s attempt %d/%d failed (%s), retrying in %ds",
                thread_id, attempt + 1, max_retries, exc, wait,
            )
            await asyncio.sleep(wait)

    # All retries exhausted
    thread.status = "failed"
    db.commit()
    logger.error("Worker: thread %s failed after %d attempts: %s", thread_id, max_retries, last_error)


async def start_conversation_worker():
    """Background worker — runs forever, drains the queue."""
    from app.backend.database.connection import SessionLocal

    logger.info("Conversation worker started")
    while True:
        thread_id = await _queue.get()
        db = SessionLocal()
        try:
            await _process_thread(thread_id, db)
        except Exception as exc:
            logger.exception("Worker: unhandled error for thread %s: %s", thread_id, exc)
        finally:
            db.close()
            _queue.task_done()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ConversationIn(BaseModel):
    tweet_id: str
    thread_id: str
    user_id: Optional[str] = None
    text: str
    timestamp: Optional[str] = None   # ISO8601


class AnalysisOut(BaseModel):
    sentiment_score: Optional[float]
    clusters: Optional[List[str]]
    confidence: Optional[float]
    reasoning: Optional[str]


class ConversationStatusOut(BaseModel):
    thread_id: str
    status: str
    analysis: Optional[AnalysisOut]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/v1/conversations", status_code=202)
async def submit_conversation(
    body: ConversationIn,
    db: Session = Depends(get_db),
):
    """Accept a tweet/conversation for async sentiment analysis."""
    # Inbound rate limit
    if not await _inbound_bucket.consume():
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "1"},
        )

    # Upsert Thread
    thread = db.query(Thread).filter(Thread.thread_id == body.thread_id).first()
    if not thread:
        thread = Thread(thread_id=body.thread_id, status="queued")
        db.add(thread)

    # Parse optional timestamp
    ts: Optional[datetime] = None
    if body.timestamp:
        try:
            ts = datetime.fromisoformat(body.timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Upsert Tweet (idempotent on tweet_id)
    existing_tweet = db.query(Tweet).filter(Tweet.tweet_id == body.tweet_id).first()
    if not existing_tweet:
        db.add(Tweet(
            tweet_id=body.tweet_id,
            thread_id=body.thread_id,
            user_id=body.user_id,
            text=body.text,
            timestamp=ts,
        ))

    db.commit()

    # Enqueue for processing
    await _queue.put(body.thread_id)

    return JSONResponse(
        status_code=202,
        content={
            "thread_id": body.thread_id,
            "status": "queued",
            "message": "Conversation queued for analysis",
        },
    )


@router.get("/api/v1/conversations/{thread_id}", response_model=ConversationStatusOut)
async def get_conversation_status(
    thread_id: str,
    db: Session = Depends(get_db),
):
    """Poll for the analysis result of a thread."""
    thread = db.query(Thread).filter(Thread.thread_id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    analysis_row = db.query(Analysis).filter(Analysis.thread_id == thread_id).first()
    analysis_out = None
    if analysis_row:
        analysis_out = AnalysisOut(
            sentiment_score=analysis_row.sentiment_score,
            clusters=analysis_row.clusters,
            confidence=analysis_row.confidence,
            reasoning=analysis_row.reasoning,
        )

    return ConversationStatusOut(
        thread_id=thread_id,
        status=thread.status,
        analysis=analysis_out,
    )
