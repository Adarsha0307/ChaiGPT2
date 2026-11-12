"""GeminiBackend retries 429/5xx and gives up on other errors. No network."""
from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError, ServerError

from gateway.backends import GeminiBackend


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append(contents)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(text=out)


def make_backend(outcomes, max_attempts=4):
    b = GeminiBackend.__new__(GeminiBackend)  # skip __init__: no key, no SDK client
    b.model, b.max_attempts, b.base_delay = "fake-model", max_attempts, 2.0
    b.sleeps = []
    b._sleep = b.sleeps.append
    b._client = SimpleNamespace(models=FakeModels(outcomes))
    return b


def overloaded():
    return ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})


def test_retries_503_then_succeeds():
    b = make_backend([overloaded(), overloaded(), "pong"])
    r = b.generate("<PERSON_1> prompt")
    assert r.text == "pong"
    assert b.sleeps == [2.0, 4.0]
    # the same sanitized prompt is resent on every attempt
    assert b._client.models.calls == ["<PERSON_1> prompt"] * 3
    assert r.outbound_payload == "<PERSON_1> prompt"


def test_retries_429_rate_limit():
    b = make_backend([ClientError(429, {"error": {"code": 429}}), "ok"])
    assert b.generate("p").text == "ok"
    assert b.sleeps == [2.0]


def test_gives_up_after_max_attempts():
    b = make_backend([overloaded()] * 4)
    with pytest.raises(ServerError):
        b.generate("p")
    assert b.sleeps == [2.0, 4.0, 8.0]
    assert len(b._client.models.calls) == 4


def test_does_not_retry_non_retryable_errors():
    b = make_backend([ClientError(404, {"error": {"code": 404}})])
    with pytest.raises(ClientError):
        b.generate("p")
    assert b.sleeps == []
