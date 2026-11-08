"""Claude Haiku 5.5 adapter for the two engine calls, plus fake and scripted providers.

LLM_PROVIDER ("anthropic" | "fake" | "scripted") and LLM_MODEL are read at call
time, never at import, so tests and the stage fallback can switch them live.
"""
import json
import logging
import os
import time
from dataclasses import dataclass

import anthropic

log = logging.getLogger("pact.llm")

# Plan section 10.3, verbatim.
QUESTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["questions"],
    "properties": {
        "questions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["source", "bank_id", "cue", "text", "target", "reason"],
            "properties": {
                "source": {"enum": ["bank", "new"]},
                "bank_id": {"type": ["string", "null"]},
                "cue": {"enum": ["Follow-up:", "Gap:", "Contradiction:", "Detail:"]},
                "text": {"type": "string"},
                "target": {"type": "string"},
                "reason": {"type": "string"}}}}
    },
}

BOOK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["slot_fills", "contradictions", "rules_mentioned"],
    "properties": {
        "slot_fills": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["contract_id", "slot", "value", "quote", "answered_question_id"],
            "properties": {"contract_id": {"type": "string"}, "slot": {"type": "string"}, "value": {"type": "string"},
                "quote": {"type": "string"}, "answered_question_id": {"type": ["string", "null"]}}}},
        "contradictions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["kind", "statement_a", "statement_b", "rule_id"],
            "properties": {"kind": {"enum": ["person_vs_code", "person_vs_person", "person_vs_self", "person_vs_logs"]},
                "statement_a": {"type": "string"}, "statement_b": {"type": "string"}, "rule_id": {"type": ["string", "null"]}}}},
        "rules_mentioned": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass
class BookResult:
    slot_fills: list
    contradictions: list
    rules_mentioned: list


class LLMRefused(Exception):
    pass


# Recent per-call usage, newest last (for logs and the live cache check).
usage_log: list[dict] = []

_client = None


def _c():
    global _client
    # gzip only: the SDK's httpx2 needs Brotli >= 1.2 for "br" responses, and older
    # Brotli installs (common in conda) crash every call with a connection error.
    _client = _client or anthropic.AsyncAnthropic(default_headers={"Accept-Encoding": "gzip, deflate"})
    return _client


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "anthropic").strip().lower() or "anthropic"


async def _call(kind: str, brief: str, user_input: str, schema: dict, max_tokens: int) -> dict:
    t0 = time.perf_counter()
    resp = await _c().with_options(timeout=6.0).messages.create(
        model=os.environ.get("LLM_MODEL", "claude-haiku-5-5") or "claude-haiku-5-5",
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        system=[{"type": "text", "text": brief, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_input}],
    )
    u = resp.usage
    entry = {
        "kind": kind,
        "ms": round((time.perf_counter() - t0) * 1000),
        "input_tokens": u.input_tokens,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "output_tokens": u.output_tokens,
        "stop_reason": resp.stop_reason,
    }
    usage_log.append(entry)
    del usage_log[:-200]
    log.info("llm %(kind)s %(ms)sms in=%(input_tokens)s cache_read=%(cache_read_input_tokens)s "
             "cache_write=%(cache_creation_input_tokens)s out=%(output_tokens)s stop=%(stop_reason)s", entry)
    if resp.stop_reason == "refusal":
        raise LLMRefused()
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


_FAKE_QUESTION = {"source": "new", "bank_id": None, "cue": "Detail:", "text": "Can you walk me through a normal claim?",
                  "target": "C-02.current_practice", "reason": "fake provider"}


async def complete_questions(brief: str, user_input: str) -> list[dict]:
    p = _provider()
    if p == "fake":
        return [dict(_FAKE_QUESTION)]
    if p == "scripted":
        return []  # the engine falls back to the next plan question
    return (await _call("questions", brief, user_input, QUESTION_SCHEMA, 400))["questions"]


async def complete_bookkeeping(brief: str, user_input: str) -> BookResult:
    if _provider() in ("fake", "scripted"):
        return BookResult([], [], [])
    d = await _call("bookkeeping", brief, user_input, BOOK_SCHEMA, 1024)
    return BookResult(d["slot_fills"], d["contradictions"], d["rules_mentioned"])


async def warm_up(brief: str) -> None:
    hello = "<transcript>\n</transcript>\nThe interview is about to start. Return empty lists."
    await complete_questions(brief, hello)
    await complete_bookkeeping(brief, hello)
