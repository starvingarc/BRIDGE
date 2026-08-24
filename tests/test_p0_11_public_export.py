from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

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
    "claim_verifier_run": "bridge://schemas/tool-run/v0.2",
    "review_projection_spec": (
        "bridge://schemas/review-projection-spec/v0.1"
    ),
}


def _report() -> dict[str, Any]:
    text = "configured_metric: 1.2 configured-unit."
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


def _verification(report: dict[str, Any], *, warnings: bool = False) -> dict:
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
            "ac0b6d8251ac2d7d73ae9e1247d9a7bca3a0676f64b9707a51a16ddfe22e640c"
        ),
        "public_release_authority_state": "not_configured",
        "report_draft_ref": "report:demo@1.0.0",
        "report_content_hash": report["content_hash"],
        "report_audience": report["audience"],
        "evidence_graph_id": "case-evidence-graph:demo",
        "evidence_graph_version": 1,
        "evidence_graph_manifest_sha256": "d" * 64,
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0",
        "release_state": "verified_with_warnings" if warnings else "verified",
        "check_records": checks,
        "public_export_eligibility": "ineligible",
    }


def _payloads(*, warnings: bool = False) -> dict[str, dict]:
    report = _report()
    verification = _verification(report, warnings=warnings)
    return {
        "report_draft": report,
        "claim_verification_result": verification,
        "review_projection_spec": {
            "object_version": "0.1.0",
            "projection_spec_id": "review-projection-spec:demo",
            "projection_spec_version": "1.0.0",
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
                    "review_claim_id": "review-claim:demo",
                    "review_case_label": "Demo candidate",
                }
            ],
            "source_accessions": ["GSE-DEMO"],
            "prohibited_literals": ["private-canary"],
            "review_policy": "human_review_required",
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def _claim_verifier_run(
    *,
    root: Path,
    verification: dict[str, Any],
    verification_path: Path,
    verification_sha256: str,
) -> dict[str, Any]:
    return {
        "run_id": "run-p0-10-demo",
        "request": {
            "request_id": "request-p0-10-demo",
            "tool_id": "P0-10",
            "tool_version": "0.1.0",
            "output_dir": str((root / "p0-10-output").resolve()),
            "assets": [],
            "measurement_spec_ref": None,
            "parameters": {},
            "random_seed": 0,
            "object_inputs": [],
        },
        "implementation_state": "implemented",
        "execution_state": "succeeded",
        "tool_version": "0.1.0",
        "environment_spec_id": "ENV-EVIDENCE-v0.1",
        "input_hash": "a" * 64,
        "created_at": "2026-08-24T00:00:00Z",
        "measurements": [],
        "artifacts": [
            {
                "artifact_id": "artifact:run-p0-10-demo:claim-verification",
                "kind": "claim_verification_result",
                "path": str(verification_path.resolve()),
                "media_type": "application/json",
                "sha256": verification_sha256,
                "evidence_ids": [],
            }
        ],
        "visualizations": [],
        "result_schema_ref": (
            "bridge://schemas/claim-verification-result/v0.1"
        ),
        "result": verification,
        "reason_codes": [],
        "warnings": [],
    }


def _request(
    tmp_path: Path,
    *,
    payloads: dict[str, dict] | None = None,
    claim_verifier_run: dict[str, Any] | None = None,
    claim_verification_result_path: Path | None = None,
    output_dir: Path | None = None,
    input_id_prefix: str = "input",
    random_seed: int = 0,
) -> ToolRequestV2:
    values = deepcopy(payloads or _payloads())
    input_root = tmp_path / f"objects-{input_id_prefix}"
    input_root.mkdir(parents=True)
    paths = {role: input_root / f"{role}.json" for role in ROLE_SCHEMAS}
    if claim_verification_result_path is not None:
        paths["claim_verification_result"] = claim_verification_result_path
        verification_sha = hashlib.sha256(
            claim_verification_result_path.read_bytes()
        ).hexdigest()
    else:
        verification_sha = _write_json(
            paths["claim_verification_result"],
            values["claim_verification_result"],
        )
    values["claim_verifier_run"] = (
        deepcopy(claim_verifier_run)
        if claim_verifier_run is not None
        else _claim_verifier_run(
            root=tmp_path,
            verification=values["claim_verification_result"],
            verification_path=paths["claim_verification_result"],
            verification_sha256=verification_sha,
        )
    )
    refs: list[StructuredInputRef] = []
    versions = {
        "report_draft": "0.1.0",
        "claim_verification_result": "0.1.0",
        "claim_verifier_run": "0.2.0",
        "review_projection_spec": "0.1.0",
    }
    for index, role in enumerate(ROLE_SCHEMAS, start=1):
        digest = (
            verification_sha
            if role == "claim_verification_result"
            else _write_json(paths[role], values[role])
        )
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{index}",
                role=role,
                schema_ref=ROLE_SCHEMAS[role],
                object_version=versions[role],
                path=paths[role],
                sha256=digest,
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id=f"request-{input_id_prefix}",
        tool_id="P0-11",
        tool_version="0.3.0",
        output_dir=(output_dir or (tmp_path / "output")).resolve(),
        random_seed=random_seed,
        object_inputs=refs,
    )


