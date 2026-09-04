from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import importlib
from io import StringIO
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
import pytest

from bridge.tool_packages.p0_09_evidence_compiler.models import (
    EvidenceRecord,
    EvidenceRecordSet,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.tool_packages.p0_10_claim_verifier.adapter import adapter
from bridge.tool_packages.p0_10_claim_verifier.models import (
    EXTERNAL_BENCHMARK_ID,
    EXTERNAL_BENCHMARK_SHA256,
    PUBLIC_SCHEMA_MODELS,
    ClaimCheckRecord,
    ClaimPolicySpec,
    ClaimVerificationResult,
    CheckOutcome,
    CheckSeverity,
    ReportDraft,
    StatementRegistry,
    report_content_hash,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import (
    load_release_contract,
    release_contract_sha256,
)
from bridge.tool_packages.p0_10_claim_verifier.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS,
    ClaimVerifierVisualizationDataV1,
    FindingState,
    NumericCorrespondenceRecord,
    P010VisualizationArtifactSet,
    _check_category,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema


adapter_module = importlib.import_module(
    "bridge.tool_packages.p0_10_claim_verifier.adapter"
)
visualization_module = importlib.import_module(
    "bridge.tool_packages.p0_10_claim_verifier.visualization"
)


CREATED_AT = "2026-08-12T00:00:00Z"
EVIDENCE_REF = "evidence:" + "a" * 24 + "@1"
CLAIM_REF = "claim:synthetic-observation-count@1.0.0"
PRODUCT_CASE_REF = "product-case:synthetic-observation@1.0.0"


def _write(path: Path, payload: object) -> str:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_record(**changes: Any) -> EvidenceRecord:
    payload = {
        "evidence_id": "evidence:" + "a" * 24,
        "evidence_version": 1,
        "logical_key": "synthetic-observation-count",
        "content_hash": "b" * 64,
        "product_case_ref": {
            "object_id": "product-case:synthetic-observation",
            "object_version": "1.0.0",
        },
        "sample_or_preparation_ref": {
            "object_id": "report-source:synthetic-observation",
            "object_version": "1.0.0",
        },
        "domain_id": "target_identity",
        "measurement_result_ref": {
            "object_id": "measurement-result:observed-cell-count",
            "object_version": "1.0.0",
        },
        "measurement_spec_ref": {
            "object_id": "measurement-spec:observed-cell-count",
            "object_version": "1.0.0",
        },
        "metric_id": "observed-cell-count",
        "value": 42,
        "unit": "cells",
        "numerator": 42,
        "denominator": 42,
        "interval": {
            "lower": 42.0,
            "upper": 42.0,
            "confidence_level": None,
            "method_ref": None,
        },
        "claim_ref": {
            "object_id": "claim:synthetic-observation-count",
            "object_version": "1.0.0",
        },
        "biological_context": {
            "context_id": "context:synthetic-observation",
            "context_version": "1.0.0",
        },
        "relation": "supports",
        "evidence_state": "measured",
        "evidence_tier": "formal",
        "lifecycle_state": "active",
        "applicability": "applicable",
        "evidence_family_ref": {
            "object_id": "evidence-family:synthetic-observation",
            "object_version": "1.0.0",
        },
        "sufficiency_profile_ref": {
            "object_id": "evidence-sufficiency-profile:synthetic-observation",
            "object_version": "1.0.0",
        },
        "tool_run_ref": {
            "object_id": "tool-run:synthetic-observation",
            "object_version": "1.0.0",
        },
        "tool_run_execution_state": "succeeded",
        "reference_refs": [],
        "prior_refs": [],
        "artifact_refs": [],
        "provenance_refs": ["provenance:synthetic-observation"],
        "revision_action": "create",
        "predecessor_ref": None,
        "created_at": CREATED_AT,
        "compiler_version": "0.2.0",
    }
    payload.update(changes)
    return EvidenceRecord.model_validate(payload)


def _evidence_set(**record_changes: Any) -> EvidenceRecordSet:
    return EvidenceRecordSet(
        record_set_id="evidence-record-set:" + "c" * 16,
        record_set_version="0.1.0",
        graph_id="case-evidence-graph:" + "d" * 24,
        graph_version=1,
        records=[_evidence_record(**record_changes)],
        dispositions=[],
    )


def _graph_manifest(
    evidence_set: EvidenceRecordSet | None = None,
    *,
    backing_dir: Path | None = None,
) -> dict[str, Any]:
    evidence_set = evidence_set or _evidence_set()

    def artifact(filename: str, *, parquet: bool = False) -> dict[str, Any]:
        payload = b"PAR1synthetic-observation" if parquet else b"{}\n"
        if backing_dir is not None:
            (backing_dir / filename).write_bytes(payload)
        return {
            "filename": filename,
            "media_type": (
                "application/vnd.apache.parquet" if parquet else "application/json"
            ),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "row_count": 0 if parquet else None,
        }

    return {
        "graph_id": evidence_set.graph_id,
        "graph_version": evidence_set.graph_version,
        "canonicalization_id": "bridge-canonical-json/v0.1",
        "node_count": 1,
        "edge_count": 0,
        "object_counts": {"EvidenceRecord": 1},
        "source_input_hash": "f" * 64,
        "base_graph_ref": None,
        "evidence_records": artifact("evidence_records.json"),
        "evidence_requirements": artifact("evidence_requirements.json"),
        "reconciliation_records": artifact("reconciliation_records.json"),
        "graph_nodes": artifact("graph_nodes.parquet", parquet=True)
        | {"row_count": 1},
        "graph_edges": artifact("graph_edges.parquet", parquet=True),
        "created_at": CREATED_AT,
        "graph_kind": "case",
        "product_case_ref": {
            "object_id": "product-case:synthetic-observation",
            "object_version": "1.0.0",
        },
    }


@pytest.fixture(autouse=True)
def _validated_graph_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_graph(monkeypatch, _evidence_set())


def _stub_graph(
    monkeypatch: pytest.MonkeyPatch, evidence_set: EvidenceRecordSet
) -> None:
    monkeypatch.setattr(
        EvidenceGraphQueries,
        "open",
        classmethod(
            lambda cls, path: SimpleNamespace(evidence_record_set=evidence_set)
        ),
    )


def _policy() -> ClaimPolicySpec:
    return load_release_contract().claim_policy


def _statements() -> StatementRegistry:
    return load_release_contract().statement_registry


def _value_binding(
    text: str,
    rendered: str,
    *,
    binding_id: str = "observed-cell-count",
    source_field: str = "value",
    canonical: str = "42",
    raw_unit: str | None = "cells",
) -> dict[str, Any]:
    start = text.index(rendered)
    return {
        "binding_id": f"binding:{binding_id}",
        "source_evidence_ref": EVIDENCE_REF,
        "source_field": source_field,
        "canonical_numeric_string": canonical,
        "raw_unit": raw_unit,
        "text_span": (start, start + len(rendered)),
    }


def _report_payload(
    *,
    text: str = "observed-cell-count: 42 cells.",
    claim_type: str = "measurement_claim",
    reported_state: str | None = "measured",
    comparison_mode: str = "not_applicable",
    binding_changes: dict[str, Any] | None = None,
    statement_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    include_binding: bool = True,
    audience: str = "public_candidate",
) -> dict[str, Any]:
    claim_evidence = [EVIDENCE_REF] if evidence_refs is None else evidence_refs
    binding = None
    if claim_evidence and include_binding:
        rendered = "42 cells" if "42 cells" in text else "42"
        binding = _value_binding(text, rendered)
        binding.update(binding_changes or {})
    payload = {
        "object_version": "0.1.0",
        "report_id": "report:synthetic-observation",
        "report_version": "0.1.0",
        "content_hash": "0" * 64,
        "audience": audience,
        "language": "en",
        "evidence_record_set_ref": "evidence-record-set:" + "c" * 16 + "@0.1.0",
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
        "claim_blocks": [
            {
                "claim_id": "claim-block:observed-cell-count",
                "claim_version": "0.1.0",
                "claim_ref": CLAIM_REF,
                "product_case_ref": PRODUCT_CASE_REF,
                "claim_type": claim_type,
                "text": text,
                "language": "en",
                "evidence_refs": claim_evidence,
                "statement_refs": statement_refs or [],
                "value_bindings": [binding] if binding is not None else [],
                "reported_evidence_state": reported_state,
                "comparison_mode": comparison_mode,
                "authoring_channel": "deterministic_renderer",
            }
        ],
        "renderer_id": "BRIDGE-REPORT-DRAFT-RENDERER-v0.1",
        "renderer_version": "0.1.0",
        "authoring_channel": "deterministic_renderer",
        "created_at": CREATED_AT,
    }
    payload["content_hash"] = report_content_hash(payload)
    return payload


def _request(
    tmp_path: Path,
    *,
    report: dict[str, Any] | None = None,
    policy: ClaimPolicySpec | None = None,
    statements: StatementRegistry | None = None,
) -> ToolRequestV2:
    tmp_path.mkdir(parents=True, exist_ok=True)
    objects = [
        (
            "report",
            "report_draft",
            "bridge://schemas/report-draft/v0.1",
            report or _report_payload(),
            "0.1.0",
        ),
        (
            "evidence",
            "evidence_graph_manifest",
            "bridge://schemas/case-evidence-graph-manifest/v0.1",
            _graph_manifest(backing_dir=tmp_path),
            "1",
        ),
        (
            "policy",
            "claim_policy_spec",
            "bridge://schemas/claim-policy-spec/v0.1",
            (policy or _policy()).model_dump(mode="json"),
            "0.1.0",
        ),
        (
            "statements",
            "statement_registry",
            "bridge://schemas/statement-registry/v0.1",
            (statements or _statements()).model_dump(mode="json"),
            "0.1.0",
        ),
    ]
    refs: list[StructuredInputRef] = []
    for input_id, role, schema_ref, payload, version in objects:
        path = tmp_path / f"{input_id}.json"
        refs.append(
            StructuredInputRef(
                input_id=input_id,
                role=role,
                schema_ref=schema_ref,
                object_version=version,
                path=path,
                sha256=_write(path, payload),
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id="request-p0-10",
        tool_id="P0-10",
        tool_version="0.4.0",
        output_dir=tmp_path / "output",
        object_inputs=refs,
    )


def _spec() -> ToolPackageSpecV2:
    spec = ToolRegistry.load_default().describe("P0-10")
    assert isinstance(spec, ToolPackageSpecV2)
    return spec


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(schema_ref: str, model: type) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_runtime_validates_each_raw_input_with_jsonschema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    runtime_validator = adapter_module.Draft202012Validator

    class TrackingValidator:
        @classmethod
        def check_schema(cls, schema: dict[str, Any]) -> None:
            runtime_validator.check_schema(schema)

        def __init__(self, schema: dict[str, Any]) -> None:
            calls.append(schema["$id"])
            self.validator = runtime_validator(schema)

        def validate(self, payload: Any) -> None:
            self.validator.validate(payload)

    monkeypatch.setattr(
        adapter_module,
        "Draft202012Validator",
        TrackingValidator,
    )

    eligibility = adapter.check_eligibility(_request(tmp_path), _spec())

    assert eligibility.eligible
    assert sorted(calls) == sorted(
        schema_ref for schema_ref, _model in adapter_module.ROLE_MODELS.values()
    )


def test_receipt_binds_authority_and_matches_the_published_bytes(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["release_state"] == "verified"
    assert run.result["report_audience"] == "public_candidate"
    assert run.result["evidence_graph_id"] == "case-evidence-graph:" + "d" * 24
    assert run.result["evidence_graph_version"] == 1
    manifest_ref = next(
        ref for ref in request.object_inputs if ref.role == "evidence_graph_manifest"
    )
    assert run.result["evidence_graph_manifest_sha256"] == manifest_ref.sha256
    assert run.result["benchmark_id"] == EXTERNAL_BENCHMARK_ID
    assert run.result["benchmark_sha256"] == EXTERNAL_BENCHMARK_SHA256
    assert run.result["release_contract_id"] == load_release_contract().contract_id
    assert run.result["release_contract_sha256"] == release_contract_sha256()
    assert run.measurements == []
    assert len(run.artifacts) == 16
    artifact_bytes = next(
        artifact.path.read_bytes()
        for artifact in run.artifacts
        if artifact.kind == "claim_verification_result"
    )
    assert artifact_bytes == canonical_json_bytes(run.result, indent=2)
    result_artifact = next(
        artifact
        for artifact in run.artifacts
        if artifact.kind == "claim_verification_result"
    )
    assert hashlib.sha256(artifact_bytes).hexdigest() == result_artifact.sha256


def test_p0_11_can_reject_a_mutated_report_draft_from_the_p0_10_receipt(
    tmp_path: Path,
) -> None:
    payload = _report_payload()
    report = ReportDraft.model_validate(payload)
    run = adapter.run(_request(tmp_path, report=payload), _spec())
    receipt = ClaimVerificationResult.model_validate(run.result)

    assert receipt.matches_report_draft(report)
    for field, value in (
        ("text", "This synthetic claim reports: 42 cells."),
        ("claim_ref", "claim:replacement@1.0.0"),
        ("reported_evidence_state", "negative"),
        ("value_bindings", []),
    ):
        mutated = deepcopy(payload)
        mutated["claim_blocks"][0][field] = value
        mutated["content_hash"] = report_content_hash(mutated)
        assert not receipt.matches_report_draft(ReportDraft.model_validate(mutated))


def test_identical_inputs_reuse_byte_identical_result(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    second = adapter.run(request.model_copy(update={"request_id": "request-repeat"}), _spec())

    assert first.run_id == second.run_id
    assert first.input_hash == second.input_hash
    assert first.result == second.result
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"canonical_numeric_string": "41"}, "canonical_numeric_mismatch"),
        ({"raw_unit": "samples"}, "unit_mismatch"),
        ({"text_span": (0, 3)}, "rendered_numeric_mismatch"),
    ],
)
def test_numeric_mutations_are_hard_blockers(
    tmp_path: Path, changes: dict[str, Any], reason: str
) -> None:
    report = _report_payload(binding_changes=changes)
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["release_state"] == "release_blocked"
    assert reason in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_numeric_suffix_cannot_hide_an_extra_number(tmp_path: Path) -> None:
    text = "observed-cell-count: 42 cells999."
    start = text.index("42")
    report = _report_payload(
        text=text,
        binding_changes={"text_span": (start, start + len("42 cells999"))},
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert "rendered_numeric_mismatch" in {
        item["reason_code"] for item in run.result["check_records"]
    }


@pytest.mark.parametrize(
    ("token", "numeric", "canonical", "unit", "value"),
    [
        ("42cells", "42", "42", "cells", 42),
        ("42cell", "42", "42", "cells", 42),
        ("1e3cells", "1e3", "1000", "cells", 1000),
        ("42_cells", "42", "42", "cells", 42),
    ],
)
def test_noncanonical_numeric_text_cannot_bypass_complete_reconstruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    numeric: str,
    canonical: str,
    unit: str,
    value: int,
) -> None:
    text = f"observed-cell-count: {token}."
    _stub_graph(monkeypatch, _evidence_set(value=value, unit=unit))
    report = _report_payload(text=text, include_binding=False)
    report["claim_blocks"][0]["value_bindings"] = [
        _value_binding(
            text,
            numeric,
            canonical=canonical,
            raw_unit=unit,
        )
    ]
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    reasons = {item["reason_code"] for item in run.result["check_records"]}
    assert {"deterministic_claim_text_mismatch", "rendered_numeric_mismatch"} <= reasons
    assert run.result["release_state"] == "release_blocked"


@pytest.mark.parametrize("metric_id", ["SOX2_fraction", "CD8_fraction", "O2_level"])
def test_scientific_identifiers_are_not_misread_as_numeric_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metric_id: str,
) -> None:
    _stub_graph(monkeypatch, _evidence_set(metric_id=metric_id))
    report = _report_payload(text=f"{metric_id}: 42 cells.")

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "verified"
    assert run.result["check_records"] == []


