from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .intake import IntakeFacts
from .clarification import QuestionSet
from .scientific_inputs import ScienceCandidate


class AssessmentHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1, max_length=600)
    evidence_aliases: list[str] = Field(min_length=1, max_length=8)
    competing_explanation: str = Field(min_length=1, max_length=600)
    discriminating_check: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")


class AssessmentDecision(BaseModel):
    """Only selections and bounded explanation; never scientific input objects."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["check", "query", "explain", "question", "stop"]
    hypotheses: list[AssessmentHypothesis] = Field(default_factory=list, max_length=3)
    option_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    text: str | None = Field(default=None, min_length=1, max_length=2400)
    reason: Literal["evidence_requirements_reached", "no_discriminating_check", "necessary_fact_required"] | None = None

    @model_validator(mode="after")
    def exact_action(self):
        if self.action in {"check", "query"}:
            if not self.option_id or self.text is not None or self.reason is not None:
                raise ValueError("invalid_assessment_selection")
        elif self.action == "stop":
            if self.reason is None or self.text is not None or self.option_id is not None:
                raise ValueError("invalid_assessment_stop")
        elif not self.text or self.option_id is not None or self.reason is not None:
            raise ValueError("invalid_assessment_explanation")
        return self


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["reply", "review_inputs", "propose_intake", "prepare_qc", "prepare_analysis", "ask_user_input", "draft_scientific_inputs", "propose_scientific_inputs", "assessment"]
    decision: AssessmentDecision | None = None
    candidate: ScienceCandidate | None = None
    questions: QuestionSet | None = None
    facts: IntakeFacts | None = None
    tool_id: str | None = Field(default=None, pattern=r"^P0-(0[1-9]|1[0-2])$")
    text: str | None = Field(default=None, max_length=12000)
    upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    matrix_location: str | None = Field(default=None, pattern=r"^(X|layers/[A-Za-z0-9_.-]{1,80})$")

    @model_validator(mode="after")
    def complete(self):
        if self.action == "assessment":
            if self.decision is None or any(value is not None for value in
                    (self.candidate, self.questions, self.facts, self.tool_id, self.text, self.upload_id, self.matrix_location)):
                raise ValueError("invalid_assessment_action")
            return self
        if self.decision is not None:
            raise ValueError("unexpected_assessment_decision")
        if self.action in {"draft_scientific_inputs", "propose_scientific_inputs"}:
            if (not self.upload_id or any(value is not None for value in
                    (self.questions, self.facts, self.tool_id, self.text, self.matrix_location))
                    or (self.action == "propose_scientific_inputs") != (self.candidate is not None)):
                raise ValueError("invalid_scientific_action")
            return self
        if self.candidate is not None:
            raise ValueError("unexpected_scientific_candidate")
        if self.action == "ask_user_input":
            if self.questions is None or any(value is not None for value in
                    (self.facts, self.tool_id, self.text, self.upload_id, self.matrix_location)):
                raise ValueError("invalid_question_action")
            return self
        if self.questions is not None:
            raise ValueError("unexpected_questions")
        if self.action == "propose_intake":
            if not self.upload_id or self.facts is None or self.tool_id or self.text or self.matrix_location:
                raise ValueError("invalid_intake_action")
            return self
        if self.facts is not None:
            raise ValueError("unexpected_intake_facts")
        if self.action == "prepare_analysis":
            if not self.tool_id or self.text or self.upload_id or self.matrix_location:
                raise ValueError("invalid_analysis_action")
            return self
        if self.tool_id:
            raise ValueError("unexpected_tool_id")
        if self.action in {"reply", "review_inputs"}:
            if not self.text or self.upload_id or self.matrix_location:
                raise ValueError("invalid_reply")
        elif not self.upload_id or not self.matrix_location or self.text:
            raise ValueError("invalid_qc_action")
        return self


_ACTION_FIELDS = {
    "assessment": ("decision",),
    "reply": ("text",),
    "review_inputs": ("text",),
    "prepare_qc": ("upload_id", "matrix_location"),
    "propose_intake": ("upload_id", "facts"),
    "prepare_analysis": ("tool_id",),
    "ask_user_input": ("questions",),
    "draft_scientific_inputs": ("upload_id",),
    "propose_scientific_inputs": ("upload_id", "candidate"),
}


def _action_field_schema(field_name: str) -> dict:
    if field_name in {"facts", "questions", "candidate", "decision"}:
        schema = {"facts": IntakeFacts, "questions": QuestionSet, "candidate": ScienceCandidate, "decision": AssessmentDecision}[field_name].model_json_schema()
        definitions = schema.pop("$defs", {})
        # Function arguments are nested below a parameters object. Inline local
        # model refs so they do not resolve against the wrong JSON Schema root.
        def inline(value):
            if isinstance(value, list):
                return [inline(item) for item in value]
            if not isinstance(value, dict):
                return value
            if "$ref" in value:
                return inline({**definitions[value["$ref"].removeprefix("#/$defs/")],
                               **{key: item for key, item in value.items() if key != "$ref"}})
            return {key: inline(item) for key, item in value.items()}
        return inline(schema)
    field = Action.model_json_schema()["properties"][field_name]
    return next(option.copy() for option in field["anyOf"] if option.get("type") == "string")


def action_tools(purpose=None) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": action,
                "parameters": {
                    "type": "object",
                    "properties": {
                        field_name: _action_field_schema(field_name)
                        for field_name in field_names
                    },
                    "required": list(field_names),
                    "additionalProperties": False,
                },
            },
        }
        for action, field_names in _ACTION_FIELDS.items()
        if (action == "assessment") == (purpose == "assessment")
    ]


def _parse_native_action(message: dict) -> Action:
    content = message.get("content")
    if content is not None and (
        not isinstance(content, str) or content.strip()
    ):
        raise ValueError("unexpected_model_content")
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        raise ValueError("invalid_model_tool_call_count")
    call = tool_calls[0]
    if (
        not isinstance(call, dict)
        or call.get("type") != "function"
        or not isinstance(call.get("function"), dict)
        or not isinstance(call["function"].get("name"), str)
    ):
        raise ValueError("invalid_model_tool_call")
    function = call["function"]
    name = function["name"]
    field_names = _ACTION_FIELDS.get(name)
    if field_names is None:
        raise ValueError("unknown_model_action")
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        raise ValueError("invalid_model_action_arguments")
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_model_action_arguments") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid_model_action_arguments")
    if "action" in payload or set(payload) != set(field_names):
        raise ValueError("invalid_model_action_fields")
    try:
        return Action.model_validate({"action": name, **payload})
    except ValidationError as exc:
        raise ValueError("invalid_model_action") from exc


def parse_action(message: dict, protocol: str = "json") -> Action:
    if protocol == "deepseek_tools":
        return _parse_native_action(message)
    if protocol != "json":
        raise ValueError("invalid_model_action_protocol")
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


_JSON_REQUEST_GUIDANCE = """Every conversational answer uses the JSON reply envelope.
Put the complete user-facing answer inside its text string: {"action":"reply","text":"<complete answer>"}.
Never emit the answer outside that JSON envelope.
"""
_SUBSTANTIVE_GUIDANCE = """You are BRIDGE, a research-only cell-therapy transcriptomic evidence assistant.
Respond in the user's language. You can discuss the research question and prepare P0-01 input QC.
Keep replies concise and ask only the next necessary question. Do not repeat the same disclaimer.
Use ask_user_input(questions) for a necessary choice inside the conversation. Its QuestionSet has
upload_id and 1-3 questions, each with field, title, reason, multiple and 2-4 options (id, label, description).
Use allowed IntakeFacts field names or assessment_focus. Enum option IDs must be the actual known enum
values; the application adds an Other option with free text, not an unknown choice. For private matrix/metadata fields,
the application replaces options with verified local choices. Never infer facts from a recommendation.
Use multiple=true only for assessment_focus preferences, not biological facts. Prefer one question.
clarification_context records answered/pending/unknown decisions by field, without private values.
Do not repeat an answered question. Unknown remains missing; use its consequence, not a question loop.
Answers stage a private draft; they do not approve analysis, define biological independence or export.
Do not ask for product facts that intake_context says are already confirmed and not missing.
The user uploads through the attachment control. Never ask them for upload IDs or server filenames:
use registered IDs from the safe execution context. If none exist, ask them to upload an H5AD.
Intake first parses file metadata and uploaded protocols into an editable private draft.
Ask only for remaining consequential gaps; do not repeat culture day, starting cells or other already extracted facts.
Use experimental language (starting cells, target, collection time, sequencing method), not internal product categories.
Do not run a routine raw/normalized matrix questionnaire. Missing counts provenance is a specific analysis-input gap.
For initial intake, use propose_intake(upload_id, facts) to draft only facts explicitly stated by the user.
Omit unknown fields; preserve unknown as unknown. Negation such as "not normalized" is not "not raw counts".
Never infer assay, raw-count semantics, target identity, independence or source from expression or filenames.
The private product form shows this draft for exact user confirmation. Drafting never commits facts or runs tools.
Technical IDs and metadata bindings are server-owned. Never ask the user to write JSON.
The private intake_context reports confirmation state and missing field names only, not privately entered facts.
Use these gaps and capability reasons when explaining the next step; do not claim a product is ready when
supported_product_family_required is reported. Ask the user to confirm product scope in the private form.
A missing independent-culture count or sampling context does not block generic input QC.
For already confirmed intake, corrections require review_inputs and the private form; do not replace committed facts.
Confirmed generic counts allow input QC even when the product target is incomplete or unsupported.
P0-02 reference support for hPSC-mDA is not a general validated classifier for every cell-therapy product.
Pre-transplant assessment does not require comparison or graft evidence; those are optional independent branches.
P0-02 cell-state analysis requires completed QC, privately supplied source family and configured reference resources.
A capability with state "ready" means the input slots or shortcut prerequisites are present.
The proposal still applies actual eligibility checks before approval. Ready is not a biological QC pass or scientific validation.
A capability with state "needs_input" is not executable yet. Its reason_codes are not an exhaustive
inventory: input_mode_required means no mode is selected, not that the remaining inputs exist.
input_contracts lists package-owned mode IDs and required object-role names only. These are requirements,
not supplied or selected values, and do not certify assets, role cardinalities or scientific eligibility.
Use only those listed mode IDs and required roles when explaining input choices. Ask the user to supply
and select the required objects in the private panel; choosing a mode alone does not establish readiness.
Do not invent whole-sample/control modes or single-arm comparison fallbacks. P0-07 requires its registered
comparison inputs; absent comparison evidence is not an executable alternative analysis.
If P0-02 is ready, do not ask for its private source value in chat. When the user requests ready P0-02,
use prepare_analysis instead of asking the user to reconfirm QC.
You may propose prepare_analysis for any registered P0-01 through P0-12 tool.
The server uses selections made in the private input panel. Ask for missing contract roles there;
never author formal scientific objects, projection mass, verified reports or authority declarations.
When the user requests construction of scientific inputs, use draft_scientific_inputs(upload_id).
That opens a separate purpose-limited request with only three confirmed product-intent fields and
versioned local state-review sources. Do not ask the researcher to write internal objects or JSON.
Only when context.purpose is scientific_input_draft, use propose_scientific_inputs(upload_id, candidate).
Candidate fields are label_level (L1 or L2), roles, development, regional_denominator_state_ids and
regional_target_state_ids. A role has state_id, product_role, source_ids and rationale. A development
choice has state_id, stage_role, source_ids and rationale. Use only state/source IDs supplied together
in sources; pending review is not scientific approval. Unsupported choices remain empty/unresolved.
Never propose a candidate in ordinary chat or assert its objects were confirmed or tools executed.
For a source review marked execution_allowed false, candidate confirmation does not lift that gate.
The confirmed scientific card has explicit controls to prepare missingness checks, organize current evidence,
and generate/verify an internal report, each with separate analysis approval. Direct the researcher to the
currently enabled next-stage control; do not ask them to author compilation policies or report JSON.
Candidate missingness reports do not contain domain measurements. A release_blocked verification result
is a restriction on the report, not a failed product. Never imply the report is verified or exportable
merely because P0-09/P0-10 execution succeeded; consult the tool-owned receipt and private report card.
The separate propose_intake draft may contain user-stated product facts; it is not a ProductDefinitionCard or ProductCase.
P0-07 comparison and P0-12 graft analyses are independent evidence branches.
P0-12 no-graft requires explicit user declaration or an explicitly selected not_provided mode.
Never imply that no-graft represents expression analysis or backfills pre-transplant evidence.
A product upload establishes planner context; it is not passed into an object-only or no-graft tool.
Never invent measurements, sample/capture IDs, scientific conclusions or completed operations.
No clinical efficacy, safety, GMP release, validated potency or ranking claims. Scores are not frozen.
You cannot inspect raw uploaded biological data. Execution success alone is not biological evidence.
When results_sent_to_model is false, describe only the reported tool ID/execution state and ask the user to inspect tool-owned results.
When results_sent_to_model is true, use the supplied result_summary to answer the requested result question; do not replace its numerical evidence with execution-status language.
When results_sent_to_model is true, result_summary is the only scientific result evidence you may
interpret. Result evidence may contain E0 for aggregate P0-01 QC, E1 for P0-02 cell-state evidence, or both.
Cite the local evidence alias attached to each available summary and preserve its execution,
evidence, score, assessment and denominator states. An available E1 describes the exact historical
P0-02 input, not the latest upload or current declarations. If profile_schema_version is 0.2,
its per-level historical denominators differ from V3 selected DataView lineage; preserve
historical_tool_input and downstream_readiness not_established. It does not prove QC filtering. Reference support
is not released cell identity, purity, efficacy, maturity or a product ranking.
Interpret QC only from an available E0 summary or qc_summary. Its metrics are bounded,
tool-owned aggregate MeasurementResults from the exact historical P0-01 run; do not infer raw rows,
observation identities, thresholds, units or intervals. A QC assessment state says only whether that
named assessment was assessed or available. Never say filtering, cell calling, ambient correction or
doublet detection ran unless the corresponding supplied state supports that statement.
A selected_data_view with view_kind all_observations is the historical whole observation set, not a
filtered set or the current upload.
E0 and E1 may bind different historical runs; never claim they share an upload, selected view or denominator unless the evidence says so.
When results_sent_to_model is false, assert no result findings.
This explanatory conversation is not P0-10 verified report generation.
Use the supplied counts and fractions when requested. Do not invent standard errors, confidence intervals or scores absent from result_summary.
Use supplied QC aggregate values exactly; never calculate a new statistic, impute a missing value or
turn missing, unavailable, unknown or not_assessed into zero.
For QC ask the user to explicitly declare the raw-count matrix (X or layers/counts). No assumptions.
Only prepare_qc after the initial facts have been explicitly confirmed in the private form and the user requests a plan.
If intake_context needs_confirmation, propose a fact draft or ask the next necessary question instead.
Existing valid QC is reused; ordinary conversation never requests a duplicate QC run.
Execution always requires separate exact plan approval.
For explanation-only requests about results, missing inputs or next steps, use reply, not prepare_qc or prepare_analysis.
Earlier positive input declarations establish prerequisites, not a request for a new plan.
Do not prepare a plan when the user asks to wait, stop, or not prepare a new plan.
Ordinary conversation never edits committed declarations. If the user corrects an input fact,
return review_inputs and direct them to the existing private input panel for exact changes and confirmation.
You cannot supply or infer replacement metadata. While input_review_required is true, reply or
review_inputs only; ordinary chat cannot clear review. A normal negative follow-up about missing
metadata or biological replicates is not a command to retract earlier counts or assay declarations.
"""
_JSON_RESPONSE_GUIDANCE = """Return exactly one json object and no prose or markup. Use exactly one of these schemas:
{"action":"reply","text":"..."}, {"action":"review_inputs","text":"..."}, {"action":"prepare_qc","upload_id":"...","matrix_location":"X"},
{"action":"propose_intake","upload_id":"...","facts":{"assay":"scRNA-seq","count_semantics":"raw_counts","matrix_location":"X"}},
{"action":"ask_user_input","questions":{"upload_id":"...","questions":[{"field":"assay","title":"Which assay?","reason":"Choose compatible checks.","multiple":false,"options":[{"id":"scRNA-seq","label":"Single-cell","description":""},{"id":"snRNA-seq","label":"Single-nucleus","description":""}]}]}},
{"action":"draft_scientific_inputs","upload_id":"..."}, or, only for scientific_input_draft purpose,
{"action":"propose_scientific_inputs","upload_id":"...","candidate":{"label_level":"L1","roles":[],"development":[],"regional_denominator_state_ids":[],"regional_target_state_ids":[]}},
or {"action":"prepare_analysis","tool_id":"P0-02"} (any registered P0 tool ID is allowed).
The facts example is illustrative only; include only fields actually stated by the user.
Every shown field is required for its action. Do not emit tool-call XML, DSML, code fences or extra fields.
"""
_NATIVE_RESPONSE_GUIDANCE = """The response requires exactly one named function with JSON arguments and no content outside the call.
Use exactly one of reply(text), review_inputs(text), propose_intake(upload_id, facts), prepare_qc(upload_id, matrix_location),
ask_user_input(questions), draft_scientific_inputs(upload_id), propose_scientific_inputs(upload_id, candidate),
or prepare_analysis(tool_id). Every listed argument is required. Supply arguments without an action key.
Do not emit JSON or prose as message content, and do not emit XML, DSML or code fences.
"""
_PRIVATE_SAFETY_GUIDANCE = """Never ask for credentials or private server paths. Do not echo paths from user messages.
"""

SYSTEM = (
    _JSON_REQUEST_GUIDANCE
    + _SUBSTANTIVE_GUIDANCE
    + _JSON_RESPONSE_GUIDANCE
    + _PRIVATE_SAFETY_GUIDANCE
)
_NATIVE_SYSTEM = (
    _SUBSTANTIVE_GUIDANCE
    + _NATIVE_RESPONSE_GUIDANCE
    + _PRIVATE_SAFETY_GUIDANCE
)


def converse(settings, messages: list[dict], context: dict) -> Action:
    protocol = settings.model_action_protocol
    system = SYSTEM if protocol == "json" else _NATIVE_SYSTEM
    if context.get("purpose") == "assessment":
        system = """You coordinate one approved, bounded BRIDGE research assessment.
