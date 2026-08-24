from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

import bridge.tool_packages.p0_11_public_export.adapter as adapter_module
from bridge.tool_packages.p0_10_claim_verifier.models import report_content_hash
from bridge.tool_packages.p0_11_public_export.adapter import adapter
from bridge.tool_packages.p0_11_public_export.models import PUBLIC_SCHEMA_MODELS
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


ROLE_SCHEMAS = {
    "report_draft": "bridge://schemas/report-draft/v0.1",
    "claim_verification_result": (
        "bridge://schemas/claim-verification-result/v0.1"
    ),
    "public_export_spec": "bridge://schemas/public-export-spec/v0.1",
}


def _report() -> dict:
    text = "product-case:demo@1.0.0 measured 1.2 configured-unit."
    start = text.index("1.2")
    payload = {
        "object_version": "0.1.0",
        "report_id": "report:demo",
        "report_version": "1.0.0",
        "content_hash": "0" * 64,
        "audience": "public_candidate",
        "language": "en",
        "evidence_record_set_ref": "evidence-record-set:demo@1",
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
        "claim_blocks": [
            {
                "claim_id": "claim-block:demo",
                "claim_version": "1.0.0",
                "claim_ref": "claim:demo@1.0.0",
                "product_case_ref": "product-case:demo@1.0.0",
                "claim_type": "measurement_claim",
                "text": text,
                "language": "en",
                "evidence_refs": [f"evidence:{'a' * 24}@1"],
                "statement_refs": [],
                "value_bindings": [
                    {
                        "binding_id": "binding:demo",
                        "source_evidence_ref": f"evidence:{'a' * 24}@1",
                        "source_field": "value",
                        "canonical_numeric_string": "1.2",
                        "raw_unit": "configured-unit",
                        "text_span": [start, start + 3],
                    }
                ],
                "reported_evidence_state": "measured",
                "comparison_mode": "not_applicable",
                "authoring_channel": "deterministic_renderer",
            }
        ],
        "renderer_id": "BRIDGE-REPORT-DRAFT-RENDERER-v0.1",
        "renderer_version": "0.1.0",
        "authoring_channel": "deterministic_renderer",
        "created_at": "2026-08-24T00:00:00Z",
    }
    payload["content_hash"] = report_content_hash(payload)
    return payload


def _verification(report: dict, *, warnings: bool = False) -> dict:
    checks = []
    if warnings:
        checks = [
            {
                "check_id": f"check:{'b' * 16}",
                "claim_id": "claim-block:demo",
                "rule_id": "rule:configured-warning",
                "rule_version": "1.0.0",
                "outcome": "warning",
                "severity": "warning",
                "reason_code": "configured_warning",
                "text_span": None,
                "evidence_refs": [],
                "statement_ref": None,
            }
        ]
    return {
        "object_version": "0.1.0",
        "verification_id": f"claim-verification:{'c' * 16}",
        "verifier_version": "0.1.0",
        "benchmark_id": "P0-10-BENCHMARK-v0.1",
        "benchmark_sha256": (
            "908da7e8c8141e5f44e230315134d53fb63dbc6856b37e06a3b227fe2af51baa"
        ),
        "release_contract_id": "P0-10-RELEASE-CONTRACT-v0.1",
        "release_contract_sha256": (
            "c8a9237652cba4e6b3eb1c4f4215437980f0f480a0944d232abddeef5c4236c8"
        ),
        "report_draft_ref": "report:demo@1.0.0",
        "report_content_hash": report["content_hash"],
        "report_audience": "public_candidate",
        "evidence_graph_id": "case-evidence-graph:demo",
        "evidence_graph_version": 1,
        "evidence_graph_manifest_sha256": "d" * 64,
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
        "release_state": "verified_with_warnings" if warnings else "verified",
        "check_records": checks,
        "public_export_eligibility": "eligible",
    }


def _payloads(*, warnings: bool = False) -> dict[str, dict]:
    report = _report()
    verification = _verification(report, warnings=warnings)
    return {
        "report_draft": report,
        "claim_verification_result": verification,
        "public_export_spec": {
            "object_version": "0.1.0",
            "export_spec_id": "public-export-spec:demo",
            "export_spec_version": "1.0.0",
            "source_report_ref": "report:demo@1.0.0",
            "source_report_hash": report["content_hash"],
            "claim_verification_id": verification["verification_id"],
            "target_language": "en",
            "allowed_claim_types": ["measurement_claim"],
            "allowed_evidence_states": ["measured"],
            "allow_claims_without_evidence_state": False,
            "selections": [
                {
                    "source_claim_id": "claim-block:demo",
                    "public_claim_id": "public-claim:demo",
                    "public_case_label": "Demo candidate",
                    "replacements": [
                        {
                            "source_literal": "product-case:demo@1.0.0",
                            "public_literal": "Demo candidate",
                        }
                    ],
                }
            ],
            "public_source_accessions": ["GSE-DEMO"],
            "prohibited_literals": ["private-canary"],
            "candidate_policy": "human_confirmation_required",
        },
    }