def test_large_finite_integer_returns_a_typed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = 10**30
    _stub_graph(monkeypatch, _evidence_set(value=value))
    text = f"observed-cell-count: {value} cells."
    report = _report_payload(text=text, include_binding=False)
    report["claim_blocks"][0]["value_bindings"] = [
        _value_binding(text, f"{value} cells", canonical=str(value))
    ]
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["release_state"] == "verified"


def test_declared_renderer_cannot_author_extra_scientific_prose(tmp_path: Path) -> None:
    report = _report_payload(
        text=(
            "observed-cell-count: 42 cells. "
            "The cells produce dopamine."
        )
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert "deterministic_claim_text_mismatch" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_denominator_and_interval_values_use_separate_exact_spans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_graph(
        monkeypatch,
        _evidence_set(
            denominator=50,
            interval={
                "lower": 40,
                "upper": 44,
                "confidence_level": None,
                "method_ref": None,
            },
        ),
    )
    text = (
        "The value was 42 cells, denominator 50 cells, "
        "and interval 40 cells to 44 cells."
    )
    report = _report_payload(text=text)
    report["claim_blocks"][0]["value_bindings"] = [
        _value_binding(text, "42 cells"),
        _value_binding(
            text,
            "50 cells",
            binding_id="denominator",
            source_field="denominator",
            canonical="50",
        ),
        _value_binding(
            text,
            "40 cells",
            binding_id="interval-lower",
            source_field="interval_lower",
            canonical="40",
        ),
        _value_binding(
            text,
            "44 cells",
            binding_id="interval-upper",
            source_field="interval_upper",
            canonical="44",
        ),
    ]
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "review_required"
    assert not {
        "canonical_numeric_mismatch",
        "unit_mismatch",
        "rendered_numeric_mismatch",
    }.intersection(
        item["reason_code"] for item in run.result["check_records"]
    )


def test_extra_numeric_prose_fails_complete_reconstruction(tmp_path: Path) -> None:
    report = _report_payload(
        text="The first observation contains 42 cells and the second contains 42 cells."
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert "deterministic_claim_text_mismatch" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_overlapping_numeric_spans_are_rejected_by_the_report_schema() -> None:
    report = _report_payload()
    duplicate = dict(report["claim_blocks"][0]["value_bindings"][0])
    duplicate["binding_id"] = "binding:duplicate"
    report["claim_blocks"][0]["value_bindings"].append(duplicate)
    report["content_hash"] = report_content_hash(report)

    with pytest.raises(ValueError, match="must not overlap"):
        ReportDraft.model_validate(report)


@pytest.mark.parametrize(
    ("record_changes", "reason"),
    [
        (
            {
                "claim_ref": {
                    "object_id": "claim:unrelated-cell-state",
                    "object_version": "1.0.0",
                }
            },
            "claim_evidence_semantic_mismatch",
        ),
        (
            {
                "product_case_ref": {
                    "object_id": "product-case:other",
                    "object_version": "1.0.0",
                }
            },
            "product_case_evidence_mismatch",
        ),
    ],
)
def test_claim_and_product_targets_must_match_every_evidence_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_changes: dict[str, Any],
    reason: str,
) -> None:
    _stub_graph(monkeypatch, _evidence_set(**record_changes))

    run = adapter.run(_request(tmp_path), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert reason in {
        item["reason_code"] for item in run.result["check_records"]
    }


@pytest.mark.parametrize("channel", ["human_edit", "imported_draft"])
def test_human_or_imported_prose_requires_review(
    tmp_path: Path, channel: str
) -> None:
    report = _report_payload()
    report["authoring_channel"] = channel
    report["claim_blocks"][0]["authoring_channel"] = channel
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "review_required"
    assert run.result["public_export_eligibility"] == "ineligible"
    assert "non_deterministic_authoring_requires_review" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_unapproved_renderer_metadata_requires_review(tmp_path: Path) -> None:
    report = _report_payload()
    report["renderer_version"] = "caller-defined"
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "review_required"
    assert "unapproved_renderer_requires_review" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_unbound_number_and_evidence_state_substitution_block_release(tmp_path: Path) -> None:
    report = _report_payload(
        text="The sample contains 42 cells across 2 preparations.",
        reported_state="negative",
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())
    reasons = {
        item["reason_code"] for item in run.result["check_records"]
    }

    assert {"deterministic_claim_text_mismatch", "evidence_state_mismatch"} <= reasons
    assert run.result["release_state"] == "release_blocked"


def test_registered_boundary_statement_is_exact_exception(tmp_path: Path) -> None:
    report = _report_payload(
        text="This verification does not establish safety.",
        claim_type="policy_or_boundary_statement",
        reported_state=None,
        statement_refs=["statement:safety-boundary@0.1.0"],
        evidence_refs=[],
        audience="internal_research",
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "verified"


def test_public_boundary_statement_requires_formal_cited_evidence(
    tmp_path: Path,
) -> None:
    report = _report_payload(
        text="This verification does not establish safety.",
        claim_type="policy_or_boundary_statement",
        reported_state=None,
        statement_refs=["statement:safety-boundary@0.1.0"],
        evidence_refs=[],
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert "formal_evidence_required_for_public_candidate" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_distinct_missing_statements_emit_distinct_check_ids(tmp_path: Path) -> None:
    missing = ["statement:missing-a@0.1.0", "statement:missing-b@0.1.0"]
    report = _report_payload(
        text="This statement requires review.",
        claim_type="policy_or_boundary_statement",
        reported_state=None,
        statement_refs=missing,
        evidence_refs=[],
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    checks = [
        item
        for item in run.result["check_records"]
        if item["reason_code"] == "statement_ref_not_found"
    ]
    assert {item["statement_ref"] for item in checks} == set(missing)
    assert len({item["check_id"] for item in checks}) == 2


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("该样本含 42 个细胞，因此证明安全性。", "zh"),
        ("The sample contains 42 cells；这不能证明安全性。", "mixed"),
    ],
)
def test_bilingual_prohibited_claims_are_hard_blockers(
    tmp_path: Path, text: str, language: str
) -> None:
    report = _report_payload(text=text)
    report["language"] = language
    report["claim_blocks"][0]["language"] = language
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert "prohibited_claim" in {
        item["reason_code"]
        for item in run.result["check_records"]
    }


@pytest.mark.parametrize(
    "text",
    [
        "- The sample contains 42 cells.",
        "The *sample* contains 42 cells.",
        "The sample contains 42 cells. <img src=x onerror=alert(1)>",
    ],
)
def test_report_claims_reject_free_markup(text: str) -> None:
    with pytest.raises(ValueError, match="plain structured paragraph"):
        ReportDraft.model_validate(_report_payload(text=text))


def test_caller_numeric_transform_is_rejected_before_verification(
    tmp_path: Path,
) -> None:
    report = _report_payload(text="observed-cell-count: 4200 cells.")
    binding = report["claim_blocks"][0]["value_bindings"][0]
    binding["format_spec"] = {
        "decimal_places": 0,
        "scale": "percent",
        "rounding": "half_even",
    }
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None


def test_claim_text_cannot_execute_nested_template_syntax(tmp_path: Path) -> None:
    report = _report_payload(
        text="The {{ literal_template_text }} sample contains 42 cells."
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert "deterministic_claim_text_mismatch" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_report_cannot_self_declare_release_reviewer_authority(
    tmp_path: Path,
) -> None:
    report = _report_payload()
    report["human_review_decisions"] = [
        {
            "claim_id": "claim-block:observed-cell-count",
            "rule_id": "rule:ambiguous-superiority",
            "decision": "approved",
            "reviewer_role": "claim_reviewer",
            "reviewer_ref": "reviewer:self-declared",
            "reason": "caller supplied",
        }
    ]
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_descriptive_claim_cannot_use_inferential_language(tmp_path: Path) -> None:
    report = _report_payload(
        text="The result was statistically significant at 42 cells.",
        claim_type="descriptive_comparison",
        comparison_mode="descriptive_only",
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert "inferential_language_in_descriptive_claim" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_public_candidate_requires_formal_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_graph(monkeypatch, _evidence_set(evidence_tier="shadow"))

    run = adapter.run(_request(tmp_path), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert run.result["public_export_eligibility"] == "ineligible"
    assert "nonformal_evidence_used_for_formal_claim" in {
        item["reason_code"] for item in run.result["check_records"]
    }


def test_internal_report_with_shadow_evidence_stays_export_ineligible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_graph(monkeypatch, _evidence_set(evidence_tier="shadow"))
    report = _report_payload(audience="internal_research")

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "verified"
    assert run.result["report_audience"] == "internal_research"
    assert run.result["public_export_eligibility"] == "ineligible"


def test_report_cannot_downgrade_its_required_evidence_tier(tmp_path: Path) -> None:
    report = _report_payload()
    report["claim_blocks"][0]["intended_release_tier"] = "internal_candidate"
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_report_model_and_schema_reject_caller_release_authority() -> None:
    validator = Draft202012Validator(ReportDraft.model_json_schema())
    mutations = []

    numeric_transform = _report_payload()
    numeric_transform["claim_blocks"][0]["value_bindings"][0]["format_spec"] = {
        "scale": "percent"
    }
    mutations.append(numeric_transform)

    reviewer = _report_payload()
    reviewer["human_review_decisions"] = [{"reviewer_role": "claim_reviewer"}]
    mutations.append(reviewer)

    release_tier = _report_payload()
    release_tier["claim_blocks"][0]["intended_release_tier"] = "internal_candidate"
    mutations.append(release_tier)

    invalid_numeric = _report_payload()
    invalid_numeric["claim_blocks"][0]["value_bindings"][0][
        "canonical_numeric_string"
    ] = "NaN"
    mutations.append(invalid_numeric)

    for payload in mutations:
        payload["content_hash"] = report_content_hash(payload)
        with pytest.raises(ValueError):
            ReportDraft.model_validate(payload)
        with pytest.raises(JSONSchemaValidationError):
            validator.validate(payload)


def test_caller_cannot_replace_the_approved_claim_policy(tmp_path: Path) -> None:
    payload = _policy().model_dump(mode="json")
    payload["text_rules"] = []
    policy = ClaimPolicySpec.model_validate(payload)
    report = _report_payload(
        text="observed-cell-count: 42 cells; this proves safety."
    )

    run = adapter.run(_request(tmp_path, report=report, policy=policy), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["claim_policy_not_approved"]
    assert run.result is None


def test_caller_cannot_replace_the_approved_statement_registry(tmp_path: Path) -> None:
    payload = _statements().model_dump(mode="json")
    payload["statements"][0]["approved"] = False
    statements = StatementRegistry.model_validate(payload)

    run = adapter.run(_request(tmp_path, statements=statements), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["statement_registry_not_approved"]
    assert run.result is None


def test_report_hash_mismatch_fails_before_verification(tmp_path: Path) -> None:
    report = _report_payload()
    report["content_hash"] = "f" * 64
    request = _request(tmp_path, report=report)

    eligibility = adapter.check_eligibility(request, _spec())

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["structured_input_schema_invalid"]


def test_removed_review_metadata_fails_without_echoing_the_value(tmp_path: Path) -> None:
    private_value = "/" + "data1/example/private/reviewer.txt"
    report = _report_payload()
    report["human_review_decisions"] = [
        {
            "claim_id": "claim-block:observed-cell-count",
            "rule_id": "rule:ambiguous-superiority",
            "decision": "approved",
            "reviewer_role": "claim_reviewer",
            "reviewer_ref": private_value,
            "reason": "caller supplied",
        }
    ]
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None
    assert private_value not in json.dumps(run.model_dump(mode="json"))


def test_invalid_p0_09_graph_is_a_typed_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_graph(cls: type, path: Path) -> None:
        raise ValueError("manifest_integrity_failed")

    monkeypatch.setattr(
        EvidenceGraphQueries,
        "open",
        classmethod(reject_graph),
    )

    run = adapter.run(_request(tmp_path), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["evidence_graph_integrity_failed"]
    assert run.result is None


def test_direct_and_registry_v1_runs_return_typed_failures(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="legacy-p0-10",
        tool_id="P0-10",
        output_dir=(tmp_path / "out").resolve(),
    )

    direct = adapter.run(request, _spec())
    registered = ToolRegistry.load_default().run(request)

    assert direct.execution_state is ExecutionState.FAILED
    assert direct.reason_codes == ["tool_request_v2_required"]
    assert direct.request.object_inputs == []
    assert direct.result is None and direct.artifacts == []
    assert registered.execution_state is ExecutionState.FAILED
    assert registered.reason_codes == ["tool_request_v2_required"]


def test_post_publication_replacement_is_a_typed_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish = adapter_module._publish_bundle

    def replace_after_publish(**kwargs: Any) -> dict[str, Path]:
        paths = publish(**kwargs)
        paths["claim_verification_result.json"].write_bytes(
            b'{"replacement":true}\n'
        )
        return paths

    monkeypatch.setattr(adapter_module, "_publish_bundle", replace_after_publish)

    run = adapter.run(_request(tmp_path), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["published_bundle_hash_mismatch"]
    assert run.result is None and run.artifacts == []


@pytest.mark.parametrize("target", ["missing-target", "output"])
def test_broken_or_self_referential_output_symlink_is_typed(
    tmp_path: Path, target: str
) -> None:
    request = _request(tmp_path)
    request.output_dir.symlink_to(target, target_is_directory=True)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_dir_not_regular_directory"]


def test_existing_run_symlink_fails_without_following_it(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    final = first.artifacts[0].path.parent
    shutil.rmtree(final)
    final.symlink_to(final.name, target_is_directory=True)

    second = adapter.run(request, _spec())

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


def test_existing_result_drift_fails_without_overwrite(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    first.artifacts[0].path.write_text("{}\n", encoding="utf-8")

    second = adapter.run(request, _spec())

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


def test_receipt_model_and_public_schema_reject_impossible_combinations(
    tmp_path: Path,
) -> None:
    valid = adapter.run(_request(tmp_path / "valid"), _spec()).result
    assert valid is not None
    ClaimVerificationResult.model_validate(valid)
    validator = Draft202012Validator(ClaimVerificationResult.model_json_schema())
    assert list(validator.iter_errors(valid)) == []

    blocked = adapter.run(
        _request(
            tmp_path / "blocked",
            report=_report_payload(
                text="observed-cell-count: 42 cells; this proves safety."
            ),
        ),
        _spec(),
    ).result
    assert blocked is not None
    blocked_check = next(
        item
        for item in blocked["check_records"]
        if item["outcome"] == "blocked"
    )

    impossible: list[dict[str, Any]] = []
    state_mismatch = deepcopy(valid)
    state_mismatch["check_records"] = [blocked_check]
    impossible.append(state_mismatch)

    inconsistent_check = deepcopy(blocked)
    inconsistent_check["check_records"] = [
        blocked_check | {"severity": "review"}
    ]
    impossible.append(inconsistent_check)

    duplicate_check = deepcopy(blocked)
    duplicate_check["check_records"] = [blocked_check, deepcopy(blocked_check)]
    impossible.append(duplicate_check)

    duplicate_benchmark = deepcopy(valid)
    duplicate_benchmark["benchmark_id"] = "caller-benchmark"
    duplicate_benchmark["benchmark_sha256"] = "0" * 64
    impossible.append(duplicate_benchmark)

    wrong_benchmark_receipt = deepcopy(valid)
    wrong_benchmark_receipt["benchmark_sha256"] = "0" * 64
    impossible.append(wrong_benchmark_receipt)

    wrong_release_receipt = deepcopy(valid)
    wrong_release_receipt["release_contract_sha256"] = "0" * 64
    impossible.append(wrong_release_receipt)

    internal = adapter.run(
        _request(
            tmp_path / "internal",
            report=_report_payload(audience="internal_research"),
        ),
        _spec(),
    ).result
    assert internal is not None
    export_promotion = deepcopy(internal)
    export_promotion["public_export_eligibility"] = "eligible"
    impossible.append(export_promotion)

    lossy_report_copy = deepcopy(valid)
    lossy_report_copy["verified_report"] = {
        "text": "This product is clinically safe.",
        "claim_ref": "not-versioned",
        "product_case_ref": "/private/case",
    }
    impossible.append(lossy_report_copy)

    for payload in impossible:
        with pytest.raises(ValueError):
            ClaimVerificationResult.model_validate(payload)
        with pytest.raises(JSONSchemaValidationError):
            validator.validate(payload)


def test_registry_exposes_p0_10_as_v2_candidate() -> None:
    spec = _spec()

    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.input_schema_ref == "bridge://schemas/tool-request/v0.2"
    assert spec.result_schema_ref == "bridge://schemas/claim-verification-result/v0.1"


def _visualization_artifact_set(run) -> P010VisualizationArtifactSet:
    artifact = next(
        item for item in run.artifacts if item.kind == "visualization_artifact_set"
    )
    return P010VisualizationArtifactSet.model_validate_json(artifact.path.read_bytes())


def _visualization_profile(run) -> ClaimVerifierVisualizationDataV1:
    artifact = next(
        item
        for item in run.artifacts
        if item.kind == "claim_verifier_visualization_data"
    )
    return ClaimVerifierVisualizationDataV1.model_validate_json(
        artifact.path.read_bytes()
    )


@pytest.mark.parametrize(
    "schema_ref,model",
    {**PUBLIC_SCHEMA_MODELS, **PUBLIC_VISUALIZATION_SCHEMA_MODELS}.items(),
)
def test_public_schema_files_are_exact_draft_2020_12_exports(
    schema_ref: str, model: type
) -> None:
    expected = model.model_json_schema()
    expected["$id"] = schema_ref
    actual = load_schema(schema_ref)

    Draft202012Validator.check_schema(actual)
    assert actual == expected
    if schema_ref == "bridge://schemas/claim-verification-result/v0.1":
        assert {"benchmark_id", "benchmark_sha256"} <= set(actual["required"])
        assert "default" not in actual["properties"]["benchmark_id"]
        assert "default" not in actual["properties"]["benchmark_sha256"]


def test_unregistered_claim_check_rule_is_not_silently_categorized() -> None:
    check = ClaimCheckRecord(
        check_id="check:" + "1" * 16,
        claim_id="claim-block:synthetic-observation",
        rule_id="rule:new-unregistered-rule",
        rule_version="0.1.0",
        outcome=CheckOutcome.WARNING,
        severity=CheckSeverity.WARNING,
        reason_code="synthetic_reason",
    )

    with pytest.raises(ValueError, match="unregistered claim-check rule"):
        _check_category(check)


def test_every_current_verifier_rule_has_an_explicit_visualization_category() -> None:
    static_rule_ids = {
        "rule:case-scope",
        "rule:claim-scope",
        "rule:claim-type-policy",
        "rule:comparison-contract",
        "rule:comparison-mode",
        "rule:descriptive-scope",
        "rule:deterministic-authoring",
        "rule:evidence-applicability",
        "rule:evidence-binding",
        "rule:evidence-lifecycle",
        "rule:evidence-state",
        "rule:evidence-state-policy",
        "rule:evidence-tier",
        "rule:numeric-fidelity",
        "rule:statement-binding",
        "rule:statement-text",
        "rule:value-binding",
    }
    policy_rule_ids = {rule.rule_id for rule in _policy().text_rules}
    for index, rule_id in enumerate(sorted(static_rule_ids | policy_rule_ids), start=1):
        check = ClaimCheckRecord(
            check_id=f"check:{index:016x}",
            claim_id="claim-block:synthetic-observation",
            rule_id=rule_id,
            rule_version="0.1.0",
            outcome=CheckOutcome.WARNING,
            severity=CheckSeverity.WARNING,
            reason_code="synthetic_reason",
        )
        _check_category(check)


def test_renderer_uses_redundant_status_symbols_and_readable_finding_labels() -> None:
    assert visualization_module._finding_symbol(FindingState.NO_FINDING, 0) == "—"
    assert visualization_module._finding_symbol(FindingState.WARNING, 2) == "! 2"
    assert visualization_module._finding_symbol(FindingState.REVIEW_REQUIRED, 1) == "? 1"
    assert visualization_module._finding_symbol(FindingState.BLOCKED, 3) == "× 3"
    assert (
        visualization_module._human_label("canonical_numeric_mismatch")
        == "Canonical numeric mismatch"
    )


def test_visualization_bundle_conserves_artifacts_and_typed_data_binding(
    tmp_path: Path,
) -> None:
    run = adapter.run(_request(tmp_path), _spec())
    final = run.request.output_dir / run.run_id
    manifest = json.loads((final / "artifact_manifest.json").read_text())
    artifact_set = _visualization_artifact_set(run)
    data_artifact = next(
        item
        for item in run.artifacts
        if item.kind == "claim_verifier_visualization_data"
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert len(run.artifacts) == 16
    assert len(manifest["artifacts"]) == 15
    assert len({item["filename"] for item in manifest["artifacts"]}) == 15
    assert {item["filename"] for item in manifest["artifacts"]} == {
        path.name
        for path in final.iterdir()
        if path.name != "artifact_manifest.json"
    }
    assert sum(item.kind == "visualization_table" for item in run.artifacts) == 3
    assert sum(item.kind == "visualization_render" for item in run.artifacts) == 9
    assert artifact_set.data_profile_artifact_id == data_artifact.artifact_id
    assert artifact_set.data_profile_sha256 == data_artifact.sha256
    assert len(artifact_set.visualizations) == 3
    artifact_ids = {item.artifact_id for item in run.artifacts}
    for visualization in artifact_set.visualizations:
        assert visualization.data_binding.artifact_id == data_artifact.artifact_id
        assert visualization.data_binding.sha256 == data_artifact.sha256
        assert visualization.accessibility.data_sha256 == data_artifact.sha256
        assert visualization.accessibility.table_artifact_id in artifact_ids
        assert len(visualization.renders) == 3
        assert {render.media_type for render in visualization.renders} == {
            "image/svg+xml",
            "image/png",
            "application/pdf",
        }
        assert all(
            render.artifact_id in artifact_ids
            and render.data_sha256 == data_artifact.sha256
            for render in visualization.renders
        )

    serialized_manifest = json.dumps(manifest, sort_keys=True)
    assert all("input_id" not in item for item in manifest["structured_inputs"])
    assert str(tmp_path) not in serialized_manifest
    assert not any(
        prefix in serialized_manifest
        for prefix in ("/data", "/home/", "/Users/", "/private/")
    )


def test_exact_rerun_reuses_every_artifact_byte(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    before = {
        item.path.name: (item.sha256, item.path.read_bytes())
        for item in first.artifacts
    }

    second = adapter.run(
        request.model_copy(update={"request_id": "request-byte-rerun"}),
        _spec(),
    )
    after = {
        item.path.name: (item.sha256, item.path.read_bytes())
        for item in second.artifacts
    }

    assert first.run_id == second.run_id
    assert before == after


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("_FONT_RELATIVE_PATH", Path("fonts/missing-cjk-font.ttf")),
        ("_FONT_SHA256", "0" * 64),
        ("_FONT_FAMILY", "Synthetic Missing Family"),
    ],
)
def test_font_contract_failures_publish_no_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    value: object,
) -> None:
    monkeypatch.setattr(visualization_module, attribute, value)
    request = _request(tmp_path)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["visualization_font_unavailable"]
    assert run.result is None and run.artifacts == []
    assert not (request.output_dir / run.run_id).exists()


def test_cjk_claim_context_is_rendered_with_the_declared_font(
    tmp_path: Path,
) -> None:
    text = "样本含 42 cells；该表述需要人工复核。"
    report = _report_payload(text=text)
    report["language"] = "zh"
    report["authoring_channel"] = "human_edit"
    report["claim_blocks"][0]["language"] = "zh"
    report["claim_blocks"][0]["authoring_channel"] = "human_edit"
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())
    profile_artifact = next(
        item
        for item in run.artifacts
        if item.kind == "claim_verifier_visualization_data"
    )
    profile = ClaimVerifierVisualizationDataV1.model_validate_json(
        profile_artifact.path.read_bytes()
    )
    renders = {
        item.path.suffix: item.path.read_bytes()
        for item in run.artifacts
        if item.kind == "visualization_render"
        and "finding-context" in item.path.name
    }

    assert any(row.claim_text == text for row in profile.finding_records)
    assert renders[".png"].startswith(b"\x89PNG")
    assert renders[".pdf"].startswith(b"%PDF")
    assert b"<path" in renders[".svg"]


def test_input_change_during_atomic_publication_leaves_no_run_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(adapter_module, "_inputs_unchanged", lambda _refs: False)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_modified_during_run"]
    assert run.result is None and run.artifacts == []
    assert not (request.output_dir / run.run_id).exists()


def test_oversized_matrix_uses_complete_table_without_top_n(
    tmp_path: Path,
) -> None:
    report = _report_payload()
    template = report["claim_blocks"][0]
    report["claim_blocks"] = []
    for index in range(25):
        claim = deepcopy(template)
        claim["claim_id"] = f"claim-block:synthetic-{index:03d}"
        claim["value_bindings"][0]["binding_id"] = f"binding:count-{index:03d}"
        report["claim_blocks"].append(claim)
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())
    profile_artifact = next(
        item
        for item in run.artifacts
        if item.kind == "claim_verifier_visualization_data"
    )
    profile = ClaimVerifierVisualizationDataV1.model_validate_json(
        profile_artifact.path.read_bytes()
    )
    artifact_set = _visualization_artifact_set(run)
    matrix = next(
        item
        for item in artifact_set.visualizations
        if item.component_id.endswith("claim-check-matrix")
    )
    table = next(
        item
        for item in run.artifacts
        if item.artifact_id == matrix.accessibility.table_artifact_id
    )
    rows = list(csv.DictReader(StringIO(table.path.read_text()), delimiter="\t"))

    assert profile.claim_count == 25
    assert len(profile.check_matrix_records) == 26
    assert len(rows) == 26
    assert "static_render_requires_complete_table_fallback" in (
        matrix.missing_reason_codes
    )


def test_long_finding_context_uses_complete_table_without_text_truncation(
    tmp_path: Path,
) -> None:
    text = "observed-cell-count: 42 cells. " + "Detailed context " * 45
    report = _report_payload(text=text)
    report["authoring_channel"] = "human_edit"
    report["claim_blocks"][0]["authoring_channel"] = "human_edit"
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())
    artifact_set = _visualization_artifact_set(run)
    finding = next(
        item
        for item in artifact_set.visualizations
        if item.component_id.endswith("finding-context")
    )
    table = next(
        item
        for item in run.artifacts
        if item.artifact_id == finding.accessibility.table_artifact_id
    )
    rows = list(csv.DictReader(StringIO(table.path.read_text()), delimiter="\t"))

    assert rows
    assert all(row["claim_text"] == text for row in rows)
    assert "static_render_requires_complete_table_fallback" in (
        finding.missing_reason_codes
    )


def test_result_schema_bytes_remain_v01_compatible() -> None:
    schema_path = (
        Path(adapter_module.__file__).resolve().parents[2]
        / "resources/schemas/claim_verification_result.schema.json"
    )

    assert hashlib.sha256(schema_path.read_bytes()).hexdigest() == (
        "41e160b47e1a5a23a41355ff52256a0bc2e63d4a60e66a5dbd4b66c1dece402d"
    )


def test_visualization_records_preserve_normal_and_mismatch_semantics(
    tmp_path: Path,
) -> None:
    normal = adapter.run(_request(tmp_path / "normal"), _spec())
    normal_profile = ClaimVerifierVisualizationDataV1.model_validate_json(
        next(
            item
            for item in normal.artifacts
            if item.kind == "claim_verifier_visualization_data"
        ).path.read_bytes()
    )
    report_rows = [
        row
        for row in normal_profile.check_matrix_records
        if row.record_kind == "report_check_matrix"
    ]
    claim_rows = [
        row
        for row in normal_profile.check_matrix_records
        if row.record_kind == "claim_check_matrix"
    ]

    assert len(report_rows) == 1
    assert len(report_rows[0].checks) == 4
    assert len(claim_rows) == 1
    assert len(claim_rows[0].categories) == 5
    assert len(normal_profile.numeric_records) == 1
    assert (
        normal_profile.numeric_records[0].correspondence_state.value
        == "exact_identity_under_current_rules"
    )
    assert normal_profile.finding_records == []

    report = _report_payload(binding_changes={"canonical_numeric_string": "41"})
    mismatch = adapter.run(
        _request(tmp_path / "mismatch", report=report),
        _spec(),
    )
    mismatch_profile = ClaimVerifierVisualizationDataV1.model_validate_json(
        next(
            item
            for item in mismatch.artifacts
            if item.kind == "claim_verifier_visualization_data"
        ).path.read_bytes()
    )
    numeric = mismatch_profile.numeric_records[0]
    finding_by_id = {
        row.check_id: row for row in mismatch_profile.finding_records
    }
    start, end = report["claim_blocks"][0]["value_bindings"][0]["text_span"]

    assert numeric.check_ids
    assert set(numeric.check_ids) <= set(finding_by_id)
    for check_id in numeric.check_ids:
        finding = finding_by_id[check_id]
        assert finding.record_kind == "span_finding_context"
        assert (finding.span_start, finding.span_end) == (start, end)
        assert finding.matched_text == report["claim_blocks"][0]["text"][start:end]


def test_component_artifacts_use_only_records_path_evidence_lineage(
    tmp_path: Path,
) -> None:
    reports = [_report_payload()]
    boundary = _report_payload(
        text="This verification does not establish safety.",
        claim_type="policy_or_boundary_statement",
        reported_state=None,
        statement_refs=["statement:safety-boundary@0.1.0"],
        evidence_refs=[],
        audience="internal_research",
    )
    reports.append(boundary)

    for index, report in enumerate(reports):
        run = adapter.run(
            _request(tmp_path / f"case-{index}", report=report),
            _spec(),
        )
        profile = ClaimVerifierVisualizationDataV1.model_validate_json(
            next(
                item
                for item in run.artifacts
                if item.kind == "claim_verifier_visualization_data"
            ).path.read_bytes()
        )
        artifact_set = _visualization_artifact_set(run)
        artifacts = {item.artifact_id: item for item in run.artifacts}

        for visualization in artifact_set.visualizations:
            records = getattr(profile, visualization.data_binding.records_path)
            expected = (
                sorted(
                    {
                        evidence_id
                        for record in records
                        for evidence_id in record.evidence_ids
                    }
                )
                if records
                else [profile.source_result_ref]
            )
            assert visualization.evidence_ids == expected
            linked_ids = {
                visualization.accessibility.table_artifact_id,
                *(render.artifact_id for render in visualization.renders),
            }
            assert all(artifacts[item].evidence_ids == expected for item in linked_ids)


def test_backing_graph_change_during_publication_leaves_no_run_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    publish = adapter_module._publish_bundle

    def mutate_backing_artifact(**kwargs: Any):
        (tmp_path / "evidence_records.json").write_bytes(b"{\"changed\":true}\n")
        return publish(**kwargs)

    monkeypatch.setattr(
        adapter_module,
        "_publish_bundle",
        mutate_backing_artifact,
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_modified_during_run"]
    assert run.result is None and run.artifacts == []
    assert not (request.output_dir / run.run_id).exists()


def test_typed_visualization_rejects_cross_record_identity_mutations(
    tmp_path: Path,
) -> None:
    normal = _visualization_profile(
        adapter.run(_request(tmp_path / "normal"), _spec())
    ).model_dump(mode="json")
    mismatch_report = _report_payload(
        binding_changes={"canonical_numeric_string": "41"}
    )
    mismatch = _visualization_profile(
        adapter.run(
            _request(tmp_path / "mismatch", report=mismatch_report),
            _spec(),
        )
    ).model_dump(mode="json")

    ghost_claim = deepcopy(normal)
    ghost_claim["numeric_records"][0]["claim_id"] = "claim-block:ghost"

    wrong_span = deepcopy(mismatch)
    wrong_span["numeric_records"][0]["span_end"] += 1
    wrong_span["numeric_records"][0]["report_rendered_text"] += "."

    duplicate_binding = deepcopy(normal)
    duplicate_row = deepcopy(duplicate_binding["numeric_records"][0])
    duplicate_row["record_id"] = "numeric.002"
    duplicate_binding["numeric_records"].append(duplicate_row)
    duplicate_binding["binding_count"] = 2

    wrong_check = deepcopy(mismatch)
    wrong_check["numeric_records"][0]["check_ids"] = ["check:" + "f" * 16]

    wrong_report = deepcopy(normal)
    wrong_report["check_matrix_records"][0]["report_draft_ref"] = (
        "report:unbound@0.1.0"
    )

    for payload in (
        ghost_claim,
        wrong_span,
        duplicate_binding,
        wrong_check,
        wrong_report,
    ):
        with pytest.raises(ValueError):
            ClaimVerifierVisualizationDataV1.model_validate(payload)


def test_typed_visualization_rejects_incoherent_state_axes(
    tmp_path: Path,
) -> None:
    profile = _visualization_profile(
        adapter.run(_request(tmp_path), _spec())
    ).model_dump(mode="json")

    no_finding_alert = deepcopy(profile)
    no_finding_alert["check_matrix_records"][1]["evidence_state"] = "alert"
    with pytest.raises(ValueError):
        ClaimVerifierVisualizationDataV1.model_validate(no_finding_alert)

    fake_unit_mismatch = deepcopy(profile["numeric_records"][0])
    fake_unit_mismatch.update(
        {
            "correspondence_state": "unit_mismatch",
            "display_state": "unit_mismatch",
            "evidence_state": "alert",
            "reason_codes": ["unit_mismatch"],
            "check_ids": ["check:" + "e" * 16],
        }
    )
    with pytest.raises(ValueError, match="different units"):
        NumericCorrespondenceRecord.model_validate(fake_unit_mismatch)


def test_numeric_unavailable_and_uncited_axes_preserve_missingness(
    tmp_path: Path,
) -> None:
    exact = _visualization_profile(
        adapter.run(_request(tmp_path), _spec())
    ).numeric_records[0].model_dump(mode="json")

    absent_record = deepcopy(exact)
    absent_record.update(
        {
            "evidence_canonical_numeric_string": None,
            "evidence_unit": None,
            "correspondence_state": "source_numeric_unavailable",
            "display_state": "source_numeric_unavailable",
            "evidence_state": "unavailable",
            "missingness": "unavailable",
            "applicability": "not_assessed",
            "reason_codes": ["source_evidence_record_unavailable"],
            "check_ids": [],
        }
    )
    NumericCorrespondenceRecord.model_validate(absent_record)

    empty_source_field = deepcopy(absent_record)
    empty_source_field.update(
        {
            "reason_codes": ["numeric_source_unavailable"],
            "check_ids": ["check:" + "d" * 16],
        }
    )
    NumericCorrespondenceRecord.model_validate(empty_source_field)

    for evidence_value, missingness in (("42", "available"), (None, "unavailable")):
        uncited = deepcopy(exact)
        uncited.update(
            {
                "citation_state": "not_cited",
                "evidence_canonical_numeric_string": evidence_value,
                "correspondence_state": "source_not_cited_numeric_not_assessed",
                "display_state": "source_not_cited_numeric_not_assessed",
                "evidence_state": "alert",
                "missingness": missingness,
                "applicability": "not_assessed",
                "reason_codes": ["binding_evidence_not_cited"],
                "check_ids": ["check:" + "c" * 16],
            }
        )
        NumericCorrespondenceRecord.model_validate(uncited)


def test_visualization_artifact_set_rejects_incomplete_or_aliased_artifacts(
    tmp_path: Path,
) -> None:
    artifact_set = _visualization_artifact_set(
        adapter.run(_request(tmp_path), _spec())
    ).model_dump(mode="json")

    truncated = deepcopy(artifact_set)
    truncated["visualizations"][0]["renders"].pop()

    duplicate_table = deepcopy(artifact_set)
    duplicate_table["visualizations"][1]["accessibility"]["table_artifact_id"] = (
        duplicate_table["visualizations"][0]["accessibility"]["table_artifact_id"]
    )

    duplicate_render = deepcopy(artifact_set)
    duplicate_render["visualizations"][1]["renders"][0]["artifact_id"] = (
        duplicate_render["visualizations"][0]["renders"][0]["artifact_id"]
    )

    for payload in (truncated, duplicate_table, duplicate_render):
        with pytest.raises(ValueError):
            P010VisualizationArtifactSet.model_validate(payload)


def test_typed_visualization_recomputes_categories_text_and_record_lineage(
    tmp_path: Path,
) -> None:
    report = _report_payload(binding_changes={"canonical_numeric_string": "41"})
    profile = _visualization_profile(
        adapter.run(_request(tmp_path, report=report), _spec())
    ).model_dump(mode="json")
    claim = profile["check_matrix_records"][1]
    finding = profile["finding_records"][0]

    wrong_category = deepcopy(profile)
    cells = {
        cell["category"]: cell
        for cell in wrong_category["check_matrix_records"][1]["categories"]
    }
    check_id = cells["numeric_and_unit"]["check_ids"][0]
    cells["numeric_and_unit"].update(
        {
            "finding_state": "no_finding_under_current_rules",
            "finding_count": 0,
            "check_ids": [],
        }
    )
    cells["wording_and_statements"].update(
        {
            "finding_state": "blocking_finding",
            "finding_count": 1,
            "check_ids": [check_id],
        }
    )

    extra_binding = deepcopy(profile)
    extra_ref = "evidence:" + "b" * 24 + "@1"
    extra_id = extra_ref.split("@", 1)[0]
    extra_claim = extra_binding["check_matrix_records"][1]
    extra_claim["binding_source_refs"].append(extra_ref)
    extra_claim["evidence_ids"] = sorted({*extra_claim["evidence_ids"], extra_id})
    extra_binding["source_evidence_refs"].append(extra_ref)
    extra_binding["source_evidence_refs"].sort()
    extra_binding["evidence_ids"] = sorted({*extra_binding["evidence_ids"], extra_id})

    wrong_type = deepcopy(profile)
    wrong_type["finding_records"][0]["claim_type"] = "availability_claim"

    wrong_text = deepcopy(profile)
    wrong_text["finding_records"][0]["claim_text"] += " "

    wrong_numeric_text = deepcopy(profile)
    wrong_numeric_text["numeric_records"][0]["report_rendered_text"] = "41 cells"

    wrong_lineage = deepcopy(profile)
    ghost_id = "evidence:" + "e" * 24
    wrong_lineage["finding_records"][0]["evidence_ids"] = sorted(
        {*finding["evidence_ids"], ghost_id}
    )
    wrong_lineage["evidence_ids"] = sorted(
        {*wrong_lineage["evidence_ids"], ghost_id}
    )

    assert claim["claim_text"] == report["claim_blocks"][0]["text"]
    for payload in (
        wrong_category,
        extra_binding,
        wrong_type,
        wrong_text,
        wrong_numeric_text,
        wrong_lineage,
    ):
        with pytest.raises(ValueError):
            ClaimVerifierVisualizationDataV1.model_validate(payload)


def test_artifact_set_closes_global_ids_and_producer_identity(tmp_path: Path) -> None:
    artifact_set = _visualization_artifact_set(
        adapter.run(_request(tmp_path), _spec())
    ).model_dump(mode="json")

    data_as_table = deepcopy(artifact_set)
    data_as_table["visualizations"][0]["accessibility"]["table_artifact_id"] = (
        data_as_table["data_profile_artifact_id"]
    )

    producer_drift = deepcopy(artifact_set)
    producer_drift["visualizations"][1]["producer_tool_version"] = "9.9.9"

    digest_drift = deepcopy(artifact_set)
    digest_drift["artifact_set_id"] = "p0-10-visualizations:" + "f" * 16

    for payload in (data_as_table, producer_drift, digest_drift):
        with pytest.raises(ValueError):
            P010VisualizationArtifactSet.model_validate(payload)


def test_visualization_profile_rejects_run_and_source_digest_drift(
    tmp_path: Path,
) -> None:
    profile = _visualization_profile(
        adapter.run(_request(tmp_path), _spec())
    ).model_dump(mode="json")
    other_digest = "f" * 16

    profile_id_drift = deepcopy(profile)
    profile_id_drift["visualization_profile_id"] = (
        f"claim-verifier-visualization:{other_digest}"
    )
    producer_drift = deepcopy(profile)
    producer_drift["producer_run_ref"] = f"run:run-{other_digest}"
    source_drift = deepcopy(profile)
    source_drift["source_result_ref"] = f"claim-verification:{other_digest}"

    for payload in (profile_id_drift, producer_drift, source_drift):
        with pytest.raises(ValueError, match="digests must agree"):
            ClaimVerifierVisualizationDataV1.model_validate(payload)


def test_artifact_set_rejects_component_naming_and_records_path_drift(
    tmp_path: Path,
) -> None:
    artifact_set = _visualization_artifact_set(
        adapter.run(_request(tmp_path), _spec())
    ).model_dump(mode="json")
    digest = artifact_set["artifact_set_id"].rsplit(":", 1)[1]

    records_path_drift = deepcopy(artifact_set)
    records_path_drift["visualizations"][0]["data_binding"]["records_path"] = (
        "numeric_records"
    )

    table_swap = deepcopy(artifact_set)
    first_table = table_swap["visualizations"][0]["accessibility"]
    second_table = table_swap["visualizations"][1]["accessibility"]
    first_table["table_artifact_id"], second_table["table_artifact_id"] = (
        second_table["table_artifact_id"],
        first_table["table_artifact_id"],
    )

    render_swap = deepcopy(artifact_set)
    first_render = render_swap["visualizations"][0]["renders"][0]
    second_render = render_swap["visualizations"][1]["renders"][0]
    first_render["artifact_id"], second_render["artifact_id"] = (
        second_render["artifact_id"],
        first_render["artifact_id"],
    )

    visualization_id_drift = deepcopy(artifact_set)
    visualization_id_drift["visualizations"][0]["visualization_id"] = (
        f"visualization:run-{digest}:claim-check-matrix-drift"
    )

    for payload in (
        records_path_drift,
        table_swap,
        render_swap,
        visualization_id_drift,
    ):
        with pytest.raises(ValueError):
            P010VisualizationArtifactSet.model_validate(payload)


def test_empty_and_capacity_figures_do_not_repeat_status_or_limitation_text(
    tmp_path: Path,
) -> None:
    normal = _visualization_profile(
        adapter.run(_request(tmp_path / "normal"), _spec())
    )
    boundary_report = _report_payload(
        text="This verification does not establish safety.",
        claim_type="policy_or_boundary_statement",
        reported_state=None,
        statement_refs=["statement:safety-boundary@0.1.0"],
        evidence_refs=[],
        include_binding=False,
        audience="internal_research",
    )
    boundary = _visualization_profile(
        adapter.run(
            _request(tmp_path / "boundary", report=boundary_report),
            _spec(),
        )
    )
    fallback_reason = "static_render_requires_complete_table_fallback"
    cases = (
        (
            visualization_module._render_numeric_correspondence(boundary),
            "No numeric ValueBinding is present in this structured report.",
            "No numeric identity assessment was created",
        ),
        (
            visualization_module._render_finding_context(normal),
            "No finding records were emitted under the current deterministic rules.",
            "This does not establish biological validity",
        ),
        (
            visualization_module._fallback_figure(
                visualization_module._COMPONENTS[0], fallback_reason
            ),
            "The complete typed table is retained without truncation.",
            fallback_reason,
        ),
    )

    for figure, message, limitation_fragment in cases:
        texts = [
            artist.get_text()
            for artist in figure.findobj(match=visualization_module.Text)
        ]
        assert texts.count("Records are not drawn in this static view.") == 1
        assert texts.count(message) == 1
        assert sum(limitation_fragment in text for text in texts) == 1
        visualization_module.plt.close(figure)