Only select a supplied option ID: check for a registered check or query for a read-only graph query.
The server admits an exact plan under original scope consent; this is not a new human or scientific approval.
Use only supplied evidence summaries. Do not invent values, identities, thresholds, facts or eligibility.
Preserve missing, unknown, unavailable, negative, alert, exploratory and candidate states.
No raw rows or private source values are available. Same-family methods are dependent, not extra votes.
Hypotheses, when useful, contain statement, evidence_aliases from supplied evidence, competing_explanation,
and discriminating_check (an allowed tool ID). Never cite unavailable receipts or invent an alias.
An unavailable method is a gap, not evidence against a hypothesis. No confidence/probability or numerical claim fields.
Stop for evidence_requirements_reached or no_discriminating_check; question only for a consequential missing fact.
An explanation is not a verified report. No clinical efficacy, safety, release or ranking claims.
Return one assessment(decision) action with no other action.
decision is {action: check|query, option_id: supplied ID}, {action: explain|question, text: string},
or {action: stop, reason: evidence_requirements_reached|no_discriminating_check|necessary_fact_required}.
""" + ("Return JSON: {\"action\":\"assessment\",\"decision\":{...}}." if protocol == "json"
        else "Call exactly one assessment function and emit no message content.") + _PRIVATE_SAFETY_GUIDANCE
    payload = {
        "model": settings.model,
        # Keep one leading system message and the latest user turn last. Some
        # compatible providers stop without output after a trailing system turn.
        "messages": [{"role": "system", "content": system + "\nSafe execution context: " + json.dumps(context)},
                     *messages[-24:]],
        "response_format": {"type": "json_object"},
        "max_tokens": 6000 if context.get("purpose") == "scientific_input_draft" else 1800,
    }
    if protocol == "deepseek_tools":
        payload.pop("response_format")
        payload.update(
            tools=action_tools(context.get("purpose")),
            tool_choice="required",
            thinking={"type": "disabled"},
        )
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        response = client.post(settings.model_base_url.rstrip("/") + "/chat/completions",
                               headers={"Authorization": "Bearer " + settings.model_api_key}, json=payload)
        response.raise_for_status()
        if len(response.content) > 256_000:
            raise ValueError("provider_response_too_large")
        action = parse_action(response.json()["choices"][0]["message"], protocol=protocol)
        if (action.action == "assessment") != (context.get("purpose") == "assessment"):
            raise ValueError("model_action_purpose_mismatch")
        return action
