"""Interview session: transcript, debounce, critic, Q-N ids, slot fills, lineage.

Pure state, no I/O except reading kb/people.json and kb/slots.json at creation.
The routes own the timing and the LLM calls.
"""
import re

from server import kb

DEBOUNCE_MS = 1000
MAX_QUEUE = 3
MAX_WORDS = 15
_DIGITS = re.compile(r"\d{4,}")


def mmss(t_ms: int) -> str:
    return f"{t_ms // 60000:02d}:{t_ms // 1000 % 60:02d}"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


class InterviewSession:
    def __init__(self, interview_id: str, interviewee: str, brief: str, bank: dict, plan: list[str] | None = None):
        self.interview_id = interview_id
        self.interviewee = interviewee
        self.brief = brief
        self.bank = bank
        person = kb.load_people().get(interviewee, {})
        self.label = person.get("label", interviewee)
        self.plan = list(plan) if plan is not None else list(person.get("plan", []))
        slots = kb.load_slots()
        self.relevant_contracts = list(person.get("relevant_contracts", []))
        self.slot_ids = [f"{c}.{s}" for c in self.relevant_contracts for s in slots.get(c, [])]

        self.transcript: list[dict] = []          # {"t_ms", "text"}
        self.last_utterance_t = -1
        self.last_called_t = -1
        self.q_counter = 0
        self.plan_index = 0
        self.questions: dict[str, dict] = {}      # every Q-N ever queued, for lineage
        self.queue: list[dict] = []
        self.based_on_t_ms = 0
        self.played: list[dict] = []
        self.slot_fills: dict[str, dict] = {}
        self.contradictions: list[dict] = []
        self.rules_mentioned: set[str] = set()

    # --- transcript and debounce -------------------------------------------------

    def add_utterance(self, text: str, t_ms: int) -> None:
        text = text.strip()
        if not text:
            return
        self.transcript.append({"t_ms": t_ms, "text": text})
        self.last_utterance_t = max(self.last_utterance_t, t_ms)

    def due_for_call(self, now_ms: int) -> bool:
        return self.last_utterance_t > self.last_called_t and now_ms - self.last_utterance_t >= DEBOUNCE_MS

    def begin_call(self) -> tuple[str, int]:
        self.last_called_t = self.last_utterance_t
        events = [(u["t_ms"], 0, f"[{mmss(u['t_ms'])}] {u['text']}") for u in self.transcript]
        events += [(p["played_at"], 1, f"[{p['id']} played at {mmss(p['played_at'])}]") for p in self.played]
        lines = ["<transcript>"] + [e[2] for e in sorted(events, key=lambda e: (e[0], e[1]))] + ["</transcript>"]
        lines.append("Slot status:")
        lines += [f"{sid}: {'filled' if sid in self.slot_fills else 'open'}" for sid in self.slot_ids]
        used = sorted({q["bank_id"] for q in self.played + self.queue if q.get("bank_id")})
        lines.append("Bank IDs used: " + (", ".join(used) if used else "none"))
        return "\n".join(lines), max(self.last_utterance_t, 0)

    # --- questions ----------------------------------------------------------------

    def _resolve(self, item: dict) -> dict | None:
        if item.get("source") == "bank":
            entry = self.bank.get(item.get("bank_id") or "")
            if not entry:
                return None
            return {"bank_id": item["bank_id"], "cue": entry["cue"], "text": entry["text"], "target": entry["target"],
                    "reason": item.get("reason", ""), "audio_url": f"/clips/{item['bank_id']}.mp3"}
        return {"bank_id": None, "cue": item.get("cue", "Follow-up:"), "text": (item.get("text") or "").strip(),
                "target": item.get("target", ""), "reason": item.get("reason", ""), "audio_url": None}

    def _passes_critic(self, q: dict, played_texts: set[str]) -> bool:
        text = q["text"]
        return bool(text) and len(text.split()) <= MAX_WORDS and text.count("?") <= 1 \
            and _norm(text) not in played_texts and q["target"] not in self.slot_fills \
            and not _DIGITS.search(text)

    def _assign(self, q: dict) -> dict:
        self.q_counter += 1
        q = {"id": f"Q-{self.q_counter}", **q}
        self.questions[q["id"]] = q
        return q

    def apply_questions(self, items: list[dict], now_ms: int, based_on_t_ms: int) -> list[dict]:
        played_texts = {_norm(p["text"]) for p in self.played}
        survivors, seen = [], set()
        for item in items:
            q = self._resolve(item)
            if q and self._passes_critic(q, played_texts) and _norm(q["text"]) not in seen:
                seen.add(_norm(q["text"]))
                survivors.append(q)
            if len(survivors) == MAX_QUEUE:
                break
        self.based_on_t_ms = max(self.based_on_t_ms, based_on_t_ms)
        if survivors:
            self.queue = [self._assign({**q, "origin": "ai", "suggested_at": now_ms}) for q in survivors]
        elif not self.queue and self.plan_index < len(self.plan):
            text = self.plan[self.plan_index]
            self.plan_index += 1
            self.queue = [self._assign({"bank_id": None, "cue": "Detail:", "text": text, "target": "plan",
                                        "reason": "fallback plan", "audio_url": None, "origin": "plan",
                                        "suggested_at": now_ms})]
        return self.queue

    def mark_played(self, question_id: str, t_ms: int) -> None:
        q = self.questions.get(question_id, {"id": question_id, "bank_id": None, "text": "", "target": "", "reason": "", "origin": "unknown"})
        self.played.append({"id": question_id, "bank_id": q.get("bank_id"), "text": q.get("text", ""),
                            "target": q.get("target", ""), "reason": q.get("reason", ""),
                            "origin": q.get("origin", "unknown"), "played_at": t_ms})
        self.queue = [x for x in self.queue if x["id"] != question_id]

    # --- bookkeeping --------------------------------------------------------------

    def _origin_of(self, question_id: str | None) -> str:
        if not question_id:
            return "unprompted"
        origin = self.questions.get(question_id, {}).get("origin")
        return {"ai": "ai", "plan": "interviewer"}.get(origin, "unprompted")

    def apply_bookkeeping(self, result) -> None:
        for f in result.slot_fills:
            qid = f.get("answered_question_id")
            origin = self._origin_of(qid)
            cid, slot = f["contract_id"], f["slot"]
            if slot.startswith(f"{cid}."):  # the model sometimes repeats the contract prefix
                slot = slot[len(cid) + 1:]
            self.slot_fills[f"{cid}.{slot}"] = {
                "value": f.get("value", ""), "quote": f.get("quote", ""),
                "question_id": qid if origin != "unprompted" else None, "question_origin": origin,
                "t_ms": self.last_called_t if self.last_called_t >= 0 else None,
            }
        last_played = self.played[-1]["id"] if self.played else None
        def key(c: dict) -> tuple:
            # one entry per (kind, rule); without a rule, per wording
            if c.get("rule_id"):
                return (c.get("kind"), c["rule_id"])
            return (c.get("kind"), _norm(c.get("statement_a", "")), _norm(c.get("statement_b", "")))
        for c in result.contradictions:
            if all(key(x) != key(c) for x in self.contradictions):
                self.contradictions.append({**c, "after_question_id": last_played})
        self.rules_mentioned.update(result.rules_mentioned)

    # --- views --------------------------------------------------------------------

    def queue_message(self) -> dict:
        fields = ("id", "bank_id", "cue", "text", "target", "audio_url")
        return {"type": "queue", "based_on_t_ms": self.based_on_t_ms,
                "questions": [{k: q.get(k) for k in fields} for q in self.queue]}

    def _yield(self) -> float:
        ai_played = [p["id"] for p in self.played if p["origin"] == "ai"]
        if not ai_played:
            return 0.0
        productive = {f["question_id"] for f in self.slot_fills.values() if f["question_id"]}
        productive |= {c["after_question_id"] for c in self.contradictions if c.get("after_question_id")}
        return sum(1 for q in ai_played if q in productive) / len(ai_played)

    def state(self) -> dict:
        filled = sum(1 for sid in self.slot_ids if sid in self.slot_fills)
        return {
            "interview_id": self.interview_id,
            "interviewee": self.interviewee,
            "label": self.label,
            "transcript": list(self.transcript),
            "queue": list(self.queue),
            "based_on_t_ms": self.based_on_t_ms,
            "played": list(self.played),
            "slot_fills": dict(self.slot_fills),
            "contradictions": list(self.contradictions),
            "rules_mentioned": sorted(self.rules_mentioned),
            "coverage": filled / len(self.slot_ids) if self.slot_ids else 0.0,
            "slots": list(self.slot_ids),
            "yield": self._yield(),
        }
