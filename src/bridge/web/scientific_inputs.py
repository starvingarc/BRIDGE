"""Private source-backed candidates; deterministic objects, never measurements."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
import yaml

from bridge.tool_packages._configurable_contracts import (
    ProductCase, ProductDefinitionCard, StateRoleMap, DevelopmentWindowSpec,
)
from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
from bridge.tool_packages.p0_02_cell_state.reference import load_packaged_vocabulary
from bridge.tool_packages.p0_02_cell_state.scientific_review import load_development_review, development_review_sha256
from bridge.tool_packages.p0_03_target_regional.models import TargetRegionalAssessmentSpec
from bridge.tool_packages.p0_04_developmental_compatibility.models import DevelopmentStateMap
from .inputs import InputBody, ObjectChoice, Selection, verify_checked_file


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


SCIENTIFIC_ROOTS = {
    "P0-03": ("product_definition_card", "state_role_map", "target_regional_assessment_spec", "measurement_spec"),
    "P0-04": ("product_definition_card", "development_state_map", "development_window_spec", "measurement_spec"),
    "P0-05": ("product_definition_card", "state_role_map", "off_target_assessment_spec", "biological_unit_attestation_receipt"),
    "P0-06": ("product_definition_card", "development_window_spec", "program_spec",
              "process_method_spec", "protocol_ir", "measurement_spec", "biological_unit_attestation_receipt"),
}

# The paths are deployment-owned; these published identities and digests only
# allow the two reviewed source files to enter an approved case.
DIRECTED_PROGRAM_RESOURCES = (
    ("PLURI", "cf32f7cee11034e669d331e028b85f071d0babeb27ed7d547dca1d048d4114a0",
     "source:pluri-original-csv", "Hu-2020-Table-S1", "HU-2020", "hu_pluripotency_csv",
     "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7260443/supplementaryFiles",
     "CC-BY-NC-ND-4.0", "PROC-PLURI", "HU-2020-TABLE-S1"),
    ("DISSOC", "8c9dcbda7c2e797d70071f23f645581727892f49a15602a5dfda1e8cc7dbde17",
     "source:dissoc-original-csv", "a623cd950e18191ad69a5b2c0fab343248893f81",
     "OFLANAGAN-2019", "oflanagan_core_csv",
     "https://raw.githubusercontent.com/kieranrcampbell/scrnaseq-digestion-paper/a623cd950e18191ad69a5b2c0fab343248893f81/data/deliverables/coregene_df-FALSE-v3.csv",
     "redistribution-unconfirmed-private-only", "PROC-DISSOC", "OFLANAGAN-2019-CORE"),
)


def _admitted_directed_inputs(state, roots_by_id, tool_version):
    """Include dispatched plans that were cancelled before a tool receipt existed."""
    admitted = {row["plan_id"] for assessment in
                [*state.get("_assessment_history", []), state.get("_assessment") or {}]
                for row in assessment.get("admissions", [])
                if (row.get("tool_id"), row.get("mode_id")) == ("P0-06", "directed_programs")}
    plans = [state.get("_plan"), *(row.get("plan") for row in state.get("_plan_history", []))]
    attempted = set()
    for plan in plans:
        if not isinstance(plan, dict) or plan.get("plan_id") not in admitted:
            continue
        for step in plan.get("steps", []):
            if step.get("tool_id") != "P0-06" or not step.get("approved_request_json"):
                continue
            request = json.loads(step["approved_request_json"])
            if request.get("tool_version") != tool_version:
                continue
            for ref in request.get("object_inputs", []):
                record = roots_by_id.get(ref.get("input_id"))
                if (ref.get("role") == "directed_program_input" and record is not None
                        and ref.get("sha256") == record["sha256"]
                        and ref.get("schema_ref") == record["schema_ref"]):
                    attempted.add(ref["input_id"])
    return attempted


class ScientificInputs:
    def __init__(self, service):
        self.service = service

    def register_program_input(self, state, upload_id, view, qc_id, qc_receipt):
        """Pin one configured official resource and its exact QC view before scope approval."""
        from bridge.tool_packages._structured_runtime import read_regular_bytes
        from bridge.tool_packages.p0_06_proliferation_stress_response.candidate_programs import (
            CandidateProgramSelection, ExploratoryProgramInput, ProgramResourceBinding,
        )
        from .sessions import write_file

        configured = os.environ.get("BRIDGE_P006_PROGRAM_RESOURCE_PATH")
        expected = os.environ.get("BRIDGE_P006_PROGRAM_RESOURCE_SHA256")
        if not configured or expected != "bc465ea8f94009689abdff725ffa16bbd9a38a7d13a876d046727fae49f61f2c":
            raise ValueError("program_resource_not_configured")
        source = Path(configured)
        if not source.is_absolute() or any(part.is_symlink() for part in (source, *source.parents)):
            raise ValueError("program_resource_path_invalid")
        raw = read_regular_bytes(source)
        if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("program_resource_integrity_mismatch")
        # Only a server-configured resource can enter the private session; no browser path is accepted.
        target = self.service.directory(state["id"]) / "resources" / ("hallmark-" + expected + ".json")
        if target.exists():
            from .inputs import verify_checked_file
            verify_checked_file(self.service, state, target, expected)
        else:
            write_file(target, raw)
        resource = ProgramResourceBinding(resource_ref="source:msigdb-hallmark-human-2026-1",
            resource_version="2026.1.Hs", source_family_id="MSIGDB-HALLMARK", path=target,
            sha256=expected,
            source_url="https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2026.1.Hs/h.all.v2026.1.Hs.json",
            license_ref="CC-BY-4.0", format="msigdb_hallmark_json")
        inputs = self.service.inputs
        qc = inputs.verify(state, state["_input_objects"][qc_id])
        if qc["selected_data_view"] != view or view["parent_asset_id"] != upload_id:
            raise ValueError("program_qc_view_mismatch")
        asset = inputs.selected_asset(state, "P0-06", upload_id)
        if asset.checksum != view["sha256"]:
            raise ValueError("program_asset_view_mismatch")
        run, _ = inputs.producer_objects(state, qc_receipt, "P0-01", set())
        programs = [CandidateProgramSelection(program_id=program_id, source_gene_set=gene_set)
                    for program_id, gene_set in (
                        ("PROC-ROS", "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY"),
                        ("PROC-UPR", "HALLMARK_UNFOLDED_PROTEIN_RESPONSE"),
                        ("PROC-APOPTOSIS", "HALLMARK_APOPTOSIS"),
                        ("PROC-HYPOXIA", "HALLMARK_HYPOXIA"))]
        value = ExploratoryProgramInput(object_version="0.2.0",
            input_id="exploratory-programs:assessment-" + digest({"view": view, "resource": expected})[:24],
            source_family_id=state["_uploads"][upload_id]["source_family_id"],
            data_view=view, gene_symbol_column=asset.metadata.get("gene_symbol_column"),
            resource=resource, programs=programs, gene_coverage_policy="observed_subset",
            created_at=run.created_at)
        return inputs.add_derived_object(state, tool_id="P0-06", mode_id="exploratory_programs",
            role="exploratory_program_input", schema_ref="bridge://schemas/exploratory-process-input/v0.2",
            payload=value.model_dump(mode="json"), dependencies=[qc_id],
            file_dependencies=[{"path": str(target), "sha256": expected}])

    def register_directed_program_inputs(self, state, upload_id, view, qc_id, qc_receipt):
        """Register configured, hash-pinned source candidates; never accept a browser path."""
        from bridge.tool_packages._structured_runtime import read_regular_bytes
        from bridge.tool_packages.p0_06_proliferation_stress_response.candidate_programs import (
            DirectedProgramInput, DirectedProgramSelection, DirectedResourceBinding,
        )
        from .sessions import write_file

        inputs = self.service.inputs
        qc = inputs.verify(state, state["_input_objects"][qc_id])
        if qc["selected_data_view"] != view or view["parent_asset_id"] != upload_id:
            raise ValueError("program_qc_view_mismatch")
        asset = inputs.selected_asset(state, "P0-06", upload_id)
        if asset.checksum != view["sha256"]:
            raise ValueError("program_asset_view_mismatch")
        run, _ = inputs.producer_objects(state, qc_receipt, "P0-01", set())
        identifiers = []
        for (name, expected, resource_ref, version, family, format_, url, license_ref,
             program_id, source_gene_set) in DIRECTED_PROGRAM_RESOURCES:
            configured = os.environ.get(f"BRIDGE_P006_{name}_RESOURCE_PATH")
            if not configured:
                continue
            source = Path(configured)
            if not source.is_absolute() or any(part.is_symlink() for part in (source, *source.parents)):
                raise ValueError("program_resource_path_invalid")
            raw = read_regular_bytes(source)
            if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("program_resource_integrity_mismatch")
            target = self.service.directory(state["id"]) / "resources" / (name.lower() + "-" + expected + ".csv")
            if target.exists():
                verify_checked_file(self.service, state, target, expected)
            else:
                write_file(target, raw)
            resource = DirectedResourceBinding(resource_ref=resource_ref, resource_version=version,
                source_family_id=family, path=target, sha256=expected, source_url=url,
                license_ref=license_ref, format=format_)
            value = DirectedProgramInput(object_version="0.3.0",
                input_id="directed-program:assessment-" + digest({"view": view, "resource": expected})[:24],
                source_family_id=state["_uploads"][upload_id]["source_family_id"],
                data_view=view, gene_symbol_column=asset.metadata.get("gene_symbol_column"),
                resource=resource, programs=[DirectedProgramSelection(program_id=program_id,
                    source_gene_set=source_gene_set)], gene_coverage_policy="observed_subset",
                created_at=run.created_at)
            identifiers.append(inputs.add_derived_object(state, tool_id="P0-06", mode_id="directed_programs",
                role="directed_program_input", schema_ref="bridge://schemas/exploratory-process-input/v0.3",
                payload=value.model_dump(mode="json"), dependencies=[qc_id],
                file_dependencies=[{"path": str(target), "sha256": expected}]))
        return identifiers

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
        verify_checked_file(
            self.service,
            state,
            self.service.directory(state["id"]) / "uploads" / (aid + ".h5ad"),
            upload["sha256"],
            limit=self.service.settings.max_upload_bytes,
        )
        return facts

    def _catalog(self, state):
        resource = files("bridge.tool_packages.p0_02_cell_state.resources")
        biological_raw = resource.joinpath("biological_review_draft.yaml").read_bytes()
        product_raw = resource.joinpath("product_context_review_draft.yaml").read_bytes()
        biological, product = yaml.safe_load(biological_raw), yaml.safe_load(product_raw)
        review = load_development_review("1.1.0")
        vocabulary = load_packaged_vocabulary()
        if review.vocabulary_ref != vocabulary.vocabulary_id:
            raise ValueError("scientific_vocabulary_mismatch")
        known = {(label.level, label.state_id) for label in vocabulary.labels}
        defaults = biological["card_defaults"]
        sources = []
        for row in review.state_reviews:
            level = row.state_id.split(":", 1)[0]
            if (level, row.state_id) not in known:
                raise ValueError("scientific_source_state_mismatch")
            sources.append({
                "source_id": "state-review:" + row.state_id, "version": review.object_version,
                "state_id": row.state_id, "label_level": level, "definition": row.definition,
                "anatomy_scope": defaults["anatomy_scope"], "developmental_scope": defaults["developmental_scope"],
                "derivation": row.rationale, "review_status": review.status,
                "decision": row.decision, "parent_state_id": row.parent_state_id,
                "default_product_role": row.default_product_role,
                "limitations": row.limitations, "source_refs": row.source_ids,
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
        binding = {"biological": development_review_sha256("1.1.0"),
                   "legacy_biological": hashlib.sha256(biological_raw).hexdigest(),
                   "product": hashlib.sha256(product_raw).hexdigest(),
                   "vocabulary": digest(vocabulary.model_dump(mode="json")),
                   "measurement": digest(spec.model_dump(mode="json")),
                   "references": reference_bindings, "reference_state": reference_state}
        return {
            "sources": sources, "vocabulary_id": vocabulary.vocabulary_id,
            "vocabulary_version": vocabulary.version,
            "source_review_state": review.status, "scientific_qualification": review.scientific_qualification,
            "execution_allowed": product["execution_allowed"],
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
                    "A complete source review is not product-role approval. parent_only and unavailable states cannot be target, adjacent, off-target or regional identities.",
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
            if source["decision"] != "evaluate":
                if (isinstance(choice, RoleChoice) and choice.product_role != "role_unresolved"
                        or isinstance(choice, DevelopmentChoice) and choice.stage_role != "unresolved"):
                    raise ValueError("scientific_source_identity_unavailable")
        if any(available[state_id]["decision"] != "evaluate"
               for state_id in candidate.regional_denominator_state_ids
               if state_id in available):
            raise ValueError("scientific_source_identity_unavailable")
        selected = {row.state_id for row in candidate.roles}
        if not set(candidate.regional_denominator_state_ids).issubset(selected):
            raise ValueError("regional_choice_requires_reviewable_role")
        targets = {row.state_id for row in candidate.roles if row.product_role in {"target", "acceptable_adjacent"}}
        if not set(candidate.regional_target_state_ids).issubset(targets):
            raise ValueError("regional_target_role_required")

    def propose(self, state, aid, candidate, expected_binding=None):
        from .sessions import uid
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
            unknowns.append("state_role_review_required" if catalog["source_review_state"] == "complete"
                            else "scientific_source_review_pending")
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
        self.service.message(state, "assistant", "科学输入候选已整理。请核对来源、角色与未知项；确认只生成草稿对象，不代表完成生物学审阅，也不会运行分析。", source="server_template")
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


    def exploratory_resource(self):
        raw = files("bridge.tool_packages.p0_06_proliferation_stress_response").joinpath(
            "resources/seurat-cell-cycle-v5.5.1-candidate.json").read_bytes()
        value = json.loads(raw)
        if (value["selection"]["scientific_release_approved"] is not False
                or value["candidate_version"] != "0.1.0"
                or value["status"] != "owner_selected_resource_candidate_not_ProgramSpec"):
            raise ValueError("exploratory_resource_policy_mismatch")
        return value, {"alias": "R-seurat-cell-cycle-v5.5.1", "schema_ref": None,
            "resource_ref": "bridge://resources/seurat-cell-cycle-candidate/v5.5.1",
            "object_version": value["candidate_version"], "sha256": hashlib.sha256(raw).hexdigest(),
            "source": "package_resource"}

    def _exploratory_selection(self, state, scope, selection):
        if selection.object_inputs:
            return selection
        from bridge.tool_packages.p0_06_proliferation_stress_response.exploratory_models import ExploratoryProcessInput
        inputs = self.service.inputs
        self._facts(state, scope.upload_id)
        value, resource = self.exploratory_resource()
        if scope.binding["science"].get(resource["resource_ref"]) != resource["sha256"]:
            raise ValueError("exploratory_resource_changed")
        pool = inputs.assessment_pool(state, scope)
        selected = scope.binding["data_view"]
        candidates = []
        for identifier, record in pool.items():
            if record["source"] != "tool_output" or record.get("producer_tool_id") != "P0-01":
                continue
            if inputs.receipt_artifacts(state, record)[record["artifact_id"]]["kind"] != "qc_profile_v2":
                continue
            qc = inputs.verify(state, record)
            actual = qc.get("selected_data_view")
            if actual is not None and (selected is None or actual == selected):
                if actual["parent_asset_id"] == scope.upload_id and actual["parent_asset_sha256"] == scope.binding["upload"]["sha256"]:
                    candidates.append((identifier, qc))
        if len(candidates) != 1:
            raise ValueError("canonical_source_required:qc_readiness_profile")
        identifier, qc = candidates[0]
        selected = qc["selected_data_view"]
        record = pool[identifier]
        receipt = next(row for row in state["_tool_runs"] if row["file"] == record["receipt_file"])
        run, _ = inputs.producer_objects(state, receipt, "P0-01", set())
        asset = inputs.selected_asset(state, "P0-06", scope.upload_id)
        if (asset.checksum != selected["sha256"] or selected["parent_asset_id"] != scope.upload_id
                or selected["parent_asset_sha256"] != scope.binding["upload"]["sha256"]):
            raise ValueError("scientific_selected_view_mismatch")
        s, g2m = value["lists"]["s.genes"], value["lists"]["g2m.genes"]
        payload = ExploratoryProcessInput(object_version="0.1.0",
            input_id="exploratory-process:assessment-" + digest({"view": selected, "resource": resource,
                "producer": record["receipt_sha256"], "gene_symbol_column": asset.metadata.get("gene_symbol_column")})[:24],
            source_family_id=state["_uploads"][scope.upload_id]["source_family_id"], data_view=selected,
            gene_symbol_column=asset.metadata.get("gene_symbol_column"),
            resource_ref=resource["resource_ref"], resource_version=value["candidate_version"],
            resource_sha256=resource["sha256"], s_genes=s["genes"], s_genes_sha256=s["sha256"],
            g2m_genes=g2m["genes"], g2m_genes_sha256=g2m["sha256"], created_at=run.created_at)
        object_id = inputs.add_derived_object(state, tool_id="P0-06", mode_id="exploratory_process",
            role="exploratory_process_input", schema_ref="bridge://schemas/exploratory-process-input/v0.1",
            payload=payload.model_dump(mode="json"), dependencies=[identifier])
        return selection.model_copy(update={"asset_ids": [scope.upload_id],
            "object_inputs": [ObjectChoice(role="exploratory_process_input", input_id=object_id)]})

    def assessment_blockers(self, state, scope, allowed):
        """Expose every missing caller-owned root without changing package eligibility."""
        if (allowed.tool_id, allowed.mode_id) not in {
                ("P0-03", "default"), ("P0-04", "default"),
                ("P0-05", "hard_count_accounting")}:
            return []
        inputs = self.service.inputs
        selected = scope.binding["selections"].get(allowed.tool_id, {})
        contract, mode = inputs.contract_mode(allowed.tool_id, allowed.mode_id)
        counts = {role.role: sum(row["role"] == role.role for row in selected.get("object_inputs", []))
                  for role in mode.roles}
        assets = mode.asset_input or contract.asset_input
        if (all(counts[role.role] >= role.min_count for role in mode.roles)
                and len(selected.get("asset_ids", [])) >= (assets.min_count if assets else 0)):
            return []
        choices = {row["role"]: row["input_id"] for row in selected.get("object_inputs", [])}
        shared = {row["role"]: row["input_id"] for row in
                  scope.binding["selections"].get("P0-03", {}).get("object_inputs", [])}
        if allowed.tool_id != "P0-03":
            for role in ("product_definition_card", "state_role_map"):
                choices.setdefault(role, shared.get(role))
        blockers = ["scientific_resource_required:" + role for role in SCIENTIFIC_ROOTS[allowed.tool_id]
                    if not choices.get(role)]
        if not choices.get("product_case") and scope.binding["intake"]["facts"].get("sampling_context") not in {
                "pretransplant_preparation", "process_sample"}:
            blockers.append("biological_source_unit_required")
        try:
            pool = inputs.assessment_pool(state, scope)
        except (ValueError, OSError, KeyError):
            return blockers
        reviews = {"state_role_map": ("review_state", {"reviewed", "frozen"}, "state_role_review_required"),
                   "target_regional_assessment_spec": ("status", {"frozen"}, "regional_definition_review_required"),
                   "development_state_map": ("review_state", {"reviewed", "frozen"}, "development_state_review_required"),
                   "development_window_spec": ("review_state", {"confirmed"}, "development_window_review_required")}
        for role in SCIENTIFIC_ROOTS[allowed.tool_id]:
            identifier = choices.get(role)
            if not identifier:
                continue
            record = pool.get(identifier)
            if record is None:
                blockers.append("scientific_resource_outside_scope")
                continue
            if role not in reviews:
                continue
            try:
                value = inputs.verify(state, record)
            except (ValueError, OSError, KeyError):
                blockers.append("scientific_resource_invalid:" + role)
                continue
            field, accepted, reason = reviews[role]
            if value.get(field) not in accepted:
                blockers.append(reason)
            if role == "development_window_spec" and (
                    not value.get("reviewer_ref") or not value.get("confirmed_at")):
                blockers.append("development_window_review_required")
        return sorted(set(blockers))

    def spatial_link_gaps(self, state, scope, allowed):
        """Optional visual prerequisites remain pending under normal scope/budget rules."""
        if (self.service.settings.spatial_reference_manifest_path is None
                or (allowed.tool_id, allowed.mode_id) != ('P0-02', None)):
            return []
        view = scope.binding.get('data_view')
        if view is None:
            return ['spatial_link_qc_view_required']
        try:
            return self.service.spatial_contexts.source_gaps(state, view)
        except (ValueError, OSError, KeyError, HTTPException):
            return ['spatial_link_source_verification_required']

    def assessment_selection(self, state, scope, allowed, selection):
        """Join selected reviewed roots to exact QC/P0-02 producer objects."""
        if (allowed.tool_id in {"P0-03", "P0-04", "P0-05"}
                and allowed.mode_id == "saved_cell_state_context"):
            roots = [(key, row) for key, row in scope.binding["resources"].items()
                     if row.get("label") == "saved_cell_state_run"
                     and row["schema_ref"] == "bridge://schemas/tool-run/v0.1"]
            if len(roots) != 1:
                raise ValueError("canonical_saved_cell_state_required")
            identifier, record = roots[0]
            saved = self.service.inputs.verify(state, record)
            if (saved["request"]["tool_id"] != "P0-02"
                    or saved["result"]["input_data_view"] != scope.binding["data_view"]):
                raise ValueError("saved_cell_state_scope_mismatch")
            role_choices = [row for row in selection.object_inputs
                            if allowed.tool_id == "P0-03"
                            and row.role in {"state_role_map", "product_definition_card"}]
            return selection.model_copy(update={"asset_ids": [],
                "object_inputs": [ObjectChoice(role="saved_cell_state_run", input_id=identifier), *role_choices]})
        if (allowed.tool_id, allowed.mode_id) == ("P0-06", "exploratory_process"):
            return self._exploratory_selection(state, scope, selection)
        if (allowed.tool_id, allowed.mode_id) == ("P0-06", "exploratory_programs"):
            roots = [(key, row) for key, row in scope.binding["resources"].items()
                     if row["schema_ref"] == "bridge://schemas/exploratory-process-input/v0.2"]
            if len(roots) != 1:
                raise ValueError("canonical_program_input_required")
            identifier, record = roots[0]
            payload = self.service.inputs.verify(state, record)
            if payload["data_view"] != scope.binding["data_view"]:
                raise ValueError("program_scope_view_mismatch")
            return selection.model_copy(update={"asset_ids": [scope.upload_id],
                "object_inputs": [ObjectChoice(role="exploratory_program_input", input_id=identifier)]})
        if (allowed.tool_id, allowed.mode_id) == ("P0-06", "directed_programs"):
            roots = [(key, row) for key, row in scope.binding["resources"].items()
                     if row["schema_ref"] == "bridge://schemas/exploratory-process-input/v0.3"]
            roots_by_id = dict(roots)
            bound = scope.binding["selections"].get("P0-06", {})
            frozen = ([row["input_id"] for row in bound.get("object_inputs", [])
                       if row["role"] == "directed_program_input"]
                      if bound.get("mode_id") == "directed_programs" else [])
            offered = [row.input_id for row in selection.object_inputs
                       if row.role == "directed_program_input"]
            if frozen and offered and frozen != offered:
                raise ValueError("directed_source_selection_changed")
            selected = frozen or offered
            if selected:
                if len(selected) != 1 or selected[0] not in roots_by_id:
                    raise ValueError("canonical_directed_program_input_required")
                identifier = selected[0]
            else:
                # Terminal attempts are not silently retried, including failed
                # or partially available methods. A new explicit selection and
                # approval is required to retry the same immutable input.
                from bridge.toolkit.contracts import ToolRunV2
                from .inputs import checked_bytes, strict_json
                version = next(spec.version for spec in self.service.registry.list()
                               if spec.tool_id == "P0-06")
                attempted = _admitted_directed_inputs(state, roots_by_id, version)
                for receipt in state.get("_tool_runs", []):
                    if (receipt["file"] in state.get("_invalidated_receipts", {})
                            or receipt["tool_id"] != "P0-06"
                            or receipt["state"] not in {"succeeded", "partial", "failed", "skipped", "not_implemented"}):
                        continue
                    payload = strict_json(checked_bytes(self.service, state,
                        self.service.directory(state["id"]) / "receipts" / receipt["file"],
                        receipt["sha256"]), 128 * 1024 * 1024)
                    run = ToolRunV2.model_validate(payload) if "object_inputs" in payload["request"] else None
                    if run is None or run.tool_version != version or run.execution_state.value != receipt["state"]:
                        continue
                    for input_ref in run.request.object_inputs:
                        record = roots_by_id.get(input_ref.input_id)
                        if (input_ref.role == "directed_program_input" and record is not None
                                and input_ref.sha256 == record["sha256"]
                                and input_ref.schema_ref == record["schema_ref"]):
                            attempted.add(input_ref.input_id)
                remaining = [key for key, _ in roots if key not in attempted]
                if not remaining:
                    raise ValueError("directed_program_source_required")
                # Stable scientific order is explicit in the reviewed resource
                # table, never inferred from opaque object IDs or list position.
                by_set = {self.service.inputs.verify(state, roots_by_id[key])["programs"][0]["source_gene_set"]: key
                          for key in remaining}
                identifier = next(by_set[source_gene_set] for *_, source_gene_set in DIRECTED_PROGRAM_RESOURCES
                                  if source_gene_set in by_set)
            payload = self.service.inputs.verify(state, roots_by_id[identifier])
            if payload["data_view"] != scope.binding["data_view"]:
                raise ValueError("program_scope_view_mismatch")
            return selection.model_copy(update={"asset_ids": [scope.upload_id],
                "object_inputs": [ObjectChoice(role="directed_program_input", input_id=identifier)]})
        routes = {("P0-03", "default"), ("P0-04", "default"),
                  ("P0-05", "hard_count_accounting"), ("P0-06", "method_runtime_source_bound")}
        if (allowed.tool_id, allowed.mode_id) not in routes:
            return selection
        inputs = self.service.inputs
        contract, mode = inputs.contract_mode(allowed.tool_id, allowed.mode_id)
        counts = {role.role: sum(row.role == role.role for row in selection.object_inputs) for role in mode.roles}
        assets = mode.asset_input or contract.asset_input
        if (all(counts[role.role] >= role.min_count for role in mode.roles)
                and len(selection.asset_ids) >= (assets.min_count if assets else 0)
                and allowed.tool_id not in {"P0-03", "P0-05"}):
            # Product assessments must check the same frozen roots and QC view
            # even when the caller supplied every required object explicitly.
            return selection
        facts = self._facts(state, scope.upload_id)
        pool = inputs.assessment_pool(state, scope)
        choices = {row.role: row.input_id for row in selection.object_inputs}
        shared = {row["role"]: row["input_id"] for row in
                  scope.binding["selections"].get("P0-03", {}).get("object_inputs", [])}
        for role in ("product_definition_card", "state_role_map"):
            if role not in choices and role in shared:
                choices[role] = shared[role]
            elif role in choices and role in shared and choices[role] != shared[role]:
                raise ValueError("shared_scientific_resource_mismatch")
        if allowed.tool_id == "P0-06" and "development_window_spec" not in choices:
            shared_window = [row["input_id"] for row in
                scope.binding["selections"].get("P0-04", {}).get("object_inputs", [])
                if row["role"] == "development_window_spec"]
            if len(shared_window) == 1:
                choices["development_window_spec"] = shared_window[0]
        required = SCIENTIFIC_ROOTS[allowed.tool_id]
        for role in required:
            if role not in choices:
                raise ValueError("scientific_resource_required:" + role)
            if choices[role] not in pool:
                raise ValueError("scientific_resource_outside_scope")
        if "state_role_map" in choices:
            role_map = inputs.verify(state, pool[choices["state_role_map"]])
            if role_map["review_state"] not in {"reviewed", "frozen"}:
                raise ValueError("state_role_review_required")
        if allowed.tool_id == "P0-03":
            assessment = inputs.verify(state, pool[choices["target_regional_assessment_spec"]])
            if assessment["status"] != "frozen":
                raise ValueError("regional_definition_review_required")
        if allowed.tool_id in {"P0-04", "P0-06"}:
            if allowed.tool_id == "P0-04":
                mapping = inputs.verify(state, pool[choices["development_state_map"]])
                if mapping["review_state"] not in {"reviewed", "frozen"}:
                    raise ValueError("development_state_review_required")
            window = inputs.verify(state, pool[choices["development_window_spec"]])
            if window["review_state"] != "confirmed" or not window.get("reviewer_ref") or not window.get("confirmed_at"):
                raise ValueError("development_window_review_required")
        producer_roles = {
            "qc_readiness_profile": ("P0-01", "qc_profile_v2"),
            "biological_unit_manifest": ("P0-01", "biological_unit_manifest"),
            "biological_unit_assignment": ("P0-01", "biological_unit_assignment"),
            "cell_state_evidence_profile": ("P0-02", "cell_state_profile_v3"),
        }
        view = scope.binding["data_view"]
        for role, (tool, kind) in producer_roles.items():
            found = []
            for identifier, record in pool.items():
                if record["source"] != "tool_output" or record.get("producer_tool_id") != tool:
                    continue
                artifacts = inputs.receipt_artifacts(state, record)
                if artifacts[record["artifact_id"]]["kind"] != kind:
                    continue
                payload = inputs.verify(state, record)
                actual_view = payload.get("selected_data_view", payload.get("input_data_view"))
                if actual_view is not None and view is not None and actual_view != view:
                    continue
                if role == "biological_unit_manifest" and view is not None and (
                        payload["data_view_ref"] != view["view_id"] or payload["selected_artifact_sha256"] != view["sha256"]):
                    continue
                if role == "biological_unit_assignment" and view is not None and (
                        payload["data_view_ref"] != view["view_id"]
                        or payload["observation_ids_sha256"] != view["observation_ids_sha256"]):
                    continue
                found.append(identifier)
            if role in choices:
                if choices[role] not in found:
                    raise ValueError("canonical_source_binding_mismatch")
            elif len(found) == 1:
                choices[role] = found[0]
            elif not found:
                raise ValueError("canonical_source_required:" + role)
            else:
                raise ValueError("canonical_source_ambiguous:" + role)
        for role in ("annotation_vocabulary", "reference_manifest"):
            if role not in choices:
                found = [identifier for identifier, record in pool.items()
                         if record["source"] == "system_resource" and record["label"] == role]
                if len(found) != 1:
                    raise ValueError("scientific_resource_required:" + role)
                choices[role] = found[0]
        qc = inputs.verify(state, pool[choices["qc_readiness_profile"]])
        profile = inputs.verify(state, pool[choices["cell_state_evidence_profile"]])
        view = qc["selected_data_view"]
        if view is None or profile["input_data_view"] != view or view["parent_asset_id"] != scope.upload_id:
            raise ValueError("scientific_selected_view_mismatch")
        if view["parent_asset_sha256"] != scope.binding["upload"]["sha256"]:
            raise ValueError("scientific_parent_binding_mismatch")
        if "product_case" not in choices:
            manifest_id = choices["biological_unit_manifest"]
            manifest = inputs.verify(state, pool[manifest_id])
            definition_id = choices["product_definition_card"]
            definition = inputs.verify(state, pool[definition_id])
            source_ref = view.get("sample_or_preparation_ref")
            kind = {"pretransplant_preparation": "preparation", "process_sample": "sample"}.get(facts["sampling_context"])
            if kind is None or not source_ref or not source_ref.startswith(kind + ":"):
                raise ValueError("biological_source_unit_required")
            source_id, source_version = source_ref.rsplit("@", 1)
            groups = {row["independence_group_ref"]["object_id"] + "@" + row["independence_group_ref"]["object_version"]:
                      row["independence_group_ref"] for row in manifest["unit_bindings"]}
            source_record = pool[choices["cell_state_evidence_profile"]]
            receipt = next(row for row in state["_tool_runs"] if row["file"] == source_record["receipt_file"])
            source_run, _ = inputs.producer_objects(state, receipt, "P0-02", set())
            dependencies = [definition_id, manifest_id, choices["qc_readiness_profile"],
                            choices["cell_state_evidence_profile"]]
            content = dict(object_version="0.1.0", product_case_id="product-case:assessment-" + scope.upload_id,
                product_definition_ref=ref(definition["product_definition_id"], definition["definition_version"]),
                source_unit_kind=kind, sample_or_preparation_ref=ref(source_id, source_version),
                independence_group_refs=[groups[key] for key in sorted(groups)],
                biological_unit_manifest_ref=ref(manifest["manifest_id"], manifest["manifest_version"]),
                biological_unit_manifest_sha256=pool[manifest_id]["sha256"],
                independence_scope_ref=manifest["independence_scope_ref"],
                measurement_spec_ref=ref(profile["measurement_spec_id"], profile["measurement_spec_version"]),
                assay=facts["assay"], provenance_refs=[
                    ref("upload:" + scope.upload_id, scope.binding["upload"]["sha256"]),
                    ref("tool-run:" + source_run.run_id, source_run.tool_version)],
                created_at=source_run.created_at.isoformat())
            # Versioned references must distinguish every variable case field and source,
            # not merely the content-addressed registration file that carries them.
            case = ProductCase(case_version=digest({
                "content": content, "view": view,
                "dependencies": [{"input_id": identifier, "sha256": pool[identifier]["sha256"]}
                                 for identifier in dependencies]})[:24], **content)
            choices["product_case"] = inputs.add_derived_object(state, tool_id=allowed.tool_id, mode_id=allowed.mode_id,
                role="product_case", schema_ref="bridge://schemas/product-case/v0.1", payload=case.model_dump(mode="json"),
                dependencies=dependencies)
        if allowed.tool_id == "P0-06":
            choices = self._source_bound_process(state, allowed, choices, pool)
        _, mode = inputs.contract_mode(allowed.tool_id, allowed.mode_id)
        accepted = {row.role for row in mode.roles}
        return selection.model_copy(update={
            "asset_ids": [scope.upload_id] if allowed.tool_id == "P0-06" else selection.asset_ids,
            "object_inputs": [ObjectChoice(role=role, input_id=identifier)
                              for role, identifier in choices.items() if role in accepted]})

    def _source_bound_process(self, state, allowed, choices, pool):
        if "process_method_input" in choices:
            return choices
        from .inputs import P006_SOURCE_ARTIFACTS
        from bridge.tool_packages.p0_06_proliferation_stress_response.method_models import ProcessMethodInputV2
        inputs = self.service.inputs
        profile_id = choices["cell_state_evidence_profile"]
        profile_record = pool[profile_id]
        profile = inputs.verify(state, profile_record)
        case_id = choices["product_case"]
        case = inputs.verify(state, state["_input_objects"][case_id])
        manifest_id = choices["biological_unit_manifest"]
        manifest = inputs.verify(state, pool[manifest_id])
        view = profile["input_data_view"]
        receipt = next(row for row in state["_tool_runs"] if row["file"] == profile_record["receipt_file"])
        run, _ = inputs.producer_objects(state, receipt, "P0-02", set())
        source_artifacts = {}
        for identifier, artifact in state["_canonical_artifacts"].items():
            if (artifact["receipt_file"] != receipt["file"] or artifact["receipt_sha256"] != receipt["sha256"]):
                continue
            kind = inputs.receipt_artifacts(state, artifact)[artifact["artifact_id"]]["kind"]
            if kind in {"manifest", "cell_state_evidence"}:
                prior = source_artifacts.get(kind)
                if prior is not None and prior[1] != artifact:
                    raise ValueError("canonical_source_artifact_ambiguous")
                source_artifacts[kind] = (identifier, artifact)
        if set(source_artifacts) != {"manifest", "cell_state_evidence"}:
            raise ValueError("canonical_source_artifacts_required")
        manifest_artifact, evidence = source_artifacts["manifest"], source_artifacts["cell_state_evidence"]
        content = {"case": state["_input_objects"][case_id]["sha256"], "profile": profile_record["sha256"],
                   "source_manifest": manifest_artifact[1]["sha256"], "evidence": evidence[1]["sha256"],
                   "unit_manifest": pool[manifest_id]["sha256"],
                   "assignment": pool[choices["biological_unit_assignment"]]["sha256"]}
        payload = {
            "object_version": "0.2.0", "method_input_id": "process-method-input:assessment-" + digest(content)[:24],
            "method_input_version": digest(content)[:24],
            "product_case_ref": case["product_case_id"] + "@" + case["case_version"],
            "product_case_sha256": content["case"], "cell_state_profile_id": profile["profile_id"],
            "cell_state_profile_sha256": profile_record["sha256"], "data_view_ref": view["view_id"],
            "observation_ids_sha256": view["observation_ids_sha256"],
            "biological_unit_manifest_ref": manifest["manifest_id"] + "@" + manifest["manifest_version"],
            "biological_unit_manifest_sha256": pool[manifest_id]["sha256"],
            "biological_unit_assignment_sha256": content["assignment"],
            "source_observations": {
                "source_format": "p0_02_cell_state_evidence_parquet_v0.1", "producer_tool_id": "P0-02",
                "producer_run_ref": run.run_id, "producer_tool_version": run.tool_version,
                "artifact_manifest_path": "artifact:" + manifest_artifact[0],
                "artifact_manifest_sha256": manifest_artifact[1]["sha256"],
                "evidence_artifact_id": evidence[1]["artifact_id"], "evidence_path": "artifact:" + evidence[0],
                "evidence_sha256": evidence[1]["sha256"], "label_level": "L1"},
            "created_at": run.created_at.isoformat()}
        payload, artifacts = inputs.bind_nested(state, payload, P006_SOURCE_ARTIFACTS)
        payload = ProcessMethodInputV2.model_validate(payload).model_dump(mode="json")
        choices["process_method_input"] = inputs.add_derived_object(state, tool_id=allowed.tool_id,
            mode_id=allowed.mode_id, role="process_method_input",
            schema_ref="bridge://schemas/process-method-input/v0.2", payload=payload,
            dependencies=[case_id, profile_id, manifest_id, choices["biological_unit_assignment"]],
            artifact_dependencies=artifacts)
        return choices

    def selected_blocker(self, state, tool_id, selection=None):
        if tool_id not in {"P0-03", "P0-04", "P0-05", "P0-06"}:
            return None
        saved = selection.model_dump(mode="json") if selection is not None else state.get("_input_selections", {}).get(tool_id, {})
        selected = {row["input_id"] for row in saved.get("object_inputs", [])}
        pending = list(selected)
        while pending:
            identifier = pending.pop()
            for dependency in state["_input_objects"].get(identifier, {}).get("derivation_inputs", {}):
                if dependency not in selected:
                    selected.add(dependency)
                    pending.append(dependency)
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
                return ("state_role_review_required" if catalog["source_review_state"] == "complete"
                        else "scientific_source_review_pending")
        except (ValueError, OSError, KeyError, HTTPException):
            return "scientific_draft_invalid_or_stale"
        return None

    def _objects(self, state, draft, catalog, spec):
        from .sessions import now
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
