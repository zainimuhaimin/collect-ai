"""Protocol bersama untuk klien LLM (post-presentation-review-tasks.md TASK-E5).

`GeminiClient.generate()` (services/gemini_client.py:55) sudah PERSIS bentuk
ini — ekstraksi murni untuk dokumentasi/typing, TIDAK mengubah perilaku
`GeminiClient` sama sekali (duck typing: kelas mana pun dengan method
`generate(system_instruction, payload, response_schema) -> LlmResult` sudah
memenuhi Protocol ini tanpa perlu inheritance eksplisit).

Dipakai supaya `ai_reasoning_eval.py` (Tier 2, LLM-as-judge) bisa menerima
`GeminiClient` ATAU `OpenAiCompatibleClient` (services/openai_compat_client.py)
secara seragam."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass
class LlmResult:
    text: str                     # raw JSON text dari respons (belum di-parse)
    model_used: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: int = 0


class LlmError(Exception):
    """Basis error lintas provider. `kind` konsisten dengan `GeminiError`
    (`gemini_client.py`) supaya caller (ai_reasoning_eval.py) bisa menangani
    kegagalan provider mana pun dengan cara yang sama: 'timeout' | 'quota' |
    'http' | 'invalid_response'."""

    def __init__(self, message: str, kind: str):
        super().__init__(message)
        self.kind = kind


@runtime_checkable
class LlmClient(Protocol):
    def generate(self, system_instruction: str, payload: dict, response_schema: dict) -> LlmResult: ...