def _write_json(path: Path, payload: dict) -> str:
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def _request(
    tmp_path: Path,
    *,
    payloads: dict[str, dict] | None = None,
    output_dir: Path | None = None,
    input_id_prefix: str = "input",
    random_seed: int = 0,
) -> ToolRequestV2:
    values = deepcopy(payloads or _payloads())
    input_root = tmp_path / f"objects-{input_id_prefix}"
    input_root.mkdir(parents=True)
    refs: list[StructuredInputRef] = []
    for index, role in enumerate(ROLE_SCHEMAS, start=1):
        path = input_root / f"{role}.json"
        digest = _write_json(path, values[role])
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{index}",
                role=role,
                schema_ref=ROLE_SCHEMAS[role],
                object_version="0.1.0",
                path=path,
                sha256=digest,
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id=f"request-{input_id_prefix}",
        tool_id="P0-11",
        tool_version="0.2.0",
        output_dir=output_dir or (tmp_path / "output"),
        random_seed=random_seed,
        object_inputs=refs,
    )


def test_p0_11_is_an_implemented_v2_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-11")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == "bridge://schemas/public-safe-report/v0.1"
    assert spec.adapter_ref == (
        "bridge.tool_packages.p0_11_public_export.adapter:adapter"
    )


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_allowlist_projection_runs_without_internal_identifiers(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["export_state"] == "ready_for_confirmation"
    assert run.result["public_source_accessions"] == ["GSE-DEMO"]
    claim = run.result["claims"][0]
    assert claim["public_claim_id"] == "public-claim:demo"
    assert claim["public_case_label"] == "Demo candidate"
    assert claim["text"] == "Demo candidate measured 1.2 configured-unit."
    assert claim["value_bindings"] == [
        {
            "binding_index": 0,
            "source_field": "value",
            "canonical_numeric_string": "1.2",
            "raw_unit": "configured-unit",
        }
    ]
    serialized = json.dumps(run.result, sort_keys=True)
    for private_value in (
        "product-case:demo",
        "claim-block:demo",
        f"evidence:{'a' * 24}",
        "/Users/",
        "/data1/",
    ):
        assert private_value not in serialized
    assert run.measurements == []
    assert run.visualizations == []
    assert len(run.artifacts) == 1


def test_unselected_claim_is_not_copied(tmp_path: Path) -> None:
    payloads = _payloads()
    extra = deepcopy(payloads["report_draft"]["claim_blocks"][0])
    extra.update(
        {
            "claim_id": "claim-block:not-selected",
            "claim_ref": "claim:not-selected@1.0.0",
            "text": "Private unselected prose.",
            "value_bindings": [],
        }
    )
    payloads["report_draft"]["claim_blocks"].append(extra)
    payloads["report_draft"]["content_hash"] = report_content_hash(
        payloads["report_draft"]
    )
    payloads["claim_verification_result"]["report_content_hash"] = payloads[
        "report_draft"
    ]["content_hash"]
    payloads["public_export_spec"]["source_report_hash"] = payloads["report_draft"][
        "content_hash"
    ]
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert len(run.result["claims"]) == 1
    assert "Private unselected prose" not in json.dumps(run.result)


def test_alias_is_controlled_only_by_export_spec(tmp_path: Path) -> None:
    baseline = ToolRegistry.load_default().run(_request(tmp_path / "baseline"))
    payloads = _payloads()
    selection = payloads["public_export_spec"]["selections"][0]
    selection["public_case_label"] = "Alternate public label"
    selection["replacements"][0]["public_literal"] = "Alternate public label"
    changed = ToolRegistry.load_default().run(
        _request(tmp_path / "changed", payloads=payloads)
    )

    assert baseline.result["claims"][0]["text"].startswith("Demo candidate")
    assert changed.result["claims"][0]["text"].startswith(
        "Alternate public label"
    )
    assert baseline.run_id != changed.run_id


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "private-canary measured 1.2 configured-unit.",
        "/data1/private measured 1.2 configured-unit.",
        "token:demo-secret measured 1.2 configured-unit.",
        "evidence:private-ref measured 1.2 configured-unit.",
    ],
)
def test_unsafe_public_text_fails_without_artifact(
    tmp_path: Path, unsafe_text: str
) -> None:
    payloads = _payloads()
    report = payloads["report_draft"]
    report["claim_blocks"][0]["text"] = unsafe_text
    report["claim_blocks"][0]["value_bindings"] = []
    report["content_hash"] = report_content_hash(report)
    payloads["claim_verification_result"]["report_content_hash"] = report[
        "content_hash"
    ]
    payloads["public_export_spec"]["source_report_hash"] = report["content_hash"]
    payloads["public_export_spec"]["selections"][0]["replacements"] = []
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["public_projection_failed"]
    assert run.result is None
    assert run.artifacts == []
    assert unsafe_text not in json.dumps(run.model_dump(mode="json"))


