"""Prompt template sent to the LLM (only ever with SANITIZED text)."""
from __future__ import annotations

DEFAULT_TASK = "Summarize this document in 3-4 sentences."

TEMPLATE = """{task}

The document contains placeholders such as <PERSON_1> or <PAN_1> that stand for
private values. Keep every placeholder exactly as written, including the angle
brackets, the type and the number. Do not invent new placeholders.

Document:
\"\"\"
{text}
\"\"\""""


def build_prompt(sanitized_text: str, task: str = DEFAULT_TASK) -> str:
    return TEMPLATE.format(task=task, text=sanitized_text)
