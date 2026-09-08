"""Private conversational questions. Answers stage facts; they grant no authority."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator

from .inputs import InputBody
from .intake import IntakeFacts, IntakeInput

QuestionField = Literal[
    "product_name", "product_family", "target_cell_type", "target_stage",
    "sampling_context", "independent_cultures", "assay", "matrix_location",
    "count_semantics", "source_family_id", "sample_id_column",
    "capture_id_column", "gene_symbol_column", "assessment_focus",
]
ENUM_OPTIONS = {
    "product_family": {"hpsc_mda", "other"},
    "sampling_context": {"pretransplant_preparation", "process_sample"},
    "assay": {"scRNA-seq", "snRNA-seq"},
    "count_semantics": {"raw_counts", "not_raw_counts"},
}
OBSERVED_FIELDS = {
    "matrix_location": "matrix_locations", "sample_id_column": "obs_columns",
    "capture_id_column": "obs_columns", "gene_symbol_column": "var_columns",
}


class Option(InputBody):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    label: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=300)


class Question(InputBody):
    field: QuestionField
    title: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=400)
    multiple: bool = False
    options: list[Option] = Field(min_length=2, max_length=4)

    @model_validator(mode="before")
    @classmethod
    def application_owned_unknown(cls, value):
        if isinstance(value, dict) and isinstance(value.get("options"), list):
            options = value["options"]
            reserved = [row for row in options if isinstance(row, dict) and row.get("id") == "unknown"]
            if len(reserved) == 1:
                # The actual provider may repeat this reserved option. Validate
                # its shape, then let the application render its own unknown UI.
                Option.model_validate(reserved[0])
                return {**value, "options": [row for row in options if row is not reserved[0]]}
        return value

    @model_validator(mode="after")
    def valid(self):
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_question_options")
        if self.multiple and self.field != "assessment_focus":
            raise ValueError("fact_requires_single_answer")
        if self.field in ENUM_OPTIONS and not set(ids) <= ENUM_OPTIONS[self.field]:
            raise ValueError("invalid_fact_options")
        return self


class QuestionSet(InputBody):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    questions: list[Question] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def distinct(self):
        fields = [question.field for question in self.questions]
        if len(fields) != len(set(fields)):
            raise ValueError("duplicate_question_fields")
        return self


class Answer(InputBody):
    field: QuestionField
    selected: list[str] = Field(default_factory=list, max_length=4)
    text: str = Field(default="", max_length=1000)
    unknown: bool = False


class CardIdentity(InputBody):
    card_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    card_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnswerBody(CardIdentity):
    answers: list[Answer] = Field(min_length=1, max_length=3)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Clarifications:
    def __init__(self, service):
        self.service = service

    def initialize(self, state):
        state.setdefault("_clarifications", [])

    def facts(self, state, aid):
        return self.service.intake.current_facts(state, aid).model_dump(mode="json")

    def current(self, state, card):
        upload = state["_uploads"].get(card["upload_id"])
        if not upload or upload["sha256"] != card["_binding"]["sha256"]:
            return False
        facts = self.facts(state, card["upload_id"])
        return all(facts.get(field) in values for field, values in card["_binding"]["facts"].items())

    def public(self, state):
        self.initialize(state)
        result = []
        for card in state["_clarifications"]:
            value = {key: deepcopy(item) for key, item in card.items() if not key.startswith("_")}
            if value["status"] in {"pending", "answered"} and not self.current(state, card):
                value["status"] = "stale"
            result.append(value)
        return result

    def context(self, state):
        return [{"upload_id": card["upload_id"], "state": card["status"],
                 "fields": [question["field"] for question in card["questions"]]}
                for card in self.public(state)[-12:]]

    def private_message_ids(self, state):
        self.initialize(state)
        return {identifier for card in state["_clarifications"]
                for identifier in [card["message_id"], *card.get("_answer_message_ids", [])]}

    def stage(self, state, body, *, force=False):
        from .app import uid
        self.initialize(state)
        aid = body.upload_id
        if aid not in state["_uploads"]:
            raise HTTPException(404, "upload_not_found")
        facts = self.facts(state, aid)
        fields = [question.field for question in body.questions]
        if not force:
            for card in reversed(state["_clarifications"]):
                if (card["upload_id"] == aid and self.current(state, card)
                        and [question["field"] for question in card["questions"]] == fields
                        and card["status"] in {"pending", "answered", "cancelled"}):
                    return card
            record = state.get("_intakes", {}).get(aid)
            if (record and record["signature"] == self.service.intake.signature(state, aid)
                    and all(field != "assessment_focus" and facts[field] not in (None, "unknown") for field in fields)):
                return None
        if len(state["_clarifications"]) >= 24:
            raise HTTPException(409, "clarification_count_limit")
        questions = body.model_dump(mode="json")["questions"]
        values = {}
        observed = None
        for question in questions:
            field = question["field"]
            if field in OBSERVED_FIELDS:
                observed = observed or self.service.intake.observed(state, aid)
                # Column/matrix names come from the verified private file, not the model.
                options = [{"id": "choice_" + str(index), "label": name, "description": ""}
                           for index, name in enumerate(observed[OBSERVED_FIELDS[field]][:4])]
                question["options"] = options
                values[field] = {option["id"]: option["label"] for option in options}
            else:
                values[field] = {option["id"]: (option["id"] if field in ENUM_OPTIONS
                                 or field == "independent_cultures" else option["label"])
                                 for option in question["options"]}
        card = {"id": uid(), "upload_id": aid, "status": "pending", "questions": questions,
                "answers": [], "input_revision": state["_input_revision"]}
        card["digest"] = digest([state["id"], card, state["_uploads"][aid]["sha256"]])
        self.service.message(state, "assistant", "请核对下面的问题；可以选择选项、补充说明或保留未知。提交答案不会启动分析。")
        card["message_id"] = state["messages"][-1]["id"]
        card["_proposal"] = body.model_dump(mode="json")
        card["_values"] = values
        card["_binding"] = {"sha256": state["_uploads"][aid]["sha256"],
                           "facts": {field: [facts[field]] for field in fields if field != "assessment_focus"}}
        state["_clarifications"].append(card)
        return card

    def get(self, state, body):
        self.initialize(state)
        card = next((item for item in state["_clarifications"] if item["id"] == body.card_id), None)
        if card is None or not secrets.compare_digest(card["digest"], body.card_digest):
            raise HTTPException(409, "clarification_mismatch")
        return card

    def answer(self, state, body):
        card = self.get(state, body)
        encoded = body.model_dump(mode="json")["answers"]
        answer_hash = digest(encoded)
        if card["status"] == "answered":
            if card.get("_answer_digest") == answer_hash:
                return
            raise HTTPException(409, "clarification_already_answered")
        if card["status"] != "pending" or not self.current(state, card):
            raise HTTPException(409, "clarification_stale")
        questions = {question["field"]: question for question in card["questions"]}
        fields = [item.field for item in body.answers]
        if len(fields) != len(set(fields)) or set(fields) != set(questions):
            raise HTTPException(422, "clarification_answers_mismatch")
        aid = card["upload_id"]
        before = self.facts(state, aid)
        values = deepcopy(before)
        pending = state.get("pending_input_change")
        if pending:
            if pending["kind"] != "intake" or pending["upload_id"] != aid:
                raise HTTPException(409, "input_review_required")
            values = deepcopy(state["_pending_input_payload"]["facts"])
        notes, summaries, expected, focus = {}, [], {}, None
        for item in body.answers:
            question = questions[item.field]
            options = card["_values"][item.field]
            if (len(item.selected) != len(set(item.selected))
                    or not set(item.selected) <= set(options)
                    or (not question["multiple"] and len(item.selected) > 1)
                    or (item.unknown and item.selected)
                    or (not item.unknown and not item.selected and not item.text.strip())):
                raise HTTPException(422, "invalid_clarification_answer")
            selected_labels = [option["label"] for option in question["options"] if option["id"] in item.selected]
            summaries.append(question["title"] + "：" + ("未知" if item.unknown else "、".join(selected_labels) or item.text.strip()))
            if item.text.strip():
                notes[item.field] = item.text.strip()
            if item.field == "assessment_focus":
                focus = item.model_dump(mode="json")
                continue
            value = IntakeFacts().model_dump()[item.field] if item.unknown else (
                options[item.selected[0]] if item.selected else item.text.strip())
            if item.field == "independent_cultures" and isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,5}", value):
                value = int(value)
            try:
                value = IntakeFacts.model_validate({item.field: value}).model_dump(mode="json")[item.field]
                if item.field in OBSERVED_FIELDS and value is not None:
                    observed = self.service.intake.observed(state, aid)
                    if value not in observed[OBSERVED_FIELDS[item.field]]:
                        raise ValueError("metadata_not_observed")
            except ValueError:
                # A free-text correction may need another scientific decision.
                # Keep its text privately without converting it into a valid fact.
                if item.selected:
                    raise HTTPException(422, "invalid_clarification_fact") from None
                value = values[item.field]
            values[item.field] = value
            expected[item.field] = value
        if values != before:
            self.service.controls.stage(state, "intake", IntakeInput(upload_id=aid, facts=IntakeFacts.model_validate(values)))
        card["status"], card["answers"], card["_answer_digest"] = "answered", encoded, answer_hash
        card["_notes"] = notes
        for field, value in expected.items():
            if value not in card["_binding"]["facts"][field]:
                card["_binding"]["facts"][field].append(value)
        if focus is not None:
            state.setdefault("_assessment_focus", {})[aid] = focus
        self.service.message(state, "user", "\n".join(summaries))
        card.setdefault("_answer_message_ids", []).append(state["messages"][-1]["id"])
        state["status"], state["error"] = "idle", None

    def cancel(self, state, body):
        card = self.get(state, body)
        if card["status"] != "pending" or not self.current(state, card):
            raise HTTPException(409, "clarification_stale")
        card["status"] = "cancelled"

    def revise(self, state, body):
        card = self.get(state, body)
        if state.get("pending_input_change"):
            raise HTTPException(409, "input_review_required")
        proposal = QuestionSet.model_validate(card["_proposal"])
        fresh = self.stage(state, proposal, force=True)
        card["status"] = "superseded"
        return fresh
