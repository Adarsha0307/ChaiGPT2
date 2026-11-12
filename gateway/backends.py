"""LLM backends (M1).

GeminiBackend: real calls. Only ever receives the already-built prompt, which
contains sanitized text. The exact string sent is returned as outbound_payload
so the leakage guard and the audit log can check what really left the box.

MockBackend: offline backend for tests and the eval, with modes that mimic
how real LLMs mangle placeholders: echo, paraphrase, reorder, drop, fake.
"""
from __future__ import annotations

import os
import re
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
            except Exception as e:  # noqa: BLE001 - filtered below
                retryable = getattr(e, "code", None) in RETRYABLE_STATUS or _is_network_error(e)
                if not retryable or attempt == self.max_attempts:
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


_NETWORK_ERRORS = {"ReadError", "WriteError", "ConnectError", "RemoteProtocolError",
                   "ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout"}


def _is_network_error(e: Exception) -> bool:
    """Dropped or timed-out connections (httpx / OS level) are worth a retry."""
    return isinstance(e, (ConnectionError, TimeoutError)) or type(e).__name__ in _NETWORK_ERRORS


_PH = re.compile(r"<([A-Z_]+?)_(\d+)>")
_VARIANTS = ("{t}_{n}", "[{t}_{n}]", "<{tc} {n}>", "{{{t}_{n}}}")


class MockBackend:
    """Offline stand-in for an LLM, with the ways real LLMs mangle placeholders.

    echo        returns the document unchanged
    paraphrase  rewrites placeholders as PERSON_1, [PERSON_1], <Person 1>, {PERSON_1}
    reorder     returns the sentences in reverse order
    drop        removes every occurrence of the last placeholder
    fake        appends a sentence with an invented <PERSON_9>
    """

    name = "mock"
    MODES = ("echo", "paraphrase", "reorder", "drop", "fake")

    def __init__(self, mode: str = "echo"):
        if mode not in self.MODES:
            raise ValueError(f"Unknown mock mode {mode!r}; use one of {self.MODES}")
        self.mode = mode
        self.model = f"mock-{mode}"

    def _respond(self, doc: str) -> str:
        if self.mode == "paraphrase":
            i = iter(range(10**6))

            def vary(m: re.Match) -> str:
                t, n = m.group(1), m.group(2)
                return _VARIANTS[next(i) % len(_VARIANTS)].format(
                    t=t, n=n, tc=t.replace("_", " ").title())

            return "Summary: " + _PH.sub(vary, doc)
        if self.mode == "reorder":
            parts = [p for p in re.split(r"(?<=[.!?\n])\s+", doc.strip()) if p]
            return " ".join(reversed(parts))
        if self.mode == "drop":
            found = _PH.findall(doc)
            if not found:
                return doc
            t, n = found[-1]
            return re.sub(rf"\s*<{t}_{n}>", "", doc)
        if self.mode == "fake":
            return doc + " Please also notify <PERSON_9>."
        return doc

    def generate(self, prompt: str) -> LLMResponse:
        t0 = time.perf_counter()
        text = self._respond(_extract_document(prompt))
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
        body = prompt.split(marker)[1]
        # The template adds exactly one newline on each side; keep the document's own.
        if body.startswith("\n"):
            body = body[1:]
        if body.endswith("\n"):
            body = body[:-1]
        return body
    return prompt


def get_backend(name: str, **kwargs) -> GeminiBackend | MockBackend:
    if name == "gemini":
        return GeminiBackend(**kwargs)
    if name == "mock":
        return MockBackend(**kwargs)
    raise ValueError(f"Unknown backend {name!r}")
