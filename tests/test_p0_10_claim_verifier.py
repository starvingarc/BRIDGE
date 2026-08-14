from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages.p0_09_evidence_compiler.models import (
    EvidenceRecord,
    EvidenceRecordSet,
)
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
    NumericFormatSpec,
    ReportDraft,
    StatementRegistry,
    report_content_hash,
)
from bridge.tool_packages.p0_10_claim_verifier.verifier import _render_decimal
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


def _policy(*, active: bool = True, severity: str = "hard_blocker") -> ClaimPolicySpec:
    return ClaimPolicySpec.model_validate(
        {
            "object_version": "0.1.0",
            "policy_id": "claim-policy:p0-10-public",
            "policy_version": "0.1.0",
            "active": active,
            "claim_type_policies": [
                {
                    "claim_type": "measurement_claim",
                    "requires_evidence": True,
                    "allowed_evidence_states": ["measured", "negative"],
                    "allowed_comparison_modes": ["not_applicable"],
                },
                {
                    "claim_type": "descriptive_comparison",
                    "requires_evidence": True,
                    "allowed_evidence_states": ["measured"],
                    "allowed_comparison_modes": ["descriptive_only"],
                },
                {
                    "claim_type": "policy_or_boundary_statement",
                    "requires_evidence": False,
                    "allowed_evidence_states": [],
                    "allowed_comparison_modes": ["not_applicable"],
                },
            ],
            "text_rules": [
                {
                    "rule_id": "rule:prohibited-clinical",
                    "version": "0.1.0",
                    "languages": ["zh", "en", "mixed"],
                    "pattern": "(?:safe|safety|安全|potency|疗效|best product|最佳产品)",
                    "severity": severity,
                    "reason_code": "prohibited_claim",
                    "except_statement_refs": ["statement:safety-boundary@0.1.0"],
                },
                {
                    "rule_id": "rule:ambiguous-superiority",
                    "version": "0.1.0",
                    "languages": ["zh", "en", "mixed"],
                    "pattern": "(?:better|更好)",
                    "severity": "review",
                    "reason_code": "ambiguous_superiority",
                    "except_statement_refs": [],
                },
            ],
            "descriptive_forbidden_patterns": [
                "(?:statistically significant|显著优于|caused|导致)"
            ],
            "authorized_reviewer_roles": ["claim_reviewer"],
            "require_all_numeric_tokens_bound": True,
        }
    )


def _statements() -> StatementRegistry:
    return StatementRegistry.model_validate(
        {
            "object_version": "0.1.0",
            "registry_id": "BRIDGE-STATEMENT-REGISTRY-v0.1",
            "registry_version": "0.1.0",
            "statements": [
                {
                    "statement_id": "statement:safety-boundary",
                    "statement_version": "0.1.0",
                    "texts": {
                        "en": "This verification does not establish safety.",
                        "zh": "本次核对不能证明安全性。",
                        "mixed": "This verification does not establish safety（不能证明安全性）。",
                    },
                    "allowed_claim_types": ["policy_or_boundary_statement"],
                    "approved": True,
                }
            ],
        }
    )


