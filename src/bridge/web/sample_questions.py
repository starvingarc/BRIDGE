"""Sample-bound question cards; explicit answers resume only declared basic tools."""
from copy import deepcopy
from typing import Annotated

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from .clarification import ENUM_OPTIONS, OBSERVED_FIELDS, QuestionSet, digest
from .research_object_models import MappingInput, MappingStart
from .sample_workflow import INPUT_FIELDS
from .sessions import uid

FIELDS = {name: name for name in MappingInput.model_fields if name != "matrix_semantics"}
FIELDS["count_semantics"] = "matrix_semantics"
QUESTIONS = {
    "matrix_location": "原始计数存在哪个矩阵？",
    "count_semantics": "该矩阵是否为原始计数？",
    "sample_context": "样本在移植前还是移植后采集？",
    "source_family_id": "这份数据的来源标识是什么？",
    "capture_id": "这份数据对应哪个真实捕获批次？",
    "capture_id_column": "哪一列记录真实捕获批次？",
    "gene_symbol_column": "哪一列记录基因符号？",
}


class SampleQuestions:
    def __init__(self, objects, observed, message):
        self.objects, self.observed, self.message = objects, observed, message

    def current(self, state, card):
        try:
            sample = self.objects.sample(state["owner_id"], state["research_id"], card["sample_id"])
        except HTTPException:
            return False
        upload = state["_uploads"].get(card["upload_id"])
        return bool(upload and upload["sha256"] == card["_binding"]["sha256"]
                    and sample["revision"] == card["_binding"]["revision"]
                    and sample["material_id"] == card["_binding"]["material_id"]
                    and state.get("run_id") in {None, sample["run_id"]})

    def stage(self, state, body, focus, *, force=False):
        owner, rid, oid = state["owner_id"], state["research_id"], focus["sample_id"]
        sample = self.objects.sample(owner, rid, oid)
        aid = body.upload_id
        upload = state["_uploads"].get(aid)
        public_upload = next((u for u in state["uploads"] if u["id"] == aid), {})
        if (not upload or public_upload.get("material_id") != sample["material_id"]
                or state.get("run_id") not in {None, sample["run_id"]}):
            raise HTTPException(409, "clarification_sample_mismatch")
        allowed = {field for issue in (sample.get("workflow") or {}).get("issues", []) for field in issue["fields"]}
        fields = [q.field for q in body.questions]
        if any(FIELDS.get(field) not in allowed for field in fields):
            raise HTTPException(422, "clarification_sample_field_not_needed")
        cards = state.setdefault("_clarifications", [])
        if not force:
            for card in reversed(cards):
                if (card.get("sample_id") == oid and self.current(state, card)
                        and [q["field"] for q in card["questions"]] == fields
                        and card["status"] in {"pending", "answered", "cancelled"}):
                    return card
        if len(cards) >= 24:
            raise HTTPException(409, "clarification_count_limit")
        values, questions = {}, body.model_dump(mode="json")["questions"]
        for q in questions:
            field = q["field"]
            if field in OBSERVED_FIELDS:
                names = self.observed(state, aid)[OBSERVED_FIELDS[field]]
                q["options"] = [{"id": "choice_" + str(i), "label": name, "description": ""}
                                for i, name in enumerate(names[:4])]
                values[field] = {o["id"]: o["label"] for o in q["options"]}
            elif field in ENUM_OPTIONS:
                values[field] = {o["id"]: o["id"] for o in q["options"]}
            else:
                # Source/capture identity is a user's declaration, never a model suggestion.
                q["options"], values[field] = [], {}
        card = {"id": uid(), "upload_id": aid, "sample_id": oid, "status": "pending",
                "questions": questions, "answers": [], "input_revision": state["_input_revision"]}
        card["digest"] = digest([state["id"], card, upload["sha256"], sample["revision"]])
        self.message(state, "assistant", "请核对当前样本的信息；补齐后会继续基础分析。选择未知会保留缺口，复杂分析另行确认。", source="server_template")
        card.update(message_id=state["messages"][-1]["id"], _proposal=body.model_dump(mode="json"), _values=values,
                    _binding={"sha256": upload["sha256"], "revision": sample["revision"], "material_id": sample["material_id"]})
        cards.append(card)
        return card

    def answer(self, state, card, body):
        owner, rid, oid = state["owner_id"], state["research_id"], card["sample_id"]
        values = self.objects.sample_answers(owner, rid, oid)
        questions = {q["field"]: q for q in card["questions"]}
        summaries, unknown = [], False
        for item in body.answers:
            options = card["_values"][item.field]
            if (len(item.selected) > 1 or len(set(item.selected)) != len(item.selected)
                    or not set(item.selected) <= set(options) or item.unknown and item.selected
                    or not item.unknown and not item.selected and not item.text.strip()):
                raise HTTPException(422, "invalid_clarification_answer")
            field = FIELDS[item.field]
            value = None if item.unknown else options[item.selected[0]] if item.selected else item.text.strip()
            if field == "matrix_semantics" and value == "not_raw_counts":
                value, unknown = None, True
            if value is not None:
                definition = MappingInput.model_fields[field]
                try:
                    annotation = Annotated[definition.annotation, *definition.metadata] if definition.metadata else definition.annotation
                    value = TypeAdapter(annotation).validate_python(value)
                    if item.field in OBSERVED_FIELDS and value not in self.observed(state, card["upload_id"])[OBSERVED_FIELDS[item.field]]:
                        raise ValueError("metadata_not_observed")
                except (ValidationError, ValueError):
                    raise HTTPException(422, "invalid_sample_declaration") from None
            unknown |= item.unknown
            values[field] = value
            if field in {"capture_id", "capture_id_column"} and value is not None:
                values["capture_id_column" if field == "capture_id" else "capture_id"] = None
            summaries.append(questions[item.field]["title"] + "：" + ("未知" if item.unknown else "非原始计数" if field == "matrix_semantics" and value is None else str(value)))
        missing = [f for f in INPUT_FIELDS if values.get(f) is None]
        complete = not missing and not unknown
        declaration = None
        if complete:
            try:
                declaration = MappingInput.model_validate(values)
            except ValidationError:
                raise HTTPException(422, "invalid_sample_declaration") from None
        revision = self.objects.save_sample_answers(owner, rid, oid, card["_binding"]["revision"], values)
        encoded = body.model_dump(mode="json")["answers"]
        card.update(status="answered", answers=encoded, _answer_digest=digest(encoded))
        card["_binding"]["revision"] = revision
        self.message(state, "user", "\n".join(summaries), source="user_input")
        card.setdefault("_answer_message_ids", []).append(state["messages"][-1]["id"])
        state["status"], state["error"] = "idle", None
        if complete:
            changed = self.objects.supplement_sample_input(owner, rid, oid,
                MappingStart(expected_version=revision, mapping_input=declaration))
            return {"sample_id": oid, "changed": changed}
        if unknown:
            self.message(state, "assistant", "已保留回答及已有结果；当前声明尚不能启动基础分析，核对后可修改这张问题卡继续。", source="server_template")
            return None
        # Remaining required declarations are mechanical, so do not spend another model call.
        reverse = {value: key for key, value in FIELDS.items()}
        pending = []
        for field in missing[:3]:
            key = reverse[field]
            ids = sorted(ENUM_OPTIONS.get(key, {"placeholder_a", "placeholder_b"}))
            pending.append({"field": key, "title": QUESTIONS[key], "reason": "基础分析仍缺少此项声明。",
                            "options": [{"id": value, "label": value} for value in ids]})
        self.stage(state, QuestionSet(upload_id=card["upload_id"], questions=pending), card)
        return None
