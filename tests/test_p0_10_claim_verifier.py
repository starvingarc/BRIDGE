from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
import pytest

import bridge.tool_packages.p0_10_claim_verifier.adapter as adapter_module
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    EvidenceRecord,
    EvidenceRecordSet,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.tool_packages.p0_10_claim_verifier.adapter import adapter
from bridge.tool_packages.p0_10_claim_verifier.benchmark import (
    benchmark_sha256,
    decision_payload_sha256,
    load_benchmark,
    render_benchmark_markdown,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    PUBLIC_SCHEMA_MODELS,
    ClaimPolicySpec,
    ClaimVerificationResult,
    ReportDraft,
    StatementRegistry,
    report_content_hash,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import (
    load_release_contract,
    release_contract_sha256,
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


CREATED_AT = "2026-08-12T00:00:00Z"
EVIDENCE_REF = "evidence:" + "a" * 24 + "@1"
CLAIM_REF = "claim:server-validation-test-count@1.0.0"
PRODUCT_CASE_REF = "product-case:public-validation@1.0.0"


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
        "logical_key": "public-server-test-count",
        "content_hash": "b" * 64,
        "product_case_ref": {
            "object_id": "product-case:public-validation",
            "object_version": "1.0.0",
        },
        "sample_or_preparation_ref": {
            "object_id": "report-source:server-validation",
            "object_version": "1.0.0",
        },
        "domain_id": "target_identity",
        "measurement_result_ref": {
            "object_id": "measurement-result:test-count",
            "object_version": "1.0.0",
        },
        "measurement_spec_ref": {
            "object_id": "measurement-spec:test-count",
            "object_version": "1.0.0",
        },
        "metric_id": "installed-wheel-test-count",
        "value": 192,
        "unit": "tests",
        "numerator": 192,
        "denominator": 192,
        "interval": {
            "lower": 192.0,
            "upper": 192.0,
            "confidence_level": None,
            "method_ref": None,
        },
        "claim_ref": {
            "object_id": "claim:server-validation-test-count",
            "object_version": "1.0.0",
        },
        "biological_context": {
            "context_id": "context:engineering-validation",
            "context_version": "1.0.0",
        },
        "relation": "supports",
        "evidence_state": "measured",
        "evidence_tier": "formal",
        "lifecycle_state": "active",
        "applicability": "applicable",
        "evidence_family_ref": {
            "object_id": "evidence-family:engineering-validation",
            "object_version": "1.0.0",
        },
        "sufficiency_profile_ref": {
            "object_id": "evidence-sufficiency-profile:public-validation",
            "object_version": "1.0.0",
        },
        "tool_run_ref": {
            "object_id": "tool-run:public-validation",
            "object_version": "1.0.0",
        },
        "tool_run_execution_state": "succeeded",
        "reference_refs": [],
        "prior_refs": [],
        "artifact_refs": [],
        "provenance_refs": ["provenance:public-server-validation"],
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


def _graph_manifest(evidence_set: EvidenceRecordSet | None = None) -> dict[str, Any]:
    evidence_set = evidence_set or _evidence_set()

    def artifact(filename: str, *, parquet: bool = False) -> dict[str, Any]:
        return {
            "filename": filename,
            "media_type": (
                "application/vnd.apache.parquet" if parquet else "application/json"
            ),
            "sha256": "e" * 64,
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
            "object_id": "product-case:public-validation",
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
    binding_id: str = "test-count",
    source_field: str = "value",
    canonical: str = "192",
    raw_unit: str | None = "tests",
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
    text: str = "installed-wheel-test-count: 192 tests.",
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
        rendered = "192 tests" if "192 tests" in text else "192"
        binding = _value_binding(text, rendered)
        binding.update(binding_changes or {})
    payload = {
        "object_version": "0.1.0",
        "report_id": "report:public-server-validation",
        "report_version": "0.1.0",
        "content_hash": "0" * 64,
        "audience": audience,
        "language": "en",
        "evidence_record_set_ref": "evidence-record-set:" + "c" * 16 + "@0.1.0",
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
        "claim_blocks": [
            {
                "claim_id": "claim-block:test-count",
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
            _graph_manifest(),
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
        tool_version="0.1.0",
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


def test_benchmark_is_task_grouped_complete_and_has_no_default_or_aggregate() -> None:
    benchmark = load_benchmark()
    spec = _spec()

    approved_runtime = {
        method.method_id
        for method in benchmark.methods
        if method.decision.state.value == "approved"
        and method.recommendation.value in {"default_candidate", "sensitivity_candidate"}
    }

    assert benchmark.default_method_id is None
    assert benchmark.aggregate_score is None
    assert benchmark.aggregate_rank is None
    assert benchmark.benchmark_state == "awaiting_server_validation"
    assert set(spec.method_ids) == approved_runtime
    assert len(benchmark.methods) == 18
    internal_case = next(
        case
        for case in benchmark.data_cases
        if case.case_id == "INTERNAL-ANONYMIZED-REPORT-v0.1"
    )
    assert internal_case.claim_count == 3
    assert all(
        internal_case.case_id in method.data_case_ids
        for method in benchmark.methods
        if method.evaluation != "audit_only"
    )
    core = next(
        method
        for method in benchmark.methods
        if method.method_id == "METHOD-INTERNAL-DETERMINISTIC-ENGINE-33C959"
    )
    assert core.task_metrics["internal_claim_count"] == 3
    assert core.task_metrics["internal_repeat_match"] == 1.0
    assert {
        method.decision.benchmark_sha256 for method in benchmark.methods
    } == {decision_payload_sha256(benchmark.model_dump(mode="json"))}
    assert benchmark_sha256() == hashlib.sha256(
        Path(
            "src/bridge/tool_packages/p0_10_claim_verifier/resources/benchmark_v0.1.json"
        ).read_bytes()
    ).hexdigest()


def test_benchmark_markdown_is_generated_from_json() -> None:
    expected = render_benchmark_markdown()
    actual = Path("tool_packages/P0-10/BENCHMARK.md").read_text(encoding="utf-8")

    assert actual == expected
    assert "Aggregate score/rank: `null` / `null`" in actual
    assert "## Exact numeric and unit fidelity" in actual

    card = Path("src/bridge/tool_packages/cards/P0-10.md").read_text(
        encoding="utf-8"
    )
    assert benchmark_sha256() in card
    assert f"`{load_benchmark().benchmark_state}`" in card


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
    assert run.result["benchmark_id"] == "P0-10-BENCHMARK-v0.1"
    assert run.result["benchmark_sha256"] == benchmark_sha256()
    assert run.result["release_contract_id"] == load_release_contract().contract_id
    assert run.result["release_contract_sha256"] == release_contract_sha256()
    assert run.measurements == []
    assert len(run.artifacts) == 1
    artifact_bytes = run.artifacts[0].path.read_bytes()
    assert artifact_bytes == canonical_json_bytes(run.result, indent=2)
    assert hashlib.sha256(artifact_bytes).hexdigest() == run.artifacts[0].sha256


def test_p0_11_can_reject_a_mutated_report_draft_from_the_p0_10_receipt(
    tmp_path: Path,
) -> None:
    payload = _report_payload()
    report = ReportDraft.model_validate(payload)
    run = adapter.run(_request(tmp_path, report=payload), _spec())
    receipt = ClaimVerificationResult.model_validate(run.result)

    assert receipt.matches_report_draft(report)
    for field, value in (
        ("text", "This product is clinically safe."),
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
        ({"canonical_numeric_string": "191"}, "canonical_numeric_mismatch"),
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
    text = "installed-wheel-test-count: 192 tests999."
    start = text.index("192")
    report = _report_payload(
        text=text,
        binding_changes={"text_span": (start, start + len("192 tests999"))},
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "release_blocked"
    assert "rendered_numeric_mismatch" in {
        item["reason_code"] for item in run.result["check_records"]
    }


@pytest.mark.parametrize(
    ("token", "numeric", "canonical", "unit", "value"),
    [
        ("192tests", "192", "192", "tests", 192),
        ("192cells", "192", "192", "cells", 192),
        ("1e3cells", "1e3", "1000", "cells", 1000),
        ("192_tests", "192", "192", "tests", 192),
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
    text = f"installed-wheel-test-count: {token}."
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
    report = _report_payload(text=f"{metric_id}: 192 tests.")

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["release_state"] == "verified"
    assert run.result["check_records"] == []


def test_large_finite_integer_returns_a_typed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = 10**30
    _stub_graph(monkeypatch, _evidence_set(value=value))
    text = f"installed-wheel-test-count: {value} tests."
    report = _report_payload(text=text, include_binding=False)
    report["claim_blocks"][0]["value_bindings"] = [
        _value_binding(text, str(value), canonical=str(value))
    ]
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["release_state"] == "verified"


def test_declared_renderer_cannot_author_extra_scientific_prose(tmp_path: Path) -> None:
    report = _report_payload(
        text=(
            "installed-wheel-test-count: 192 tests. "
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
            denominator=200,
            interval={
                "lower": 180,
                "upper": 198,
                "confidence_level": None,
                "method_ref": None,
            },
        ),
    )
    text = (
        "The value was 192 tests, denominator 200 tests, "
        "and interval 180 tests to 198 tests."
    )
    report = _report_payload(text=text)
    report["claim_blocks"][0]["value_bindings"] = [
        _value_binding(text, "192 tests"),
        _value_binding(
            text,
            "200 tests",
            binding_id="denominator",
            source_field="denominator",
            canonical="200",
        ),
        _value_binding(
            text,
            "180 tests",
            binding_id="interval-lower",
            source_field="interval_lower",
            canonical="180",
        ),
        _value_binding(
            text,
            "198 tests",
            binding_id="interval-upper",
            source_field="interval_upper",
            canonical="198",
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
        text="The first run passed 192 tests and the second passed 192 tests."
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
        text="The installed-wheel suite passed 192 tests across 2 runs.",
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
        ("该套件通过 192 项测试，因此证明安全性。", "zh"),
        ("The suite passed 192 tests；这不能证明安全性。", "mixed"),
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
        "- The installed-wheel suite passed 192 tests.",
        "The *installed-wheel* suite passed 192 tests.",
        "The suite passed 192 tests. <img src=x onerror=alert(1)>",
    ],
)
def test_report_claims_reject_free_markup(text: str) -> None:
    with pytest.raises(ValueError, match="plain structured paragraph"):
        ReportDraft.model_validate(_report_payload(text=text))


def test_caller_numeric_transform_is_rejected_before_verification(
    tmp_path: Path,
) -> None:
    report = _report_payload(text="installed-wheel-test-count: 19200 tests.")
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
        text="The {{ literal_template_text }} suite passed 192 tests."
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
            "claim_id": "claim-block:test-count",
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
        text="The result was statistically significant at 192 tests.",
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
        text="installed-wheel-test-count: 192 tests; this proves safety."
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
            "claim_id": "claim-block:test-count",
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
    publish = adapter_module._publish_result

    def replace_after_publish(**kwargs: Any) -> Path:
        path = publish(**kwargs)
        path.write_bytes(b'{"replacement":true}\n')
        return path

    monkeypatch.setattr(adapter_module, "_publish_result", replace_after_publish)

    run = adapter.run(_request(tmp_path), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["published_result_hash_mismatch"]
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
                text="installed-wheel-test-count: 192 tests; this proves safety."
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
