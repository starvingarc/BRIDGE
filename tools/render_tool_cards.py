#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml


DETAILS = {
    "P0-01": {
        "input": "A declared h5ad, 10x H5, or 10x MTX asset; input level, assay, matrix semantics, sample/capture metadata, gene-identifier source, and output location.",
        "output": "Raw structural and QC metrics, `QCReadinessProfile`, candidate data views when a candidate MeasurementSpec is selected, visualizations, and a checksummed artifact manifest.",
        "reject": "Unreadable or ambiguous matrix, duplicate identifiers, invalid count semantics, missing assay, missing required sample/capture information, unsupported MeasurementSpec/input-level pairing, an incomplete declared gene-symbol column, or an output directory nested inside a directory input.",
        "visualization": "Per-sample QC distributions and counts-versus-detected-genes diagnostics with explicit denominators.",
        "validation": "Format fixtures, scRNA/snRNA contracts, matrix-semantic failures, deterministic reruns, input immutability, and optional Scrublet eligibility.",
        "details": "docs/bridge_v2_spec_v0.1/input_audit_qc_task_card.md",
    },
    "P0-02": {
        "input": "QC-qualified expression views, declared scRNA/snRNA modality, internal annotation vocabulary, frozen reference candidates, and provenance.",
        "output": "Hierarchical prediction sets, soft assignments, uncertainty, method disagreement, unknown reasons, and product-level composition evidence.",
        "reject": "Reference or vocabulary mismatch, absent required genes, unresolved modality shift, or no method combination passing the state-axis benchmark.",
        "visualization": "Prediction-set composition, reference support, method agreement, uncertainty, OOD, and label-provenance views.",
        "validation": "Source/lab/modality holdouts, leave-one-state-out, rare-state mixtures, calibration, OOD detection, and product-composition error.",
        "details": "docs/bridge_v2_spec_v0.1/cell_state_annotation_task_card.md",
    },
    "P0-03": {
        "input": "Frozen Cell-State evidence, ProductDefinitionCard, internal ventral-midbrain vocabulary, and eligible reference/spatial evidence.",
        "output": "Separate target-lineage and regional-fidelity raw evidence, conflicts, uncertainty, sensitivity, and applicability state.",
        "reject": "Unconfirmed product target, insufficient reference coverage, unresolved regional vocabulary, or unstable evidence across registered channels.",
        "visualization": "Target and regional composition, reference support, spatial support, evidence conflicts, and method/reference sensitivity.",
        "validation": "Anatomical/source holdouts, OOD regions, marker masking, reference swaps, modality checks, and source-family de-duplication.",
        "details": "docs/bridge_v2_spec_v0.1/target_regional_identity_task_card.md",
    },
    "P0-04": {
        "input": "Confirmed DevelopmentWindowSpec, Cell-State soft composition, fetal references, real in-vitro timepoints, and optional lineage calibration data.",
        "output": "Static or time-course developmental profile, two denominators, window/earlier/later/branch-shift fractions, reference-stage support, and sensitivity.",
        "reject": "Unconfirmed window, single timepoint requested as a trajectory, insufficient replicates for inference, or unsupported fetal-age conversion.",
        "visualization": "Stage composition, real-D timeline, reference-stage support, program trends, sensitivity, and calibration-only lineage alluvial plots.",
        "validation": "Source/timepoint/state holdouts, mixtures, branch shifts, downsampling, modality swaps, and replicate-aware lineage-transition reconstruction.",
        "details": "docs/bridge_v2_spec_v0.1/developmental_compatibility_task_card.md",
    },
    "P0-05": {
        "input": "Frozen Cell-State prediction sets, ProductDefinitionCard role table, eligible-cell denominator, and rare-state/OOD calibration records.",
        "output": "Whole-product soft composition, role-resolved non-target evidence, unknown reasons, rare-state detection limits, and sensitivity.",
        "reject": "Missing full-product denominator, unresolved product role, uncalibrated OOD method, or a zero observation presented as biological absence.",
        "visualization": "Whole-product composition, off-axis drill-down, unknown reasons, OOD calibration, rare-state LOD/UCB, and method sensitivity.",
        "validation": "Real OOD panels, source-family holdouts, known mixtures, rare-state spike-ins, downsampling, and reference/preprocessing swaps.",
        "details": "docs/bridge_v2_spec_v0.1/off_target_control_task_card.md",
    },
    "P0-06": {
        "input": "QC-qualified expression, Cell-State evidence, confirmed developmental context, ProtocolIR metadata, and versioned process-program knowledge.",
        "output": "State-conditioned program evidence, residual-pluripotency LOD, cycling identity, confounding record, and transcriptomic review flags.",
        "reject": "Missing stage context for stage-dependent interpretation, insufficient marker/program coverage, or process attribution without protocol metadata.",
        "visualization": "Program effect profiles, state-stratified distributions, rare-state LOD, process covariates, review flags, and sensitivity.",
        "validation": "Perturbation direction recovery, pluripotent-cell spike-ins, source/cell-line/modality holdouts, program overlap, and false-flag testing.",
        "details": "docs/bridge_v2_spec_v0.1/process_integrity_task_card.md",
    },
    "P0-07": {
        "input": "Version-matched ProductEvidenceObjects, comparability contract, independent preparation map, domain raw evidence, and Evidence Sufficiency states.",
        "output": "Versioned ComparisonRecord with comparability mode, deltas, effect sizes, intervals, stability, Pareto state, and sensitivity evidence.",
        "reject": "Contract mismatch, complete protocol/lab/batch confounding, absent independent preparation, or inferential claims from descriptive-only data.",
        "visualization": "Effect-size forest, composition differences, timelines, batch distances, program heatmaps, Pareto matrix, and integration sensitivity.",
        "validation": "Known shifts and nulls, paired/unpaired designs, insufficient replication, over-correction checks, and independent-versus-joint consistency.",
        "details": "docs/bridge_v2_spec_v0.1/product_comparison_stability_task_card.md",
    },
    "P0-08": {
        "input": "QCReadinessProfile, domain MeasurementResults, benchmark and sensitivity records, and frozen reference/prior/contract versions.",
        "output": "Per-domain EvidenceSufficiencyProfile across data readiness, model robustness, and prior applicability, with deterministic reason codes.",
        "reject": "Missing gate specification, absent required upstream record, non-applicable method/prior, or unstable evidence needed for interpretation.",
        "visualization": "Three-axis sufficiency matrix, blocking reasons, domain state summary, and upstream evidence trace.",
        "validation": "Independent domain gating, missing-state semantics, evidence-family de-duplication, legacy-score exclusion, and deterministic repeatability.",
        "details": "docs/bridge_v2_spec_v0.1/evidence_sufficiency_task_card.md",
    },
    "P0-09": {
        "input": "MeasurementResults, ToolRuns, Evidence Sufficiency, versioned contracts, references, priors, and artifact manifests.",
        "output": "Atomic EvidenceRecords, immutable Case/Comparison Evidence Graph projections, and deterministic reconciliation states.",
        "reject": "Invalid schema, dangling provenance, duplicate logical evidence, forbidden lifecycle/tier, or LLM-authored numeric/reconciliation changes.",
        "visualization": "Claim neighborhood, provenance, evidence-family grouping, conflicts, missing requirements, and comparison subgraphs.",
        "validation": "Idempotence, append-only correction, family de-duplication, missing-versus-zero semantics, graph round trips, and read-only Agent access.",
        "details": "docs/bridge_v2_spec_v0.1/evidence_compiler_task_card.md",
    },
    "P0-10": {
        "input": "Structured ReportDraft, ClaimBlocks, ValueBindings, evidence/knowledge/statement references, chart artifacts, and policy versions.",
        "output": "ClaimVerificationResult and immutable VerifiedReport reference with blockers, warnings, traceability map, and release state.",
        "reject": "Numeric mismatch, invalid evidence, state substitution, unsupported inference, prohibited claim, graft leakage, or unresolved semantic review.",
        "visualization": "Claim-to-evidence map, check results, blocked text spans, chart-binding status, and human-review queue.",
        "validation": "Exact value copying, bilingual fixtures, prohibited claims, chart bindings, LLM failure, immutable report hashes, and blocker non-override.",
        "details": "docs/bridge_v2_spec_v0.1/claim_verifier_task_card.md",
    },
    "P0-11": {
        "input": "VerifiedReport with eligible export state, field allowlist, public aliases, registered visualizations, and export policy version.",
        "output": "New PublicSafeReport candidate, regenerated public figures, file manifest, checksums, scan results, and confirmation-bound package hash.",
        "reject": "Any non-allowlisted field, private path or identifier, unsafe embedded content, unregistered file, hash drift, or missing user confirmation.",
        "visualization": "Public-data payload only; figures are regenerated and checked for metadata, scripts, links, hidden text, and tooltip leakage.",
        "validation": "Leakage canaries, public accession preservation, CSV injection, MIME mismatch, archive traversal, media metadata, and deterministic packaging.",
        "details": "docs/bridge_v2_spec_v0.1/public_safe_export_task_card.md",
    },
    "P0-12": {
        "input": "Optional GraftCase with explicit host/model/animal/timepoint/species/preparation linkage plus modality-matched fetal references.",
        "output": "Independent GraftAssessment, whole-graft composition, fetal/mDA support, maturation evidence, sensitivity, and optional descriptive linkage record.",
        "reject": "No graft returns `not_provided`; missing animal IDs or confounded designs force descriptive mode; implicit preparation linkage is forbidden.",
        "visualization": "Whole-graft composition, mDA/reference support, maturation programs, animal/timepoint variation, sensitivity, and linkage Evidence Graph.",
        "validation": "Metadata contracts, source/lab/modality holdouts, mixtures, species contamination, downsampling, reference swaps, and no score backfill.",
        "details": "docs/bridge_v2_spec_v0.1/graft_assessment_task_card.md",
    },
}


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    spec_dir = repo / "src" / "bridge" / "tool_packages" / "specs"
    card_dir = repo / "src" / "bridge" / "tool_packages" / "cards"
    for spec_path in sorted(spec_dir.glob("*.yaml")):
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        tool_id = spec["tool_id"]
        detail = DETAILS[tool_id]
        text = render(spec, detail)
        (card_dir / f"{tool_id}.md").write_text(text, encoding="utf-8")
        package_dir = repo / "tool_packages" / tool_id
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "README.md").write_text(text, encoding="utf-8")
    return 0


def render(spec: dict, detail: dict) -> str:
    runtime = (
        "Executable candidate; it emits raw measurements and never emits a domain score."
        if spec["implementation_state"] == "implemented"
        else "Discoverable contract only; `run` returns `not_implemented` without scientific results."
    )
    optional = "yes" if spec.get("optional") else "no"
    return f"""# {spec['tool_id']} {spec['name']}

## Purpose

{spec['summary']}

## Contract

| Field | Value |
|---|---|
| Package version | `{spec['version']}` |
| Runtime state | `{spec['implementation_state']}` |
| Scientific state | `{spec['scientific_status']}` |
| Optional | `{optional}` |
| EnvironmentSpec | `{spec['environment_spec_id']}` |
| Input schema | `{spec['input_schema_ref']}` |
| Output schema | `{spec['output_schema_ref']}` |

**Input:** {detail['input']}

**Output:** {detail['output']}

**Runtime behavior:** {runtime}

## Refusal Conditions

{detail['reject']}

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

{detail['visualization']}

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

{detail['validation']}

Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe {spec['tool_id']}`.

## Detailed Scientific Requirement

Repository document: `{detail['details']}`.
"""


if __name__ == "__main__":
    raise SystemExit(main())
