"""Klien Google AI Studio (Gemini) — REST langsung lewat httpx, BUKAN SDK
google-generativeai/google-genai. httpx>=0.27 sudah ada di requirements.txt
dan cukup untuk generateContent + responseSchema (JSON mode); menambah SDK
baru hanya menambah permukaan audit dependency tanpa manfaat konkret di sini.

Mendukung rotasi otomatis lintas beberapa API key saat salah satu kena quota
(429/RESOURCE_EXHAUSTED) — dicap ke `max_key_attempts` (BUKAN len(api_keys))
supaya latensi tidak menumpuk kalau user mengonfigurasi banyak key sekaligus.
Index rotasi disimpan in-memory di instance ini — reset saat proses restart,
dapat diterima karena ini alat ketersediaan/biaya, bukan correctness-critical."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

_ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiError(Exception):
    """Kegagalan setelah seluruh retry/rotasi habis. `kind` membedakan
    penyebab supaya caller (ai_reasoning_service.py) bisa memutuskan
    FALLBACK vs FAILED tanpa perlu string-matching pesan error."""

    def __init__(self, message: str, kind: str):
        super().__init__(message)
        self.kind = kind   # 'timeout' | 'quota' | 'http' | 'invalid_response'


@dataclass
class GeminiResult:
    text: str                     # raw JSON text dari responseSchema (belum di-parse)
    model_used: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: int = 0


@dataclass
class GeminiClient:
    api_keys: list[str]
    model: str
    timeout_seconds: float
    max_key_attempts: int
    _key_index: int = field(default=0, init=False, repr=False)

    def _next_key(self) -> str:
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key

    def generate(self, system_instruction: str, payload: dict, response_schema: dict) -> GeminiResult:
        if not self.api_keys:
            raise GeminiError("Tidak ada API key Gemini yang dikonfigurasi", kind="http")

        started = time.monotonic()
        body = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": _to_json_text(payload)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }

        attempts = min(self.max_key_attempts, len(self.api_keys))
        last_error: Optional[GeminiError] = None
        retried_5xx_this_key = False

        with httpx.Client(timeout=self.timeout_seconds) as client:
            attempt = 0
            while attempt < attempts:
                key = self._next_key()
                url = _ENDPOINT_TEMPLATE.format(model=self.model)
                try:
                    response = client.post(url, params={"key": key}, json=body)
                except httpx.TimeoutException:
                    # Kontrak dari ai-reasoning-api-upgrade-tasks.md §7: JANGAN
                    # retry sama sekali pada read timeout — supaya latensi
                    # worst-case tetap terbatas, bukan menumpuk per key.
                    raise GeminiError("Gemini timeout", kind="timeout") from None
                except httpx.ConnectError as exc:
                    if not retried_5xx_this_key:
                        retried_5xx_this_key = True
                        continue   # retry SEKALI di key yang sama (connect error)
                    last_error = GeminiError(f"Gemini connect error: {exc}", kind="http")
                    attempt += 1
                    retried_5xx_this_key = False
                    continue

                if response.status_code == 429:
                    last_error = GeminiError("Gemini quota exceeded (429)", kind="quota")
                    attempt += 1
                    retried_5xx_this_key = False
                    continue   # rotasi ke key berikutnya

                if response.status_code >= 500:
                    if not retried_5xx_this_key:
                        retried_5xx_this_key = True
                        continue   # retry SEKALI di key yang sama
                    last_error = GeminiError(f"Gemini server error ({response.status_code})", kind="http")
                    attempt += 1
                    retried_5xx_this_key = False
                    continue

                if response.status_code != 200:
                    raise GeminiError(
                        f"Gemini HTTP {response.status_code}: {response.text[:300]}", kind="http"
                    )

                data = response.json()
                latency_ms = int((time.monotonic() - started) * 1000)
                return _parse_success(data, self.model, latency_ms)

        raise last_error or GeminiError("Gemini gagal tanpa detail", kind="http")


def _to_json_text(payload: dict) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False, default=str)


def _parse_success(data: dict, model: str, latency_ms: int) -> GeminiResult:
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise GeminiError(f"Bentuk response Gemini tidak dikenali: {exc}", kind="invalid_response") from exc

    usage = data.get("usageMetadata", {})
    return GeminiResult(
        text=text,
        model_used=model,
        prompt_tokens=usage.get("promptTokenCount"),
        completion_tokens=usage.get("candidatesTokenCount"),
        total_tokens=usage.get("totalTokenCount"),
        latency_ms=latency_ms,
    )
