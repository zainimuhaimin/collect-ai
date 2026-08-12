"""Klien LLM provider OpenAI-compatible (`/chat/completions`) — TASK-E5, Tier 2
LLM-as-judge. Satu klien ini menjangkau GLM/Zhipu, DeepSeek, Qwen, OpenRouter,
sampai Ollama lokal dengan hanya mengganti `base_url`/`model`, karena semuanya
berbagi bentuk API yang sama.

Sengaja dipakai sebagai JUDGE (bukan generator utama) supaya keluarga model
beda dari Gemini (generator) — menghilangkan bias self-preference (model
cenderung menyukai output dari keluarganya sendiri).

⚠️ Penegakan JSON LEBIH LEMAH dari Gemini: Gemini punya `responseSchema` yang
benar-benar memaksa bentuk; endpoint ini paling banter `response_format:
{"type": "json_object"}` (menjamin JSON valid, TIDAK menjamin bentuk/field-nya),
dan dukungan `json_schema` yang lebih ketat tidak seragam antar provider — jadi
TIDAK dipakai di sini supaya klien ini tetap portabel lintas provider.
`response_schema` diterjemahkan jadi instruksi teks (properti + enum + wajib)
yang disisipkan ke prompt, BUKAN constraint yang benar-benar ditegakkan server.
Karena itu caller (ai_reasoning_eval.py) WAJIB tetap re-validasi lewat Pydantic
sebelum memakai hasilnya — pola yang sama dipakai generator utama
(`GeminiReasoningOutputSchema.model_validate`, ai_reasoning_service.py:125).
Kegagalan parse/validasi dihitung sebagai *judge failure*, JANGAN dijadikan
skor 0 — itu akan mencemari rata-rata (lihat TASK-E5)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from services.llm_client import LlmError, LlmResult


def _schema_to_instruction(response_schema: dict) -> str:
    """Terjemahkan JSON-schema-ish dict (bentuk yang sama dipakai
    build_response_schema()) jadi instruksi teks — endpoint OpenAI-compatible
    tidak punya constraint schema yang seragam antar provider."""
    props = response_schema.get("properties", {})
    required = response_schema.get("required", [])
    lines = ["Jawab HANYA dengan satu objek JSON valid, TANPA teks lain di luar JSON, dengan properti:"]
    for name, spec in props.items():
        enum = spec.get("enum")
        type_ = spec.get("type", "STRING")
        desc = f" ({', '.join(f'salah satu dari: {enum}' for _ in [0])})" if enum else ""
        req = " [wajib]" if name in required else ""
        lines.append(f"- {name}: tipe {type_}{desc}{req}")
    return "\n".join(lines)


@dataclass
class OpenAiCompatClient:
    base_url: str
    api_keys: list[str]
    model: str
    timeout_seconds: float
    max_key_attempts: int = 3
    _key_index: int = field(default=0, init=False, repr=False)

    def _next_key(self) -> str:
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key

    def generate(self, system_instruction: str, payload: dict, response_schema: dict) -> LlmResult:
        if not self.api_keys:
            raise LlmError("Tidak ada API key judge yang dikonfigurasi", kind="http")

        started = time.monotonic()
        schema_instruction = _schema_to_instruction(response_schema)
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"{system_instruction}\n\n{schema_instruction}"},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            "response_format": {"type": "json_object"},
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"

        attempts = min(self.max_key_attempts, len(self.api_keys))
        last_error: Optional[LlmError] = None
        retried_5xx_this_key = False

        with httpx.Client(timeout=self.timeout_seconds) as client:
            attempt = 0
            while attempt < attempts:
                key = self._next_key()
                headers = {"Authorization": f"Bearer {key}"}
                try:
                    response = client.post(url, headers=headers, json=body)
                except httpx.TimeoutException:
                    raise LlmError("Judge timeout", kind="timeout") from None
                except httpx.ConnectError as exc:
                    if not retried_5xx_this_key:
                        retried_5xx_this_key = True
                        continue
                    last_error = LlmError(f"Judge connect error: {exc}", kind="http")
                    attempt += 1
                    retried_5xx_this_key = False
                    continue

                if response.status_code == 429:
                    last_error = LlmError("Judge quota exceeded (429)", kind="quota")
                    attempt += 1
                    retried_5xx_this_key = False
                    continue

                if response.status_code >= 500:
                    if not retried_5xx_this_key:
                        retried_5xx_this_key = True
                        continue
                    last_error = LlmError(f"Judge server error ({response.status_code})", kind="http")
                    attempt += 1
                    retried_5xx_this_key = False
                    continue

                if response.status_code != 200:
                    raise LlmError(f"Judge HTTP {response.status_code}: {response.text[:300]}", kind="http")

                data = response.json()
                latency_ms = int((time.monotonic() - started) * 1000)
                return _parse_success(data, self.model, latency_ms)

        raise last_error or LlmError("Judge gagal tanpa detail", kind="http")


def _parse_success(data: dict, model: str, latency_ms: int) -> LlmResult:
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LlmError(f"Bentuk response judge tidak dikenali: {exc}", kind="invalid_response") from exc

    usage = data.get("usage", {})
    return LlmResult(
        text=text,
        model_used=data.get("model", model),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        latency_ms=latency_ms,
    )
