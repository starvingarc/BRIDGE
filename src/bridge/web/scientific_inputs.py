"""Private source-backed candidates; deterministic objects, never measurements."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.resources import files
import json
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
import yaml

from bridge.tool_packages._configurable_contracts import (
    ProductCase, ProductDefinitionCard, StateRoleMap, DevelopmentWindowSpec,
)
from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
from bridge.tool_packages.p0_02_cell_state.reference import load_packaged_vocabulary
from bridge.tool_packages.p0_03_target_regional.models import TargetRegionalAssessmentSpec
from bridge.tool_packages.p0_04_developmental_compatibility.models import DevelopmentStateMap
from .inputs import InputBody, Selection, checked_bytes


class SupportedChoice(InputBody):
    state_id: str = Field(max_length=100)
    source_ids: list[str] = Field(min_length=1, max_length=1)
    rationale: str = Field(min_length=1, max_length=600)


class RoleChoice(SupportedChoice):
    product_role: Literal["target", "acceptable_adjacent", "known_off_target", "role_unresolved"]


class DevelopmentChoice(SupportedChoice):
    stage_role: Literal["earlier", "within_window", "later", "branch_shift", "unresolved"]


class ScienceCandidate(InputBody):
    label_level: Literal["L1", "L2"]
    roles: list[RoleChoice] = Field(max_length=32)
    development: list[DevelopmentChoice] = Field(max_length=32)
    regional_denominator_state_ids: list[str] = Field(max_length=32)
    regional_target_state_ids: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def unique_choices(self):
        state_ids = [row.state_id for row in [*self.roles, *self.development]] + self.regional_denominator_state_ids + self.regional_target_state_ids
        if any(not state_id.startswith(self.label_level + ":") for state_id in state_ids):
            raise ValueError("scientific_choices_must_share_label_level")
        for rows in (self.roles, self.development):
            if len({row.state_id for row in rows}) != len(rows):
                raise ValueError("duplicate_scientific_choice")
            if any(len(set(row.source_ids)) != len(row.source_ids) for row in rows):
                raise ValueError("duplicate_scientific_source")
        for values in (self.regional_denominator_state_ids, self.regional_target_state_ids):
            if len(set(values)) != len(values):
                raise ValueError("duplicate_regional_choice")
        if bool(self.regional_denominator_state_ids) != bool(self.regional_target_state_ids):
            raise ValueError("regional_choices_must_be_paired")
        if not set(self.regional_target_state_ids).issubset(self.regional_denominator_state_ids):
            raise ValueError("regional_numerator_outside_denominator")
        return self


class DraftIdentity(InputBody):
    draft_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    draft_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class DraftRevision(DraftIdentity):
    candidate: ScienceCandidate


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def ref(identifier, version="0.1.0"):
    return {"object_id": identifier, "object_version": version}


class ScientificInputs:
    def __init__(self, service):
        self.service = service

    def _facts(self, state, aid):
        self.service.controls.require_ready(state)
        record = state.get("_intakes", {}).get(aid)
        if not record or record["signature"] != self.service.intake.signature(state, aid):
            raise ValueError("intake_confirmation_required")
        facts = record["facts"]
        if facts["product_family"] != "hpsc_mda":
            raise ValueError("supported_product_family_required")
        if not facts["target_cell_type"] or not facts["target_stage"] or facts["assay"] == "unknown":
            raise ValueError("scientific_intent_required")
        upload = state["_uploads"][aid]
        checked_bytes(self.service, state, self.service.directory(state["id"]) / "uploads" / (aid + ".h5ad"),
                      upload["sha256"], limit=self.service.settings.upload_limit)
        return facts

    def _catalog(self, state):
        resource = files("bridge.tool_packages.p0_02_cell_state.resources")
        biological_raw = resource.joinpath("biological_review_draft.yaml").read_bytes()
        product_raw = resource.joinpath("product_context_review_draft.yaml").read_bytes()
        biological, product = yaml.safe_load(biological_raw), yaml.safe_load(product_raw)
        vocabulary = load_packaged_vocabulary()
        if biological["vocabulary_ref"] != vocabulary.vocabulary_id:
            raise ValueError("scientific_vocabulary_mismatch")
        known = {(label.level, label.state_id) for label in vocabulary.labels}
        defaults = biological["card_defaults"]
        sources = []
        for row in biological["state_reviews"]:
            if (row["level"], row["state_id"]) not in known:
                raise ValueError("scientific_source_state_mismatch")
            sources.append({
                "source_id": "state-review:" + row["state_id"], "version": biological["version"],
                "state_id": row["state_id"], "label_level": row["level"], "definition": row["definition"],
                "anatomy_scope": defaults["anatomy_scope"], "developmental_scope": defaults["developmental_scope"],
                "derivation": row.get("derivation_summary", defaults["derivation_summary"]),
                "review_status": row.get("review_status", defaults["review_status"]),
                "limitations": row.get("review_blockers", defaults["review_blockers"]),
                "source_refs": row.get("source_ids", defaults["source_ids"]),
            })
        spec = load_measurement_spec(self.service.settings.cell_state_measurement_spec_ref)
        if spec is None:
            raise ValueError("measurement_spec_not_configured")
        reference_bindings, reference_state = [], "not_configured"
        try:
            _, resources = self.service.inputs.reference_resources(state)
            reference_bindings = resources
            reference_state = "available" if resources else "not_configured"
        except (ValueError, OSError, KeyError):
            reference_state = "unavailable"
        binding = {"biological": hashlib.sha256(biological_raw).hexdigest(),
                   "product": hashlib.sha256(product_raw).hexdigest(),
                   "vocabulary": digest(vocabulary.model_dump(mode="json")),
                   "measurement": digest(spec.model_dump(mode="json")),
                   "references": reference_bindings, "reference_state": reference_state}
        return {
            "sources": sources, "vocabulary_id": vocabulary.vocabulary_id,
            "vocabulary_version": vocabulary.version,
            "source_review_state": biological["status"], "execution_allowed": product["execution_allowed"],
            "reference_state": reference_state,
        }, binding, spec

    def _binding(self, state, aid, catalog_binding):
        # Unrelated report outputs do not stale an accepted product definition.
        return {"session_id": state["id"], "upload_id": aid, "upload_sha256": state["_uploads"][aid]["sha256"],
                "intake": state["_intakes"][aid], "declaration": self.service.intake.signature(state, aid),
                "catalog": catalog_binding,
                "upstream": [row for row in state.get("_tool_runs", []) if row["tool_id"] in {"P0-01", "P0-02"}]}

    def context(self, state, aid):
        return self.request_context(state, aid)[0]

    def request_context(self, state, aid):
        facts = self._facts(state, aid)
        catalog, catalog_binding, _ = self._catalog(state)
        context = {"purpose": "scientific_input_draft", "upload_id": aid,
                "product_intent": {key: facts[key] for key in ("product_family", "target_cell_type", "target_stage")},
                **catalog,
                "rules": [
                    "Propose only source-backed candidate choices for explicit user review; omissions remain unresolved.",
                    "A state definition supports a candidate, not a validated product role. Preserve pending review.",
                    "Culture duration is not fetal age. No time series, independence, pooling or measurements may be invented.",
                    "Use propose_scientific_inputs. Leave unsupported regional/development choices empty.",
                    "Choose one label_level: ALL role, development and regional state IDs must have that same level. Never combine L1 and L2 in one candidate.",
                    "For EACH role/development choice source_ids must be exactly [the source_id paired with that state_id]. Do not add parent/sibling citations.",
                    "Regional arrays are either both empty, or every numerator ID belongs to the denominator array. Denominator IDs must have role choices; numerator roles must be target or acceptable_adjacent.",
                    "A validation_feedback code means the previous candidate was rejected. Correct only within these constraints; no facts were accepted.",
                ]}
        return context, self._binding(state, aid, catalog_binding)

    def _validate(self, candidate, catalog):
        available = {row["state_id"]: row for row in catalog["sources"]
                     if row["label_level"] == candidate.label_level}
        for choice in [*candidate.roles, *candidate.development]:
            source = available.get(choice.state_id)
            if source is None or choice.source_ids != [source["source_id"]]:
                raise ValueError("scientific_source_not_supported")
        selected = {row.state_id for row in candidate.roles}
        if not set(candidate.regional_denominator_state_ids).issubset(selected):
            raise ValueError("regional_choice_requires_reviewable_role")
        targets = {row.state_id for row in candidate.roles if row.product_role in {"target", "acceptable_adjacent"}}
        if not set(candidate.regional_target_state_ids).issubset(targets):
            raise ValueError("regional_target_role_required")

    def propose(self, state, aid, candidate, expected_binding=None):
        from .app import uid
        facts = self._facts(state, aid)
        catalog, catalog_binding, _ = self._catalog(state)
        binding = self._binding(state, aid, catalog_binding)
        if expected_binding is not None and expected_binding != binding:
            raise ValueError("scientific_draft_stale")
        self._validate(candidate, catalog)
        if len(state.get("_scientific_drafts", [])) >= 24:
            raise ValueError("scientific_draft_count_limit")
        unknowns = ["biological_unit_relationships_unconfirmed"]
        if facts["independent_cultures"] is None:
            unknowns.append("independence_unknown")
        if not catalog["execution_allowed"] or catalog["source_review_state"] != "approved":
            unknowns.append("scientific_source_review_pending")
        if catalog["reference_state"] != "available":
            unknowns.append("reference_configuration_unavailable")
        if not candidate.regional_target_state_ids:
            unknowns.append("regional_definition_unresolved")
        if not candidate.development:
            unknowns.append("developmental_window_unresolved")
        draft = {"id": uid(), "upload_id": aid, "status": "pending",
                 "facts": deepcopy(facts), "candidate": candidate.model_dump(mode="json"),
                 "sources": catalog["sources"], "unknowns": unknowns,
                 "attestation_state": "not_confirmed", "object_ids": {},
                 "stages": [{"tool_id": tool, "state": "blocked", "reason_codes": list(unknowns)}
                            for tool in ("P0-03", "P0-04", "P0-05", "P0-06")],
                 "_binding": binding, "_input_revision": state["_input_revision"]}
        draft["digest"] = digest(draft)
        self.service.message(state, "assistant", "科学输入候选已整理。请核对来源、角色与未知项；确认只生成草稿对象，不代表完成生物学审阅，也不会运行分析。")
        draft["message_id"] = state["messages"][-1]["id"]
        for old in state.get("_scientific_drafts", []):
            if old["upload_id"] == aid and old["status"] == "pending":
                old["status"] = "superseded"
        state.setdefault("_scientific_drafts", []).append(draft)
        return self._public_record(state, draft)

    def _public_record(self, state, draft):
        value = {key: deepcopy(item) for key, item in draft.items() if not key.startswith("_")}
        if value["status"] in {"pending", "confirmed"}:
            record = state.get("_intakes", {}).get(draft["upload_id"])
            if (state["input_review_required"] or record != draft["_binding"]["intake"]
                    or self.service.intake.signature(state, draft["upload_id"]) != draft["_binding"]["declaration"]):
                value["status"] = "stale"
        value["stages"] = self.service.report_inputs.stages(state, value)
        value["internal_report"] = self.service.report_inputs.public_report(state, value)
        return value

    def public(self, state):
        return [self._public_record(state, row) for row in state.get("_scientific_drafts", [])]

    def private_message_ids(self, state):
        return {row["message_id"] for row in state.get("_scientific_drafts", [])}

    def selected_blocker(self, state, tool_id):
        if tool_id not in {"P0-03", "P0-04", "P0-05", "P0-06"}:
            return None
        selected = {row["input_id"] for row in state.get("_input_selections", {}).get(tool_id, {}).get("object_inputs", [])}
        drafts = [row for row in state.get("_scientific_drafts", [])
                  if selected.intersection(row["object_ids"].values())]
        if not drafts:
            return None
        if len(drafts) != 1:
            return "scientific_draft_version_mismatch"
        draft = drafts[0]
        try:
            self._facts(state, draft["upload_id"])
            catalog, binding, _ = self._catalog(state)
            if self._binding(state, draft["upload_id"], binding) != draft["_binding"]:
                return "scientific_draft_stale"
            if not catalog["execution_allowed"] or catalog["source_review_state"] != "approved":
                return "scientific_source_review_pending"
        except (ValueError, OSError, KeyError, HTTPException):
            return "scientific_draft_invalid_or_stale"
        return None

    def _objects(self, state, draft, catalog, spec):
        from .app import now
        candidate = ScienceCandidate.model_validate(draft["candidate"])
        key = draft["id"]
        definition_ref, role_ref = ref("product-definition:" + key), ref("state-role-map:" + key)
        provenance = [ref("scientific-input-draft:" + key)]
        sources = {row["state_id"]: row for row in catalog["sources"] if row["label_level"] == candidate.label_level}
        roles = {row.state_id: row for row in candidate.roles}
        assignments = []
        for state_id, source in sources.items():
            choice = roles.get(state_id)
            assignments.append({"state_id": state_id, "product_role": choice.product_role if choice else "role_unresolved",
                                "role_evidence_class": "source_backed_candidate" if choice else "unresolved",
                                "evidence_direction": "descriptive_only",
                                "source_refs": choice.source_ids if choice else [source["source_id"]]})
        role_map = StateRoleMap(object_version="0.1.0", state_role_map_id=role_ref["object_id"],
            map_version="0.1.0", product_definition_ref=definition_ref, review_state="draft",
            assignments=assignments, provenance_refs=provenance)
        definition = ProductDefinitionCard(object_version="0.1.0", product_definition_id=definition_ref["object_id"],
            definition_version="0.1.0", state_role_map_ref=role_ref, supported_assays=[draft["facts"]["assay"]],
            review_state="draft", provenance_refs=provenance)
        kind = {"pretransplant_preparation": "preparation", "process_sample": "sample"}.get(draft["facts"]["sampling_context"])
        if kind is None:
            raise ValueError("sampling_context_required")
        case = ProductCase(object_version="0.1.0", product_case_id="product-case:" + key, case_version="0.1.0",
            product_definition_ref=definition_ref, source_unit_kind=kind,
            sample_or_preparation_ref=ref(kind + ":upload-" + draft["upload_id"]),
            measurement_spec_ref=ref(spec.measurement_spec_id, spec.version), assay=draft["facts"]["assay"],
            provenance_refs=provenance, created_at=now())
        objects = [
            ("P0-03", "product_case", "product-case/v0.1", case),
            ("P0-03", "product_definition_card", "product-definition-card/v0.1", definition),
            ("P0-03", "state_role_map", "state-role-map/v0.1", role_map),
        ]
        if candidate.regional_target_state_ids:
            assessment = TargetRegionalAssessmentSpec(object_version="0.1.0",
                assessment_spec_id="target-regional-assessment-spec:" + key, assessment_spec_version="0.1.0",
                product_definition_ref=definition_ref, state_role_map_ref=role_ref,
                state_role_map_sha256=digest(role_map.model_dump(mode="json")), status="candidate",
                composition_views=["consensus_supported_only"], included_label_levels=[candidate.label_level],
                target_identity_numerator_product_roles=["target"],
                regional_denominator_state_ids=candidate.regional_denominator_state_ids,
                regional_target_numerator_state_ids=candidate.regional_target_state_ids,
                whole_product_target_region_state_ids=candidate.regional_target_state_ids,
                unmapped_state_policy="not_assessed", ambiguous_state_policy="not_assessed",
                spatial_policy="not_assessed_without_projection")
            objects.append(("P0-03", "target_regional_assessment_spec", "target-regional-assessment-spec/v0.1", assessment))
        if candidate.development:
            by_state = {row.state_id: row for row in candidate.development}
            development_ref = ref("development-state-map:" + key)
            development_map = DevelopmentStateMap(object_version="0.1.0", state_map_id=development_ref["object_id"],
                state_map_version="0.1.0", product_definition_ref=definition_ref,
                annotation_vocabulary_ref=catalog["vocabulary_id"], review_state="draft",
                assignments=[{"state_id": state_id, "label_level": candidate.label_level,
                    "stage_role": by_state[state_id].stage_role if state_id in by_state else "unresolved",
                    "target_related": state_id in roles and roles[state_id].product_role in {"target", "acceptable_adjacent"},
                    "provenance_refs": [ref(sources[state_id]["source_id"], sources[state_id]["version"])]}
                    for state_id in sources])
            window = DevelopmentWindowSpec(object_version="0.1.0", window_spec_id="development-window-spec:" + key,
                window_spec_version="0.1.0", product_definition_ref=definition_ref, state_map_ref=development_ref,
                review_state="candidate", applicable_assays=[draft["facts"]["assay"]],
                composition_view="consensus_supported_only", label_level=candidate.label_level, rationale_refs=provenance)
            objects.extend([("P0-04", "development_state_map", "development-state-map/v0.1", development_map),
                            ("P0-04", "development_window_spec", "development-window-spec/v0.1", window)])
        return [(tool, role, "bridge://schemas/" + schema, model.model_dump(mode="json"))
                for tool, role, schema, model in objects]

    def revise(self, state, body):
        draft = next((row for row in state.get("_scientific_drafts", []) if row["id"] == body.draft_id), None)
        if draft is None or draft["digest"] != body.draft_digest or draft["status"] not in {"pending", "confirmed"}:
            raise HTTPException(409, "scientific_draft_mismatch")
        try:
            self._facts(state, draft["upload_id"])
            _, binding, _ = self._catalog(state)
            if (self._binding(state, draft["upload_id"], binding) != draft["_binding"]
                    or draft["status"] == "pending" and state["_input_revision"] != draft["_input_revision"]):
                raise ValueError("scientific_draft_stale")
            return self.propose(state, draft["upload_id"], body.candidate, expected_binding=draft["_binding"])
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "scientific_draft_invalid_or_stale") from None

    def confirm(self, state, draft_id, draft_digest):
        draft = next((row for row in state.get("_scientific_drafts", []) if row["id"] == draft_id), None)
        if draft is None or draft["digest"] != draft_digest or draft["status"] not in {"pending", "confirmed"}:
            raise HTTPException(409, "scientific_draft_mismatch")
        try:
            self._facts(state, draft["upload_id"])
            catalog, catalog_binding, spec = self._catalog(state)
            if (self._binding(state, draft["upload_id"], catalog_binding) != draft["_binding"]
                    or draft["status"] == "pending" and state["_input_revision"] != draft["_input_revision"]):
                raise ValueError("scientific_draft_stale")
            self._validate(ScienceCandidate.model_validate(draft["candidate"]), catalog)
            if draft["status"] == "confirmed":
                for identifier in draft["object_ids"].values():
                    self.service.inputs.verify(state, state["_input_objects"][identifier])
                return
            objects = self._objects(state, draft, catalog, spec)
            for tool, role, schema, payload in objects:
                self.service.inputs.role(tool, "default", role, schema, "0.1.0")
                self.service.inputs.validate_object(payload, schema, "0.1.0")
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "scientific_draft_invalid_or_stale") from None
        trial = deepcopy(state)
        identifiers = {}
        for tool, role, schema, payload in objects:
            identifiers[role] = self.service.inputs.add_object(trial, tool_id=tool, mode_id="default",
                role=role, schema_ref=schema, object_version="0.1.0", data=encoded(payload))
        saved = next(row for row in trial["_scientific_drafts"] if row["id"] == draft_id)
        saved["object_ids"], saved["status"] = identifiers, "confirmed"
        # Publish complete candidate selections only after all objects validate.
        for tool in ("P0-03", "P0-04"):
            mode = self.service.inputs.contract_mode(tool, "default")[1]
            allowed_roles = {role.role for role in mode.roles}
            trial["_input_selections"][tool] = Selection(tool_id=tool, mode_id="default", asset_ids=[],
                object_inputs=[{"role": role, "input_id": identifier} for role, identifier in identifiers.items()
                               if role in allowed_roles], measurement_spec_ref=None).model_dump(mode="json")
        self.service.controls.fence(trial)
        trial["_input_revision"] += 1
        state.update(trial)
