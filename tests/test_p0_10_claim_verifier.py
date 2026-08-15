from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from decimal import Decimal
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
from bridge.tool_packages.p0_10_claim_verifier.benchmark import (
    benchmark_sha256,
    decision_payload_sha256,
    load_benchmark,
    render_benchmark_markdown,
)
from bridge.tool_packages.p0_10_claim_verifier.models import (
    PUBLIC_SCHEMA_MODELS,
    ClaimPolicySpec,
    ClaimVerifierRunResult,
    NumericFormatSpec,
    ReportDraft,
    StatementRegistry,
    report_content_hash,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import (
    _render_decimal,
    load_release_contract,
    release_contract_sha256,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequestV2,
)
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
        "format_spec": {
            "decimal_places": 0,
            "scale": "identity",
            "rounding": "half_even",
        },
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
    reviews: list[dict[str, Any]] | None = None,
    include_binding: bool = True,
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
        "audience": "public_candidate",
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
                "intended_release_tier": "formal",
                "authoring_channel": "deterministic_renderer",
            }
        ],
        "human_review_decisions": reviews or [],
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
    assert benchmark.benchmark_state == "server_validated_candidate"
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


def test_verified_report_records_benchmark_and_one_immutable_artifact(tmp_path: Path) -> None:
    request = _request(tmp_path)
    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["verification"]["release_state"] == "verified"
    assert run.result["verified_report"] is not None
    assert run.result["verified_report"]["claims"][0]["claim_ref"] == CLAIM_REF
    assert (
        run.result["verified_report"]["claims"][0]["product_case_ref"]
        == PRODUCT_CASE_REF
    )
    verification = run.result["verification"]
    assert verification["benchmark_id"] == "P0-10-BENCHMARK-v0.1"
    assert verification["benchmark_sha256"] == benchmark_sha256()
    assert verification["release_contract_id"] == load_release_contract().contract_id
    assert verification["release_contract_sha256"] == release_contract_sha256()
    assert run.measurements == []
    assert len(run.artifacts) == 1
    assert hashlib.sha256(run.artifacts[0].path.read_bytes()).hexdigest() == run.artifacts[0].sha256


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
    assert run.result["verification"]["release_state"] == "release_blocked"
    assert reason in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }
    assert run.result["verified_report"] is None


def test_numeric_suffix_cannot_hide_an_extra_number(tmp_path: Path) -> None:
    text = "installed-wheel-test-count: 192 tests999."
    start = text.index("192")
    report = _report_payload(
        text=text,
        binding_changes={"text_span": (start, start + len("192 tests999"))},
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["verification"]["release_state"] == "release_blocked"
    assert "rendered_numeric_mismatch" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }


@pytest.mark.parametrize("token", ["192tests", "192cells", "1e3cells", "192_tests"])
def test_numeric_lexemes_adjacent_to_units_or_identifiers_are_not_hidden(
    tmp_path: Path, token: str
) -> None:
    text = f"installed-wheel-test-count: {token}."
    numeric = "1e3" if token.startswith("1e3") else "192"
    start = text.index(numeric)
    report = _report_payload(text=text, include_binding=False)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    unbound = [
        item
        for item in run.result["verification"]["check_records"]
        if item["reason_code"] == "unbound_numeric_token"
    ]
    assert any(item["text_span"] == [start, start + len(numeric)] for item in unbound)
    assert run.result["verification"]["release_state"] == "release_blocked"


def test_declared_renderer_cannot_author_extra_scientific_prose(tmp_path: Path) -> None:
    report = _report_payload(
        text=(
            "installed-wheel-test-count: 192 tests. "
            "The cells produce dopamine."
        )
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["verification"]["release_state"] == "release_blocked"
    assert "deterministic_claim_text_mismatch" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }
    assert run.result["verified_report"] is None


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

    assert run.result["verification"]["release_state"] == "review_required"
    assert not {
        "canonical_numeric_mismatch",
        "unit_mismatch",
        "rendered_numeric_mismatch",
        "unbound_numeric_token",
    }.intersection(
        item["reason_code"] for item in run.result["verification"]["check_records"]
    )


def test_repeated_number_requires_one_binding_per_occurrence(tmp_path: Path) -> None:
    report = _report_payload(
        text="The first run passed 192 tests and the second passed 192 tests."
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert "unbound_numeric_token" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
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

    assert run.result["verification"]["release_state"] == "release_blocked"
    assert reason in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
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

    assert run.result["verification"]["release_state"] == "review_required"
    assert run.result["verification"]["public_export_eligibility"] == "ineligible"
    assert "non_deterministic_authoring_requires_review" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }


def test_unapproved_renderer_metadata_requires_review(tmp_path: Path) -> None:
    report = _report_payload()
    report["renderer_version"] = "caller-defined"
    report["content_hash"] = report_content_hash(report)

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["verification"]["release_state"] == "review_required"
    assert "unapproved_renderer_requires_review" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }


def test_unbound_number_and_evidence_state_substitution_block_release(tmp_path: Path) -> None:
    report = _report_payload(
        text="The installed-wheel suite passed 192 tests across 2 runs.",
        reported_state="negative",
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())
    reasons = {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }

    assert {"unbound_numeric_token", "evidence_state_mismatch"} <= reasons
    assert run.result["verification"]["release_state"] == "release_blocked"


