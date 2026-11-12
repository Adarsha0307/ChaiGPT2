"""LLM backends (M1).

GeminiBackend: real calls. Only ever receives the already-built prompt, which
contains sanitized text. The exact string sent is returned as outbound_payload
so the leakage guard and the audit log can check what really left the box.

MockBackend: offline backend for tests and the eval. STUB: "echo" only for now.
Phase 3 adds: paraphrase, reorder, drop, fake (<PERSON_9>).
"""
from __future__ import annotations

import os
import time

from .contracts import LLMResponse


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from the project's .env (gitignored) into os.environ.

    Real environment variables win over the file. Values are never printed.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")


RETRYABLE_STATUS = {429, 500, 502, 503, 504}  # rate limit / overloaded / transient


class GeminiBackend:
    name = "gemini"

    def __init__(
        self,
        model: str = DEFAULT_GEMINI_MODEL,
        api_key: str | None = None,
        max_attempts: int = 4,
        base_delay: float = 2.0,
    ):
        from google import genai  # imported lazily so Mock-only runs need no SDK

        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY to use the Gemini backend.")
        self.model = model
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self._sleep = time.sleep  # swapped out in tests
        self._client = genai.Client(api_key=key)

    def _call_with_retry(self, prompt: str):
        """generate_content, retrying 429/5xx with exponential backoff (2s, 4s, 8s).

        Other errors (bad key, unknown model, bad request) are raised at once.
        The same sanitized prompt is resent; nothing new leaves the box.
        """
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._client.models.generate_content(model=self.model, contents=prompt)
            except Exception as e:  # noqa: BLE001 - filtered by status code below
                code = getattr(e, "code", None)
                if code not in RETRYABLE_STATUS or attempt == self.max_attempts:
                    raise
                self._sleep(self.base_delay * 2 ** (attempt - 1))

    def generate(self, prompt: str) -> LLMResponse:
        t0 = time.perf_counter()
        resp = self._call_with_retry(prompt)
        latency = (time.perf_counter() - t0) * 1000  # includes any retry waits
        return LLMResponse(
            text=resp.text or "",
            outbound_payload=prompt,
            model=self.model,
            latency_ms=latency,
        )


class MockBackend:
    name = "mock"
    MODES = ("echo",)  # phase 3: + paraphrase, reorder, drop, fake

    def __init__(self, mode: str = "echo"):
        if mode not in self.MODES:
            raise NotImplementedError(f"Mock mode {mode!r} arrives in phase 3")
        self.mode = mode
        self.model = f"mock-{mode}"

    def generate(self, prompt: str) -> LLMResponse:
        t0 = time.perf_counter()
        text = _extract_document(prompt)
        return LLMResponse(
            text=text,
            outbound_payload=prompt,
            model=self.model,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


def _extract_document(prompt: str) -> str:
    """Pull the document body back out of the prompt template."""
    marker = '"""'
    if prompt.count(marker) >= 2:
        return prompt.split(marker)[1].strip("\n")
    return prompt


def get_backend(name: str, **kwargs) -> GeminiBackend | MockBackend:
    if name == "gemini":
        return GeminiBackend(**kwargs)
    if name == "mock":
        return MockBackend(**kwargs)
    raise ValueError(f"Unknown backend {name!r}")