def _report_payload(
    *,
    text: str = "The installed-wheel suite passed 192 tests.",
    claim_type: str = "measurement_claim",
    reported_state: str | None = "measured",
    comparison_mode: str = "not_applicable",
    binding_changes: dict[str, Any] | None = None,
    statement_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    binding = {
        "binding_id": "binding:test-count",
        "source_evidence_ref": EVIDENCE_REF,
        "source_field": "value",
        "canonical_numeric_string": "192",
        "raw_unit": "tests",
        "denominator_numeric_string": "192",
        "interval_lower_numeric_string": "192",
        "interval_upper_numeric_string": "192",
        "format_spec": {
            "decimal_places": 0,
            "scale": "identity",
            "suffix": "",
            "rounding": "half_even",
        },
        "rendered_value": "192",
    }
    binding.update(binding_changes or {})
    claim_evidence = [EVIDENCE_REF] if evidence_refs is None else evidence_refs
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
                "claim_type": claim_type,
                "text": text,
                "language": "en",
                "evidence_refs": claim_evidence,
                "statement_refs": statement_refs or [],
                "value_bindings": [binding] if claim_evidence else [],
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
    evidence_set: EvidenceRecordSet | None = None,
    policy: ClaimPolicySpec | None = None,
) -> ToolRequestV2:
    tmp_path.mkdir(parents=True, exist_ok=True)
    objects = [
        ("report", "report_draft", "bridge://schemas/report-draft/v0.1", report or _report_payload()),
        (
            "evidence",
            "evidence_record_set",
            "bridge://schemas/evidence-record-set/v0.1",
            (evidence_set or _evidence_set()).model_dump(mode="json"),
        ),
        (
            "policy",
            "claim_policy_spec",
            "bridge://schemas/claim-policy-spec/v0.1",
            (policy or _policy()).model_dump(mode="json"),
        ),
        (
            "statements",
            "statement_registry",
            "bridge://schemas/statement-registry/v0.1",
            _statements().model_dump(mode="json"),
        ),
    ]
    refs: list[StructuredInputRef] = []
    for input_id, role, schema_ref, payload in objects:
        path = tmp_path / f"{input_id}.json"
        refs.append(
            StructuredInputRef(
                input_id=input_id,
                role=role,
                schema_ref=schema_ref,
                object_version="0.1.0",
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
    assert set(spec.method_ids) == approved_runtime
    assert len(benchmark.methods) == 18
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


def test_verified_report_records_benchmark_and_one_immutable_artifact(tmp_path: Path) -> None:
    request = _request(tmp_path)
    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["verification"]["release_state"] == "verified"
    assert run.result["verified_report"] is not None
    assert run.result["benchmark_id"] == "P0-10-BENCHMARK-v0.1"
    assert run.result["benchmark_sha256"] == benchmark_sha256()
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
        ({"denominator_numeric_string": "191"}, "denominator_mismatch"),
        ({"interval_upper_numeric_string": "193"}, "interval_mismatch"),
        ({"rendered_value": "191"}, "rendered_numeric_mismatch"),
    ],
)
def test_numeric_mutations_are_hard_blockers(
    tmp_path: Path, changes: dict[str, Any], reason: str
) -> None:
    report = _report_payload(binding_changes=changes)
    if "rendered_value" in changes:
        report["claim_blocks"][0]["text"] = "The installed-wheel suite passed 191 tests."
        report["content_hash"] = report_content_hash(report)
    run = adapter.run(_request(tmp_path, report=report), _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["verification"]["release_state"] == "release_blocked"
    assert reason in {
        item["reason_code"] for item in run.result["verification"]["check_records"]
    }
    assert run.result["verified_report"] is None


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

    assert run.result["verification"]["release_state"] == "verified"
    assert "{{ literal_template_text }}" in run.result["verified_report"][
        "rendered_markdown"
    ]


def test_human_review_can_clear_review_item_but_not_hard_blocker(tmp_path: Path) -> None:
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
    review_run = adapter.run(_request(tmp_path / "review", report=review_report), _spec())
    assert review_run.result["verification"]["release_state"] == "verified"
    assert any(
        item["outcome"] == "cleared_by_review"
        for item in review_run.result["verification"]["check_records"]
    )

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


def test_inactive_policy_returns_partial_not_assessed(tmp_path: Path) -> None:
    run = adapter.run(_request(tmp_path, policy=_policy(active=False)), _spec())

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.reason_codes == ["active_claim_policy_required"]
    assert run.result["verification"]["release_state"] == "not_assessed"
    assert run.result["verified_report"] is None


def test_report_hash_mismatch_fails_before_verification(tmp_path: Path) -> None:
    report = _report_payload()
    report["content_hash"] = "f" * 64
    request = _request(tmp_path, report=report)

    eligibility = adapter.check_eligibility(request, _spec())

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["structured_input_schema_invalid"]


def test_existing_result_drift_fails_without_overwrite(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    first.artifacts[0].path.write_text("{}\n", encoding="utf-8")

    second = adapter.run(request, _spec())

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]


def test_registry_exposes_p0_10_as_v2_candidate() -> None:
    spec = _spec()

    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.input_schema_ref == "bridge://schemas/tool-request/v0.2"
    assert spec.result_schema_ref == "bridge://schemas/claim-verifier-run-result/v0.1"