def test_registered_boundary_statement_is_exact_exception(tmp_path: Path) -> None:
    report = _report_payload(
        text="This verification does not establish safety.",
        claim_type="policy_or_boundary_statement",
        reported_state=None,
        statement_refs=["statement:safety-boundary@0.1.0"],
        evidence_refs=[],
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["verification"]["release_state"] == "verified"


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

    assert run.result["verification"]["release_state"] == "release_blocked"
    assert "prohibited_claim" in {
        item["reason_code"]
        for item in run.result["verification"]["check_records"]
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


def test_decimal_rounding_modes_are_explicit() -> None:
    half_even = NumericFormatSpec(decimal_places=2, rounding="half_even")
    half_up = NumericFormatSpec(decimal_places=2, rounding="half_up")

    assert _render_decimal(Decimal("2.345"), half_even) == "2.34"
    assert _render_decimal(Decimal("2.345"), half_up) == "2.35"


def test_claim_text_cannot_execute_nested_template_syntax(tmp_path: Path) -> None:
    report = _report_payload(
        text="The {{ literal_template_text }} suite passed 192 tests."
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.result["verification"]["release_state"] == "release_blocked"
    assert "deterministic_claim_text_mismatch" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }
    assert run.result["verified_report"] is None


def test_human_review_cannot_turn_free_prose_or_a_blocker_into_verified_output(
    tmp_path: Path,
) -> None:
    approved_review = {
        "claim_id": "claim-block:test-count",
        "rule_id": "rule:ambiguous-superiority",
        "decision": "approved",
        "reviewer_role": "claim_reviewer",
        "reviewer_ref": "reviewer:authorized",
        "reason": "The comparison scope is explicit in the structured Evidence.",
    }
    review_report = _report_payload(
        text="The better run passed 192 tests.", reviews=[approved_review]
    )
    review_report["authoring_channel"] = "human_edit"
    review_report["claim_blocks"][0]["authoring_channel"] = "human_edit"
    review_report["content_hash"] = report_content_hash(review_report)
    review_run = adapter.run(_request(tmp_path / "review", report=review_report), _spec())
    assert review_run.result["verification"]["release_state"] == "review_required"
    assert any(
        item["outcome"] == "cleared_by_review"
        for item in review_run.result["verification"]["check_records"]
    )
    assert review_run.result["verified_report"] is None

    blocker_report = _report_payload(
        text="The safe run passed 192 tests.",
        reviews=[approved_review | {"rule_id": "rule:prohibited-clinical"}],
    )
    blocker_run = adapter.run(
        _request(tmp_path / "blocker", report=blocker_report), _spec()
    )
    assert blocker_run.result["verification"]["release_state"] == "release_blocked"


def test_descriptive_claim_cannot_use_inferential_language(tmp_path: Path) -> None:
    report = _report_payload(
        text="The result was statistically significant at 192 tests.",
        claim_type="descriptive_comparison",
        comparison_mode="descriptive_only",
    )
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert "inferential_language_in_descriptive_claim" in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }


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


def test_unsafe_review_metadata_fails_without_echoing_the_value(tmp_path: Path) -> None:
    private_value = "/" + "data1/example/private/reviewer.txt"
    report = _report_payload(
        text="The better run passed 192 tests.",
        reviews=[
            {
                "claim_id": "claim-block:test-count",
                "rule_id": "rule:ambiguous-superiority",
                "decision": "approved",
                "reviewer_role": "claim_reviewer",
                "reviewer_ref": private_value,
                "reason": "The structured comparison scope was reviewed.",
            }
        ],
    )

    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["unsafe_report_content"]
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


def test_run_result_model_and_public_schema_reject_impossible_combinations(
    tmp_path: Path,
) -> None:
    valid = adapter.run(_request(tmp_path / "valid"), _spec()).result
    assert valid is not None
    ClaimVerifierRunResult.model_validate(valid)
    validator = Draft202012Validator(ClaimVerifierRunResult.model_json_schema())
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
        for item in blocked["verification"]["check_records"]
        if item["outcome"] == "blocked"
    )

    impossible: list[dict[str, Any]] = []
    state_mismatch = deepcopy(valid)
    state_mismatch["verification"]["check_records"] = [blocked_check]
    impossible.append(state_mismatch)

    missing_report = deepcopy(valid)
    missing_report["verified_report"] = None
    impossible.append(missing_report)

    duplicate_benchmark = deepcopy(valid)
    duplicate_benchmark["benchmark_id"] = "caller-benchmark"
    duplicate_benchmark["benchmark_sha256"] = "0" * 64
    impossible.append(duplicate_benchmark)

    wrong_benchmark_receipt = deepcopy(valid)
    wrong_benchmark_receipt["verification"]["benchmark_sha256"] = "0" * 64
    impossible.append(wrong_benchmark_receipt)

    wrong_release_receipt = deepcopy(valid)
    wrong_release_receipt["verification"]["release_contract_sha256"] = "0" * 64
    impossible.append(wrong_release_receipt)

    redundant_counts = deepcopy(valid)
    redundant_counts["verification"]["blocker_count"] = 3
    impossible.append(redundant_counts)

    redundant_render_hash = deepcopy(valid)
    redundant_render_hash["verified_report"]["rendered_sha256"] = "0" * 64
    impossible.append(redundant_render_hash)

    for payload in impossible:
        with pytest.raises(ValueError):
            ClaimVerifierRunResult.model_validate(payload)
        with pytest.raises(JSONSchemaValidationError):
            validator.validate(payload)


def test_registry_exposes_p0_10_as_v2_candidate() -> None:
    spec = _spec()

    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.input_schema_ref == "bridge://schemas/tool-request/v0.2"
    assert spec.result_schema_ref == "bridge://schemas/claim-verifier-run-result/v0.1"
