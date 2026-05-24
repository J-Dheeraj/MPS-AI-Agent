"""
Ollama client with LLM request queue
Max 3 concurrent requests, priority tiers: urgent > normal > low
"""
import asyncio
import json
import httpx
import os
from typing import AsyncGenerator
from enum import IntEnum

OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
MAX_CONCURRENT = 3

class Priority(IntEnum):
    URGENT = 0   # eviction, medical, visa expiry
    NORMAL = 1   # standard draft requests
    LOW    = 2   # policy Q&A, background tasks

class LLMQueue:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._queue_depth = 0

    def depth(self) -> int:
        return self._queue_depth

    async def run(self, messages: list, priority: Priority = Priority.NORMAL,
                  stream: bool = True) -> AsyncGenerator[str, None]:
        self._queue_depth += 1
        try:
            async with self._semaphore:
                self._queue_depth -= 1
                async for chunk in self._call_ollama(messages, stream):
                    yield chunk
        except Exception:
            self._queue_depth = max(0, self._queue_depth - 1)
            raise

    async def _call_ollama(self, messages: list, stream: bool) -> AsyncGenerator[str, None]:
        payload = {
            "model":    OLLAMA_MODEL,
            "messages": messages,
            "stream":   stream,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

# Singleton queue instance
llm_queue = LLMQueue()

# ── Prompt builders ───────────────────────────

LETTER_SYSTEM = """You are a letter drafting assistant for Singapore Meet-the-People Sessions (MPS).
Draft a formal appeal letter from the MP to the relevant Singapore government agency.

Letter structure (always follow this exactly):
1. SITUATION — factual background, dates, reference numbers
2. REQUEST — ONE clear ask only (appeal decision / expedite / waive fee / review eligibility / arrange meeting)
3. CONTEXT — brief mitigating circumstances, no speculation

Tone rules:
- Formal, respectful, factual throughout
- Never promise outcomes or set deadlines for agencies
- Never say the agency acted "wrongly" — use "request for review"
- Urgency language ONLY for: imminent eviction, pending medical procedure, visa expiry, domestic violence, child welfare
- Do not exceed one page
- Mask NRIC to last 3 chars + letter (e.g. S****567A)
- Do not fabricate policy details, agency addresses, or reference numbers

Output the letter only. No commentary before or after."""

REAPPEAL_SYSTEM = LETTER_SYSTEM + """

IMPORTANT — This is a RE-APPEAL of a previously rejected case.
- Acknowledge the previous outcome briefly
- Address the rejection reason directly
- Present any new information or changed circumstances
- Make the case stronger — do not simply repeat the previous letter"""

QA_SYSTEM = """You are a policy assistant helping Singapore MPS volunteers and vetters
understand government policies and agency procedures.

Answer based on your knowledge of Singapore government schemes (HDB, CPF, MOM, MOH, MSF, ICA, IRAS, MOE, LTA, PA/CDCs).
If you are not certain, say so clearly — do not fabricate policy details.
Always note if information may have changed and suggest verification with the agency.
Keep answers concise and practical."""

def build_draft_messages(case_type: str, agency: str, notes: str,
                          is_reappeal: bool = False,
                          previous_letter: str = None,
                          rejection_reason: str = None) -> list:
    system = REAPPEAL_SYSTEM if is_reappeal else LETTER_SYSTEM
    user_content = f"Case type: {case_type}\nAgency: {agency}\n\nVolunteer notes:\n{notes}"
    if is_reappeal and previous_letter:
        user_content += f"\n\nPrevious letter sent:\n{previous_letter}"
    if is_reappeal and rejection_reason:
        user_content += f"\n\nRejection reason given by agency:\n{rejection_reason}"
    return [{"role": "system", "content": system},
            {"role": "user",   "content": user_content}]

def build_qa_messages(question: str, context: str = None) -> list:
    user_content = question
    if context:
        user_content = f"Context from knowledge base:\n{context}\n\nQuestion: {question}"
    return [{"role": "system", "content": QA_SYSTEM},
            {"role": "user",   "content": user_content}]
