from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
from typing import Any

from bridge.tool_packages.p0_10_claim_verifier.models import report_content_hash
from bridge.toolkit.contracts import ExecutionState
from bridge.toolkit.registry import ToolRegistry


def _helpers(filename: str) -> dict[str, Any]:
    return runpy.run_path(str(Path(__file__).with_name(filename)))


def _p0_09_inputs(
    profile: dict[str, Any],
    p0_09: dict[str, Any],
    measurement_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    family_id = profile["deduplicated_evidence_family_ids"][0]
    family_registry = p0_09["_family_registry"]()
    family_registry["families"][0]["evidence_family_id"] = family_id

    candidate = p0_09["_candidate"](family_id=family_id)
    candidate["product_case_ref"] = profile["product_case_ref"]

    bundle = p0_09["_bundle"](candidates=[candidate])
    bundle["product_case_ref"] = profile["product_case_ref"]
    for item in bundle["object_catalog"]:
        if item["node_type"] == "ProductCase":
            item.update(profile["product_case_ref"])
        elif item["node_type"] == "MeasurementResult":
            item.update(profile["measurement_result_refs"][0])
            item["content_hash"] = measurement_sha256
        elif item["node_type"] == "MeasurementSpec":
            item.update(profile["measurement_spec_ref"])
    return bundle, family_registry


def _report_draft(
    record_set: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    evidence_ref = f"{record['evidence_id']}@{record['evidence_version']}"
    rendered_value = "0.75 fraction"
    text = f"target_fraction: {rendered_value}."
    start = text.index(rendered_value)
    payload = {
        "object_version": "0.1.0",
        "report_id": "report:p0-stack-handoff",
        "report_version": "0.1.0",
        "content_hash": "0" * 64,
        "audience": "public_candidate",
        "language": "en",
        "evidence_record_set_ref": (
            f"{record_set['record_set_id']}@{record_set['record_set_version']}"
        ),
        "claim_policy_ref": "claim-policy:p0-10-public@0.1.0",
        "statement_registry_ref": (
            "BRIDGE-STATEMENT-REGISTRY-v0.1@0.1.0"
        ),
        "claim_blocks": [
            {
                "claim_id": "claim-block:p0-stack-handoff",
                "claim_version": "0.1.0",
                "claim_ref": record["claim_ref"]["object_id"]
                + "@"
                + record["claim_ref"]["object_version"],
                "product_case_ref": record["product_case_ref"]["object_id"]
                + "@"
                + record["product_case_ref"]["object_version"],
                "claim_type": "measurement_claim",
                "text": text,
                "language": "en",
                "evidence_refs": [evidence_ref],
                "statement_refs": [],
                "value_bindings": [
                    {
                        "binding_id": "binding:p0-stack-handoff",
                        "source_evidence_ref": evidence_ref,
                        "source_field": "value",
                        "canonical_numeric_string": "0.75",
                        "raw_unit": "fraction",
                        "text_span": [start, start + len(rendered_value)],
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
        "created_at": "2026-08-13T00:00:00Z",
    }
    payload["content_hash"] = report_content_hash(payload)
    return payload


def test_checksummed_p0_08_to_p0_11_contract_chain_stops_at_release_boundary(
    tmp_path: Path,
) -> None:
    p0_08 = _helpers("test_p0_08_evidence_sufficiency.py")
    p0_09 = _helpers("test_p0_09_evidence_compiler.py")
    p0_10 = _helpers("test_p0_10_claim_verifier.py")
    p0_11 = _helpers("test_p0_11_public_export.py")

    handoff_measurement = p0_09["_measurement_result"]()
    handoff_measurement.update(
        {
            "measurement_id": "measurement:target-1",
            "measurement_spec_id": "MS-TARGET-v0.1",
            "measurement_spec_version": "0.1.0",
        }
    )
    sufficiency_run = p0_08["_run"](
        tmp_path / "p0-08", measurement=handoff_measurement
    )
    assert sufficiency_run.execution_state is ExecutionState.SUCCEEDED
    profile = sufficiency_run.result["profiles"][0]
    measurement_input = next(
        ref
        for ref in sufficiency_run.request.object_inputs
        if ref.role == "measurement_result"
    )
    measurement_result = json.loads(
        measurement_input.path.read_text(encoding="utf-8")
    )
    sufficiency_artifact = next(
        artifact
        for artifact in sufficiency_run.artifacts
        if artifact.kind == "evidence_sufficiency_run_result"
    )

    bundle, family_registry = _p0_09_inputs(
        profile, p0_09, measurement_input.sha256
    )
    compiler_run = p0_09["_run"](
        tmp_path / "p0-09",
        profile=profile,
        bundle=bundle,
        family_registry=family_registry,
        sufficiency_result_paths={
            "profile-target": sufficiency_artifact.path,
        },
        measurement_results={"measurement-target": measurement_result},
        measurement_result_paths={"measurement-target": measurement_input.path},
        measurement_result_versions={
            "measurement-target": measurement_input.object_version
        },
    )
    assert compiler_run.execution_state is ExecutionState.SUCCEEDED
    compiler_output = Path(compiler_run.artifacts[0].path).parent
    record_set = json.loads(
        (compiler_output / "evidence_records.json").read_text(encoding="utf-8")
    )
    manifest_path = compiler_output / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = _report_draft(record_set, record_set["records"][0])

    verifier_request = p0_10["_request"](
        tmp_path / "p0-10", report=report
    )
    verifier_request = verifier_request.model_copy(
        update={
            "object_inputs": [
                ref.model_copy(
                    update={
                        "path": manifest_path,
                        "sha256": hashlib.sha256(
                            manifest_path.read_bytes()
                        ).hexdigest(),
                        "object_version": str(manifest["graph_version"]),
                    }
                )
                if ref.role == "evidence_graph_manifest"
                else ref
                for ref in verifier_request.object_inputs
            ]
        }
    )
    verifier_run = ToolRegistry.load_default().run(verifier_request)
    assert verifier_run.execution_state is ExecutionState.SUCCEEDED
    assert verifier_run.result["release_state"] == "release_blocked"
    assert verifier_run.result["public_export_eligibility"] == "ineligible"
    assert "nonformal_evidence_used_for_formal_claim" in {
        item["reason_code"] for item in verifier_run.result["check_records"]
    }
    verification_artifact = next(
        artifact
        for artifact in verifier_run.artifacts
        if artifact.kind == "claim_verification_result"
    )

    review_projection_spec = {
        "object_version": "0.1.0",
        "projection_spec_id": "review-projection-spec:p0-stack-handoff",
        "projection_spec_version": "0.1.0",
        "source_report_ref": "report:p0-stack-handoff@0.1.0",
        "source_report_hash": report["content_hash"],
        "claim_verification_id": verifier_run.result["verification_id"],
        "target_language": "en",
        "allowed_claim_types": ["measurement_claim"],
        "allowed_evidence_states": ["measured"],
        "allow_claims_without_evidence_state": False,
        "selections": [
            {
                "source_claim_id": "claim-block:p0-stack-handoff",
                "review_claim_id": "review-claim:p0-stack-handoff",
                "review_case_label": "Synthetic candidate",
            }
        ],
        "source_accessions": [],
        "prohibited_literals": ["private-canary"],
        "review_policy": "human_review_required",
    }
    projection_run = ToolRegistry.load_default().run(
        p0_11["_request"](
            tmp_path / "p0-11",
            payloads={
                "report_draft": report,
                "claim_verification_result": verifier_run.result,
                "review_projection_spec": review_projection_spec,
            },
            claim_verifier_run=verifier_run.model_dump(mode="json"),
            claim_verification_result_path=verification_artifact.path,
        )
    )
    assert projection_run.execution_state is ExecutionState.FAILED
    assert projection_run.reason_codes == [
        "claim_verification_not_verified_for_review_candidate"
    ]
    assert projection_run.result is None
    assert projection_run.artifacts == []