def _rewrite_role(
    request: ToolRequestV2,
    role: str,
    mutate: Callable[[dict[str, Any]], None],
) -> ToolRequestV2:
    target = next(item for item in request.object_inputs if item.role == role)
    payload = json.loads(target.path.read_text())
    mutate(payload)
    digest = _write_json(target.path, payload)
    return request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(update={"sha256": digest})
                if item.input_id == target.input_id
                else item
                for item in request.object_inputs
            ]
        }
    )


def test_p0_11_is_an_internal_review_projection_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-11")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.name == "Internal Review Projection"
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == (
        "bridge://schemas/contract-validated-review-projection/v0.1"
    )


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_projection_is_internal_review_only_and_binds_exact_verifier_run(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["projection_state"] == "review_required"
    assert run.result["producer_authentication_state"] == "not_available"
    assert run.result["release_authority_state"] == "not_configured"
    assert run.result["distribution_state"] == "internal_review_only"
    assert run.reason_codes == [
        "producer_provenance_unverified",
        "public_release_authority_not_configured",
    ]
    assert run.result["source_accessions"] == ["GSE-DEMO"]
    claim = run.result["claims"][0]
    assert claim["review_claim_id"] == "review-claim:demo"
    assert claim["review_case_label"] == "Demo candidate"
    assert claim["text"] == "configured_metric: 1.2 configured-unit."
    assert claim["value_bindings"] == [
        {
            "binding_index": 0,
            "source_field": "value",
            "canonical_numeric_string": "1.2",
            "raw_unit": "configured-unit",
        }
    ]
    serialized = json.dumps(run.result, sort_keys=True)
    for internal_value in (
        "product-case:demo",
        "claim-block:demo",
        f"evidence:{'a' * 24}",
        "/Users/",
        "/data1/",
    ):
        assert internal_value not in serialized
    assert len(run.artifacts) == 1
    assert run.artifacts[0].kind == "contract_validated_review_projection"


def test_projection_copies_only_selected_claims_without_rewriting_text(
    tmp_path: Path,
) -> None:
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
    spec = payloads["review_projection_spec"]
    spec["source_report_hash"] = payloads["report_draft"]["content_hash"]
    spec["selections"][0]["review_case_label"] = "Alternate label"

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert len(run.result["claims"]) == 1
    assert run.result["claims"][0]["review_case_label"] == "Alternate label"
    assert run.result["claims"][0]["text"] == (
        "configured_metric: 1.2 configured-unit."
    )
    assert "Private unselected prose" not in json.dumps(run.result)


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "private-canary measured 1.2 configured-unit.",
        "/data1/private measured 1.2 configured-unit.",
        "/home/demo-user/private measured 1.2 configured-unit.",
        "~/demo-private measured 1.2 configured-unit.",
        "${HOME}/demo-private measured 1.2 configured-unit.",
        "token:demo-secret measured 1.2 configured-unit.",
        "evidence:private-ref measured 1.2 configured-unit.",
    ],
)
def test_unsafe_review_text_fails_without_artifact(
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
    payloads["review_projection_spec"]["source_report_hash"] = report[
        "content_hash"
    ]

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["review_projection_failed"]
    assert run.result is None and run.artifacts == []
    assert unsafe_text not in json.dumps(run.model_dump(mode="json"))


def test_verified_with_warnings_still_requires_review(tmp_path: Path) -> None:
    run = ToolRegistry.load_default().run(
        _request(tmp_path, payloads=_payloads(warnings=True))
    )

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["projection_state"] == "review_required"
    assert run.reason_codes == [
        "p0_10_verified_with_warnings",
        "producer_provenance_unverified",
        "public_release_authority_not_configured",
    ]


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
            lambda p: (
                p["report_draft"].update({"audience": "internal_research"}),
                p["report_draft"].update(
                    {"content_hash": report_content_hash(p["report_draft"])}
                ),
                p["claim_verification_result"].update(
                    {
                        "report_content_hash": p["report_draft"]["content_hash"],
                        "report_audience": "internal_research",
                    }
                ),
                p["review_projection_spec"].update(
                    {"source_report_hash": p["report_draft"]["content_hash"]}
                ),
            ),
            "report_audience_not_public_candidate",
        ),
        (
            lambda p: p["review_projection_spec"].update(
                {"source_report_hash": "f" * 64}
            ),
            "projection_spec_report_binding_mismatch",
        ),
        (
            lambda p: p["review_projection_spec"].update(
                {"claim_verification_id": f"claim-verification:{'0' * 16}"}
            ),
            "projection_spec_verification_binding_mismatch",
        ),
        (
            lambda p: p["review_projection_spec"].update(
                {"target_language": "zh"}
            ),
            "projection_language_mismatch",
        ),
        (
            lambda p: p["review_projection_spec"]["selections"][0].update(
                {"source_claim_id": "claim-block:missing"}
            ),
            "projection_claim_not_found",
        ),
        (
            lambda p: p["review_projection_spec"].update(
                {"allowed_claim_types": ["availability_claim"]}
            ),
            "projection_claim_type_not_allowed",
        ),
        (
            lambda p: p["review_projection_spec"].update(
                {"allowed_evidence_states": ["inferred"]}
            ),
            "projection_evidence_state_not_allowed",
        ),
    ],
)
def test_cross_binding_failures_are_typed(
    tmp_path: Path,
    mutate: Callable[[dict[str, dict]], None],
    reason: str,
) -> None:
    payloads = _payloads()
    mutate(payloads)
    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert reason in run.reason_codes
    assert run.result is None and run.artifacts == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda run: run["request"].update({"tool_id": "P0-09"}),
        lambda run: run.update({"execution_state": "partial"}),
        lambda run: run.update(
            {"result_schema_ref": "bridge://schemas/other/v0.1"}
        ),
        lambda run: run["result"].update(
            {"verification_id": f"claim-verification:{'0' * 16}"}
        ),
        lambda run: run["artifacts"][0].update({"sha256": "f" * 64}),
        lambda run: run["artifacts"].append(deepcopy(run["artifacts"][0])),
    ],
)
def test_claim_verifier_run_result_and_artifact_must_match_exactly(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    request = _request(tmp_path)
    request = _rewrite_role(request, "claim_verifier_run", mutate)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert "claim_verifier_run_binding_mismatch" in run.reason_codes
    assert run.result is None and run.artifacts == []


def test_projection_spec_strict_boolean_is_not_coerced(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["review_projection_spec"][
        "allow_claims_without_evidence_state"
    ] = "false"
    run = adapter.run(
        _request(tmp_path, payloads=payloads),
        ToolRegistry.load_default().describe("P0-11"),
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]


def test_input_id_renaming_preserves_projection_identity(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = ToolRegistry.load_default().run(request)
    renamed = request.model_copy(
        update={
            "request_id": "request-renamed",
            "object_inputs": [
                item.model_copy(update={"input_id": f"renamed-{index}"})
                for index, item in enumerate(request.object_inputs)
            ],
        }
    )
    second = ToolRegistry.load_default().run(renamed)

    assert first.run_id == second.run_id
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
    request = ToolRequest(
        request_id="v1",
        tool_id="P0-11",
        output_dir=tmp_path.resolve(),
    )
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
    original = adapter_module.build_review_projection

    def mutate_input(**kwargs):
        result = original(**kwargs)
        target.write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(adapter_module, "build_review_projection", mutate_input)
    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.result is None and run.artifacts == []


def test_implementation_contains_no_biological_names_or_thresholds() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(package.glob("*.py"))
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
