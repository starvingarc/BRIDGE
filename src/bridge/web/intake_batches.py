"""Private, upload-bound confirmation of observation-column culture semantics."""
from __future__ import annotations
import hashlib
import io
import json
import re
from fastapi import HTTPException
from .inputs import checked_bytes
from .intake_sources import column, clean_text

FIELDS = {"culture_batch_column", "culture_batch_role"}
CANDIDATE = re.compile(r"batch|replicate|sample|capture|culture.?id|library.?id", re.I)


def profiles(service, state, aid, selected=None):
    import h5py
    upload = state["_uploads"][aid]
    data = checked_bytes(service, state, service.directory(state["id"]) / "uploads" / (aid + ".h5ad"),
                         upload["sha256"], limit=service.settings.upload_limit)
    result = []
    with h5py.File(io.BytesIO(data), "r") as handle:
        obs = handle["obs"]
        index = obs.attrs.get("_index", "_index")
        if isinstance(index, bytes):
            index = index.decode()
        n_rows = obs[index].shape[0]
        keys = [k for k in obs if k != index and len(k) <= 160]
        if selected is not None:
            if selected not in keys:
                raise ValueError("metadata_column_not_registered")
            keys = [selected]
        else:
            keys = [k for k in keys if CANDIDATE.search(k)]
            priority = {"culture_batch": 0, "batch": 1, "replicate": 2, "sample_id": 3, "capture_id": 4}
            keys = sorted(keys, key=lambda k: (priority.get(k, 5), k))[:16]
        for key in keys:
            values, complete = column(obs, key)
            missing = sum(v is None or isinstance(v, str) and not v.strip() for v in values)
            unique = dict.fromkeys(json.dumps(v, ensure_ascii=False) for v in values
                                   if v is not None and not (isinstance(v, str) and not v.strip()))
            result.append({"column": key, "n_observations": n_rows, "complete": complete and len(values) == n_rows,
                           "missing": missing, "distinct": len(unique),
                           "examples": [clean_text(json.loads(v))[:80] for v in list(unique)[:3]],
                           "fingerprint": hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()})
    return result


def candidate(record, facts):
    selected = facts.culture_batch_column
    if selected:
        return next((p for p in record["batch_columns"] if p["column"] == selected), None)
    return record["batch_columns"][0] if record["batch_columns"] else None


def count(profile):
    return (profile["distinct"] if profile["complete"] and not profile["missing"]
            and 1 <= profile["distinct"] <= 100000 else None)


def question(record, facts):
    if facts.culture_batch_role in {"independent_culture", "unsure"}:
        return None
    if FIELDS & record["other_answers"].keys():
        return None
    # Explicit legacy numeric declarations remain readable, but are not mappings.
    if facts.independent_cultures is not None and facts.culture_batch_role == "unknown":
        return None
    current = candidate(record, facts)
    if current and facts.culture_batch_role != "not_culture":
        examples = "、".join(current["examples"]) or "未读到有效取值"
        suffix = "…" if current["distinct"] > len(current["examples"]) else ""
        return {"field": "culture_batch_role", "input_type": "text",
                "title": f"数据中的 {current['column']}（取值：{examples}{suffix}）是否表示独立培养批次？",
                "help": f"这列已读到 {current['distinct']} 个不同值。只有每个值对应一次独立培养时才能据此计数；样本或测序标签不能直接当作培养批次。",
                "options": [{"value": "independent_culture", "label": "是，每个值对应一次独立培养"},
                            {"value": "not_culture", "label": "不是，只是样本或测序标识"},
                            {"value": "unsure", "label": "不确定"},
                            {"value": "__other__", "label": "其他（自定义输入）"}]}
    seen = {current["fingerprint"]} if current else set()
    options = []
    for profile in record["batch_columns"]:
        if profile["fingerprint"] not in seen:
            options.append({"value": profile["column"], "label": profile["column"]})
            seen.add(profile["fingerprint"])
    return {"field": "culture_batch_column", "input_type": "text",
            "title": "哪一列对应独立培养批次？也可以补充样本与培养批次的对应关系。",
            "help": "选择列后还会核对其含义；补充的文字不会自动换算成独立培养次数。",
            "options": options + [{"value": "__other__", "label": "其他列或补充对应关系"}]}


def answer(service, state, body, record):
    from .intake import IntakeFacts, IntakeInput
    facts = service.intake.current_facts(state, body.upload_id)
    values = facts.model_dump()
    profile = candidate(record, facts)
    other_text = None
    value = body.value.strip() if isinstance(body.value, str) else ""
    if not value or len(value) > 240:
        raise HTTPException(422, "invalid_intake_answer")
    if body.field == "culture_batch_column":
        try:
            profile = profiles(service, state, body.upload_id, value)[0]
        except ValueError as exc:
            if not body.other or str(exc) != "metadata_column_not_registered":
                raise HTTPException(422, "invalid_intake_answer") from None
            profile, other_text = None, value
        values.update(culture_batch_column=profile["column"] if profile else None,
                      culture_batch_role="unknown", independent_cultures=None)
    else:
        if profile is None or not body.other and value not in {"independent_culture", "not_culture", "unsure"}:
            raise HTTPException(422, "invalid_intake_answer")
        role = "unknown" if body.other else value
        other_text = value if body.other else None
        values.update(culture_batch_column=profile["column"], culture_batch_role=role,
                      independent_cultures=count(profile) if role == "independent_culture" else None)
    facts = IntakeFacts.model_validate(values)
    service.intake.validate(state, IntakeInput(upload_id=body.upload_id, facts=facts))
    if profile and not any(p["column"] == profile["column"] for p in record["batch_columns"]):
        record["batch_columns"].append(profile)
    for field in FIELDS:
        record["other_answers"].pop(field, None)
    if other_text:
        record["other_answers"][body.field] = other_text
    record["batch_binding"] = ({**profile, "role": facts.culture_batch_role,
                                "upload_sha256": record["upload_sha256"]} if profile else None)
    for field in (*sorted(FIELDS), "independent_cultures"):
        record["values"][field] = getattr(facts, field)
        record["field_sources"][field] = {"kind": "user", "source_ids": [],
            "quote": f"obs.{profile['column']}: {other_text or facts.culture_batch_role}" if profile else other_text}
        if field not in record["manual_fields"]:
            record["manual_fields"].append(field)
    record["revision"] += 1
