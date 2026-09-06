from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["reply", "prepare_qc", "prepare_analysis"]
    tool_id: str | None = Field(default=None, pattern=r"^P0-(0[1-9]|1[0-2])$")
    text: str | None = Field(default=None, max_length=12000)
    upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    matrix_location: str | None = Field(default=None, pattern=r"^(X|layers/[A-Za-z0-9_.-]{1,80})$")

    @model_validator(mode="after")
    def complete(self):
        if self.action == "prepare_analysis":
            if not self.tool_id or self.text or self.upload_id or self.matrix_location:
                raise ValueError("invalid_analysis_action")
            return self
        if self.tool_id:
            raise ValueError("unexpected_tool_id")
        if self.action == "reply":
            if not self.text or self.upload_id or self.matrix_location:
                raise ValueError("invalid_reply")
        elif not self.upload_id or not self.matrix_location or self.text:
            raise ValueError("invalid_qc_action")
        return self


def parse_action(message: dict) -> Action:
    if message.get("tool_calls"):
        raise ValueError("unexpected_model_tool_call")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty_model_response")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_model_action_json") from exc
    return Action.model_validate(payload)


SYSTEM = """You are BRIDGE, a research-only cell-therapy transcriptomic evidence assistant.
Respond in the user's language. You can discuss the research question and prepare P0-01 input QC.
Keep replies concise and ask only the next necessary question. Do not repeat the same disclaimer.
The user uploads through the attachment control. Never ask them for upload IDs or server filenames:
use registered IDs from the safe execution context. If none exist, ask them to upload an H5AD.
Ask for assay and raw-count semantics in ordinary language; technical IDs are server-owned.
P0-02 cell-state analysis requires completed QC, privately supplied source family and configured reference resources.
A capability with state "ready" means the input slots or shortcut prerequisites are present.
The proposal still applies actual eligibility checks before approval. Ready is not a biological QC pass or scientific validation.
If P0-02 is ready, do not ask for its private source value in chat. When the user requests ready P0-02,
use prepare_analysis instead of asking the user to reconfirm QC.
You may propose prepare_analysis for any registered P0-01 through P0-12 tool.
The server uses selections made in the private input panel. Ask for missing contract roles there;
never author scientific objects, projection mass, reports, source facts or authority declarations.
P0-07 comparison and P0-12 graft analyses are independent evidence branches.
P0-12 no-graft requires explicit user declaration or an explicitly selected not_provided mode.
Never imply that no-graft represents expression analysis or backfills pre-transplant evidence.
A product upload establishes planner context; it is not passed into an object-only or no-graft tool.
Never invent measurements, sample/capture IDs, scientific conclusions or completed operations.
No clinical efficacy, safety, GMP release, validated potency or ranking claims. Scores are not frozen.
You receive conversation and minimal execution status only; you cannot inspect uploaded biological data.
Never infer biological findings from execution success. Ask the user to inspect tool-owned results.
Describe completed execution history only at the reported tool ID and execution-state level.
The context does not certify individual QC metrics,
filtering or doublet detection: never say these operations ran. Describe possibilities conditionally.
For QC ask the user to explicitly declare the raw-count matrix (X or layers/counts). No assumptions.
Only prepare_qc after a user declaration; execution always requires separate exact plan approval.
Return exactly one json object and no prose or markup. Use exactly one of these schemas:
{"action":"reply","text":"..."}, {"action":"prepare_qc","upload_id":"...","matrix_location":"X"},
or {"action":"prepare_analysis","tool_id":"P0-02"} (any registered P0 tool ID is allowed).
Every shown field is required for its action. Do not emit tool-call XML, DSML, code fences or extra fields.
Never ask for credentials or private server paths. Do not echo paths from user messages.
"""


def converse(settings, messages: list[dict], context: dict) -> Action:
    payload = {
        "model": settings.model,
        # Keep one leading system message and the latest user turn last. Some
        # compatible providers stop without output after a trailing system turn.
        "messages": [{"role": "system", "content": SYSTEM + "\nSafe execution context: " + json.dumps(context)},
                     *messages[-24:]],
        "response_format": {"type": "json_object"},
        "max_tokens": 1800,
    }
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        response = client.post(settings.model_base_url.rstrip("/") + "/chat/completions",
                               headers={"Authorization": "Bearer " + settings.model_api_key}, json=payload)
        response.raise_for_status()
        if len(response.content) > 256_000:
            raise ValueError("provider_response_too_large")
        return parse_action(response.json()["choices"][0]["message"])
