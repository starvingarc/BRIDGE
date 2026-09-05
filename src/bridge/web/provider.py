from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["reply", "prepare_qc"]
    text: str | None = Field(default=None, max_length=12000)
    upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    matrix_location: str | None = Field(default=None, pattern=r"^(X|layers/[A-Za-z0-9_.-]{1,80})$")

    @model_validator(mode="after")
    def complete(self):
        if self.action == "reply":
            if not self.text or self.upload_id or self.matrix_location:
                raise ValueError("invalid_reply")
        elif not self.upload_id or not self.matrix_location or self.text:
            raise ValueError("invalid_qc_action")
        return self


def parse_action(message: dict) -> Action:
    calls = message.get("tool_calls")
    if calls:
        if len(calls) != 1:
            raise ValueError("ambiguous_model_action")
        function = calls[0]["function"]
        arguments = json.loads(function["arguments"])
        return Action.model_validate({**arguments, "action": function["name"]})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty_model_response")
    content = content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if content.startswith("{"):
        return Action.model_validate(json.loads(content))
    return Action(action="reply", text=content)


SYSTEM = """You are BRIDGE, a research-only cell-therapy transcriptomic evidence assistant.
Respond in the user's language. You can discuss the research question and prepare P0-01 input QC.
Keep replies concise and ask only the next necessary question. Do not repeat the same disclaimer.
The user uploads through the attachment control. Never ask them for upload IDs or server filenames:
use registered IDs from the safe execution context. If none exist, ask them to upload an H5AD.
Ask for assay and raw-count semantics in ordinary language; technical IDs are server-owned.
Other analyses require additional reviewed scientific inputs; do not claim a full-chain analysis.
Never invent measurements, sample/capture IDs, scientific conclusions or completed operations.
No clinical efficacy, safety, GMP release, validated potency or ranking claims. Scores are not frozen.
You receive conversation and minimal execution status only; you cannot inspect uploaded biological data.
Never infer biological findings from execution success. Ask the user to inspect tool-owned results.
Describe completed execution only at tool level. The context does not certify individual QC metrics,
filtering or doublet detection: never say these operations ran. Describe possibilities conditionally.
For QC ask the user to explicitly declare the raw-count matrix (X or layers/counts). No assumptions.
Only prepare_qc after a user declaration; execution always requires separate exact plan approval.
Use a normal text reply or the prepare_qc tool. If tool calls are unavailable return one JSON object
{"action":"reply","text":"..."} or {"action":"prepare_qc","upload_id":"...","matrix_location":"X"}.
Never ask for credentials or private server paths. Do not echo paths from user messages.
"""


def converse(settings, messages: list[dict], context: dict) -> Action:
    payload = {
        "model": settings.model,
        # Keep one leading system message and the latest user turn last. Some
        # compatible providers stop without output after a trailing system turn.
        "messages": [{"role": "system", "content": SYSTEM + "\nSafe execution context: " + json.dumps(context)},
                     *messages[-24:]],
        "tools": [{"type": "function", "function": {
            "name": "prepare_qc", "description": "Propose QC for a registered upload and explicitly declared raw-count matrix.",
            "parameters": {"type": "object", "additionalProperties": False,
                           "properties": {"upload_id": {"type": "string"}, "matrix_location": {"type": "string"}},
                           "required": ["upload_id", "matrix_location"]}}}],
        "max_tokens": 1800,
    }
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        response = client.post(settings.model_base_url.rstrip("/") + "/chat/completions",
                               headers={"Authorization": "Bearer " + settings.model_api_key}, json=payload)
        response.raise_for_status()
        if len(response.content) > 256_000:
            raise ValueError("provider_response_too_large")
        return parse_action(response.json()["choices"][0]["message"])