def test_verified_with_warnings_requires_human_review(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(
        _request(tmp_path, payloads=_payloads(warnings=True))
    )

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["export_state"] == "review_required"
    assert run.reason_codes == ["p0_10_verified_with_warnings"]


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda p: p["claim_verification_result"].update(
                {"report_content_hash": "e" * 64}
            ),
            "claim_verification_report_binding_mismatch",
        ),
        (
            lambda p: p["claim_verification_result"].update(
                {
                    "release_state": "release_blocked",
                    "public_export_eligibility": "ineligible",
                    "check_records": [
                        {
                            "check_id": f"check:{'f' * 16}",
                            "claim_id": "claim-block:demo",
                            "rule_id": "rule:block",
                            "rule_version": "1.0.0",
                            "outcome": "blocked",
                            "severity": "hard_blocker",
                            "reason_code": "configured_blocker",
                            "text_span": None,
                            "evidence_refs": [],
                            "statement_ref": None,
                        }
                    ],
                }
            ),
            "claim_verification_not_export_eligible",
        ),
        (
            lambda p: p["public_export_spec"].update(
                {"source_report_hash": "f" * 64}
            ),
            "export_spec_report_binding_mismatch",
        ),
        (
            lambda p: p["public_export_spec"].update(
                {"claim_verification_id": f"claim-verification:{'0' * 16}"}
            ),
            "export_spec_verification_binding_mismatch",
        ),
        (
            lambda p: p["public_export_spec"].update({"target_language": "zh"}),
            "export_language_mismatch",
        ),
        (
            lambda p: p["public_export_spec"]["selections"][0].update(
                {"source_claim_id": "claim-block:missing"}
            ),
            "export_claim_not_found",
        ),
        (
            lambda p: p["public_export_spec"].update(
                {"allowed_claim_types": ["availability_claim"]}
            ),
            "export_claim_type_not_allowed",
        ),
        (
            lambda p: p["public_export_spec"].update(
                {"allowed_evidence_states": ["inferred"]}
            ),
            "export_evidence_state_not_allowed",
        ),
        (
            lambda p: p["public_export_spec"]["selections"][0][
                "replacements"
            ][0].update({"source_literal": "not-in-source"}),
            "public_alias_source_not_found",
        ),
    ],
)
def test_cross_binding_failures_are_typed(
    tmp_path: Path, mutate, reason: str
) -> None:
    payloads = _payloads()
    mutate(payloads)
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert reason in run.reason_codes
    assert run.result is None
    assert run.artifacts == []


def test_strict_boolean_is_not_coerced(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["public_export_spec"]["allow_claims_without_evidence_state"] = "false"
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-11"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_input_id_renaming_reuses_same_public_candidate(tmp_path: Path) -> None:
    first = ToolRegistry.load_default().run(
        _request(
            tmp_path / "first",
            output_dir=tmp_path / "output",
            input_id_prefix="alpha",
        )
    )
    second = ToolRegistry.load_default().run(
        _request(
            tmp_path / "second",
            output_dir=tmp_path / "output",
            input_id_prefix="beta",
        )
    )

    assert first.run_id == second.run_id
    assert first.input_hash == second.input_hash
    assert first.result == second.result
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256


def test_existing_output_file_returns_typed_failure(tmp_path: Path) -> None:
    output = tmp_path / "occupied"
    output.write_text("keep", encoding="utf-8")
    run = ToolRegistry.load_default().run(
        _request(tmp_path / "request", output_dir=output)
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_dir_not_regular_directory"]
    assert output.read_text(encoding="utf-8") == "keep"


def test_nonzero_random_seed_is_refused(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path, random_seed=11))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["p0_11_random_seed_forbidden"]


def test_v1_request_is_refused_without_bare_exception(tmp_path: Path) -> None:
    request = ToolRequest(request_id="v1", tool_id="P0-11", output_dir=tmp_path)
    spec = ToolRegistry.load_default().describe("P0-11")

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]


def test_registry_detects_input_mutation_during_adapter_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    target = request.object_inputs[0].path
    original = adapter_module.build_public_safe_report

    def mutate_input(**kwargs):
        result = original(**kwargs)
        target.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(adapter_module, "build_public_safe_report", mutate_input)
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.result is None
    assert run.artifacts == []


def test_implementation_contains_no_biological_names_or_thresholds() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package.glob("*.py"))
    )

    for biological_term in (
        "MKI67",
        "FOXA2",
        "ventral midbrain",
        "fetal",
        "scRNA-seq",
        "snRNA-seq",
        "0.05",
    ):
        assert biological_term not in source
