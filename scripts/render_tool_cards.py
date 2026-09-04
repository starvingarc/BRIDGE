#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml


# P0-03 through P0-07 and the downstream evidence tools keep detailed
# interface cards as maintained
# source. The generic renderer is intentionally too small for their structured
# object contracts, so regeneration validates those cards instead of replacing
# them with scaffold summaries.
DETAILED_CARD_IDS = {
    "P0-03",
    "P0-04",
    "P0-05",
    "P0-06",
    "P0-07",
    "P0-09",
    "P0-10",
    "P0-11",
    "P0-12",
}


DETAILS = {
    "P0-01": {
        "input": "A declared h5ad, 10x H5, or 10x MTX asset; input level, assay, matrix semantics, complete sample/capture metadata, gene-identifier source, and output location. Three-column 10x MTX uses only explicit Gene Expression rows; legacy two-column feature files remain readable under a recorded all-gene-expression compatibility assumption.",
        "output": "Raw structural and QC metrics, the backward-compatible `QCReadinessProfile`, an additive `QCReadinessProfileV2` bound to an immutable input snapshot, candidate data views, a typed QC visualization data profile and figure-artifact set, a checksummed artifact manifest, and versioned P0-01 structured-output indexes. Complete caller-declared lineage metadata additionally produces biological-unit assignment and manifest artifacts; one analysis unit may span captures only under one coherent independence contract. For count-ready data, typed capture refs must define the same bidirectional observation partition as the row-complete caller-declared capture IDs used by QC/Scrublet, although labels may differ. Invalid, absent, split, or merged lineage remains explicitly unavailable without changing a valid v0.1 result. Declared lineage is not reviewed authority or proof of biological independence.",
        "reject": "Unreadable or ambiguous matrix, unsafe directory entry, duplicate identifiers, invalid count semantics, incomplete/ambiguous feature types in a three-column 10x file, no explicit Gene Expression features in a three-column file, missing assay, incomplete sample values, unsupported MeasurementSpec/input-level pairing, an incomplete declared gene-symbol column, or an output directory nested inside a directory input. Incomplete caller-declared capture values instead disable capture-dependent summaries, doublet evidence, and typed lineage with stable unavailable/reason-code outputs; they do not invalidate an otherwise readable v0.1 QC result.",
        "visualization": "Four static analysis figures report observation retention and analysis eligibility, per-capture QC distributions, library-complexity/mitochondrial relationships and exclusive QC-flag intersections. Figure titles name measured variables and technical scope. Candidate flags never imply that rows were removed; incomplete capture metadata produces an explicit unavailable state rather than a pooled summary.",
        "validation": "Format and mixed-feature fixtures, zero-count semantics, scRNA/snRNA contracts, matrix-semantic failures, snapshot/replacement adversaries, atomic publication and deterministic reuse, declared-lineage fail-soft, multi-capture, and split/merge partition cases, exact data-view/checksum bindings, and optional per-capture Scrublet eligibility.",
        "details": "docs/bridge_spec_v0.1/input_audit_qc_task_card.md",
    },
    "P0-02": {
        "input": "QC-qualified expression views with required `source_family_id` and `qc_profile_ref` asset metadata, a MeasurementSpec reference, declared scRNA/snRNA modality, annotation vocabulary, reference candidates and provenance. The optional V3 handoff resolves the deployment-catalogued P0-01 structured-output index named by `qc_profile_ref`, including checksummed QC V2, biological-unit assignment and manifest artifacts.",
        "output": "Backward-compatible Cell-State evidence plus an optional candidate-only V3 profile bound to the selected data view, MeasurementSpec, vocabulary, reference, QC bytes, typed biological-unit lineage, producer and environment. V3 emits explicit evidence states and denominators; it never emits assigned states or a domain score.",
        "reject": "Reference, vocabulary, MeasurementSpec, assay, data-view or checksum mismatch fails closed. Missing structured-index or typed-lineage inputs leave the legacy run successful but V3 unavailable; no lineage or positive composition is inferred.",
        "visualization": "Prediction-set composition, reference support, method agreement, uncertainty, OOD, and label-provenance views.",
        "validation": "Real P0-01-to-P0-02 typed handoff, checksum and replacement adversaries, selected-view/observation lineage, legacy compatibility, source/lab/modality holdouts, calibration and OOD behavior.",
        "details": "docs/bridge_spec_v0.1/cell_state_annotation_task_card.md",
    },
    "P0-03": {
        "input": "Frozen Cell-State evidence, ProductDefinitionCard, internal ventral-midbrain vocabulary, and eligible reference/spatial evidence.",
        "output": "Separate target-lineage and regional-fidelity raw evidence, conflicts, uncertainty, sensitivity, and applicability state.",
        "reject": "Unconfirmed product target, insufficient reference coverage, unresolved regional vocabulary, or unstable evidence across registered channels.",
        "visualization": "Target and regional composition, reference support, spatial support, evidence conflicts, and method/reference sensitivity.",
        "validation": "Anatomical/source holdouts, OOD regions, marker masking, reference swaps, modality checks, and source-family de-duplication.",
        "details": "docs/bridge_spec_v0.1/target_regional_identity_task_card.md",
    },
    "P0-04": {
        "input": "Confirmed DevelopmentWindowSpec, Cell-State soft composition, fetal references, real in-vitro timepoints, and optional lineage calibration data.",
        "output": "Static or time-course developmental profile, two denominators, window/earlier/later/branch-shift fractions, reference-stage support, and sensitivity.",
        "reject": "Unconfirmed window, single timepoint requested as a trajectory, insufficient replicates for inference, or unsupported fetal-age conversion.",
        "visualization": "Stage composition, real-D timeline, reference-stage support, program trends, sensitivity, and calibration-only lineage alluvial plots.",
        "validation": "Source/timepoint/state holdouts, mixtures, branch shifts, downsampling, modality swaps, and replicate-aware lineage-transition reconstruction.",
        "details": "docs/bridge_spec_v0.1/developmental_compatibility_task_card.md",
    },
    "P0-05": {
        "input": "Checksummed ProductCase, role and assessment objects, P0-02 evidence and, in method mode, reviewed biological-unit lineage, a method spec and unit-level composition/spike-in/OOD inputs.",
        "output": "Whole-product composition plus descriptive intervals, independent-unit bootstrap, hard/soft sensitivity, candidate spike-in limits, single-state at-least-one binomial planning and checksummed-source OOD coordination.",
        "reject": "Missing full-product denominator, partial method inputs, lineage/count mismatch, undeclared reason/state, checksum drift, or zero observations presented as biological absence.",
        "visualization": "No visualization output in v0.3; the package emits checksummed JSON profiles and method records.",
        "validation": "Synthetic execution of all selectors and refusal paths; real OOD holdouts, known mixtures and spike-in calibration remain scientific follow-up.",
        "details": "docs/bridge_spec_v0.1/off_target_control_task_card.md",
    },
    "P0-06": {
        "input": "QC-qualified expression, Cell-State evidence, confirmed developmental context, ProtocolIR metadata, and versioned proliferation/stress-response program knowledge.",
        "output": "State-conditioned proliferation and stress-response evidence, aligned review flags, and optional checksummed MeasurementResultV2 projections for every source record.",
        "reject": "Missing stage context for stage-dependent interpretation, insufficient marker/program coverage, or process attribution without protocol metadata.",
        "visualization": "Program effect profiles, state-stratified distributions, rare-state LOD, process covariates, review flags, and sensitivity.",
        "validation": "Perturbation direction recovery, pluripotent-cell spike-ins, source/cell-line/modality holdouts, program overlap, and false-flag testing.",
        "details": "docs/bridge_spec_v0.1/proliferation_stress_response_task_card.md",
    },
    "P0-07": {
        "input": "Version-matched ProductEvidenceObjects, comparability contract, independent preparation map, domain raw evidence, and Evidence Sufficiency states.",
        "output": "Versioned ComparisonRecord with comparability mode, deltas, effect sizes, intervals, stability, Pareto state, and sensitivity evidence.",
        "reject": "Contract mismatch, complete protocol/lab/batch confounding, absent independent preparation, or inferential claims from descriptive-only data.",
        "visualization": "Effect-size forest, composition differences, timelines, batch distances, program heatmaps, Pareto matrix, and integration sensitivity.",
        "validation": "Known shifts and nulls, paired/unpaired designs, insufficient replication, over-correction checks, and independent-versus-joint consistency.",
        "details": "docs/bridge_spec_v0.1/product_comparison_stability_task_card.md",
    },
    "P0-08": {
        "input": "A `ToolRequestV2` with empty assets and parameters, one checksummed candidate GateRuleSpec v0.2 bound to ReasonCodeCatalog v0.2, one to five DomainGateInput v0.1 bindings, MeasurementSpecV2/QCReadinessProfileV2/MeasurementResultV2 objects, and their versioned validation, prior and sensitivity records.",
        "output": "One canonical `EvidenceSufficiencyRunResultV2`, one canonical public v0.2 profile JSON per domain as a P0-09-ready producer handoff, a noncanonical convenience wrapper, gate trace, case summary, typed visualization data, three complete TSV fallbacks, three SVG/PNG/PDF figure sets, an artifact set and a checksummed bundle manifest. The run result and manifest retain path-free source bindings; profiles retain their versioned domain references and `domain_score=null`. P0-09 acceptance of v0.2 remains a separate tool-package change.",
        "reject": "Wrong roles, Schema IDs, object versions, logical bindings, checksums, candidate gate bytes, unsafe references, changed inputs or drifted bundles fail with stable reason codes and no scientific result. A bound MeasurementResult whose MeasurementSpec version disagrees, or a populated QC MeasurementSpec version that disagrees, is ineligible. Missing, unknown or unavailable measurement states, or absent paired upstream ToolRun provenance, instead execute as `not_assessed`; negative and alert remain distinct and never become pass/fail.",
        "visualization": "Three static, table-backed figures show the four domain-scoped evidence axes, root interpretation requirements, and all eight MeasurementResult states. Counts remain domain-profile references rather than independent evidence; requirement records never invent source-to-reason edges. Oversized static views defer to the complete typed table without top-N truncation.",
        "validation": "Interpretation remains conditional on the bound MeasurementSpec, declared method context, reference/prior context and current candidate gate rules. A favorable axis state is not a product-quality, safety, efficacy or release conclusion, and formal family-level proof remains unavailable for P0-09.",
        "details": "docs/bridge_spec_v0.1/evidence_sufficiency_task_card.md",
    },
    "P0-10": {
        "input": "Structured ReportDraft, a verified P0-09 Case graph manifest, ClaimBlocks, one-field numeric spans, statement references, and policy versions.",
        "output": "One ClaimVerificationResult receipt binding the ReportDraft, P0-09 graph manifest, checks, audience, export eligibility and release state.",
        "reject": "Numeric mismatch, invalid evidence, state substitution, unsupported inference, prohibited claim, graft leakage, or prose outside package-owned reconstruction.",
        "visualization": "No visualization output in v0.1; deterministic checks retain claim IDs and relevant text spans.",
        "validation": "Graph integrity, semantic Claim/ProductCase binding, exact numeric spans, bilingual prohibited claims, private metadata, immutable hashes, and blocker non-override.",
        "details": "docs/bridge_spec_v0.1/claim_verifier_task_card.md",
    },
    "P0-11": {
        "input": "Exactly four checksummed JSON objects: ReportDraft v0.1, eligible ClaimVerificationResult v0.1, PublicExportPolicySpec v0.1 and PublicExportRequest v0.1.",
        "output": "Three checksummed JSON artifacts: an allowlist-rebuilt PublicSafeReport, PublicExportManifest and PublicExportResult with a confirmation-bound candidate hash.",
        "reject": "Receipt, report, audience, policy or channel mismatch; missing public alias; non-allowlisted statement; checksum drift; leak canary; confirmation mismatch; or unsafe output path.",
        "visualization": "None in v0.2.0. This first implementation is JSON-only and does not copy or regenerate figures.",
        "validation": "Candidate and confirmed reruns, exact input bindings, allowlist projection, path/credential/email/internal-ref canaries, deterministic reuse and V1 refusal.",
        "details": "docs/bridge_spec_v0.1/public_safe_export_task_card.md",
    },
    "P0-12": {
        "input": "No objects; three checksummed precomputed graft objects; or five checksummed objects binding a GraftCase, H5AD asset, analysis spec, reference panel and marker-program collection.",
        "output": "An independent not-provided/descriptive result, or one-declared-graft all-row soft composition, aggregation-matched sample-profile reference support and external marker-program means from the declared H5AD.",
        "reject": "Schema, checksum, file, matrix, probability, biological-unit, aggregation, method-set or cross-object drift fails closed; expression mode requires one declared graft, animal and timepoint.",
        "visualization": "No visualization output in v0.3.0.",
        "validation": "Synthetic H5AD and JSON fixtures exercise single-graft binding, file reading, shared matrix validation, probability non-repair, raw-count pseudobulk and log-normalized sample-mean semantics, external-context binding, deterministic output and no score backfill.",
        "details": "docs/bridge_spec_v0.1/graft_assessment_task_card.md",
    },
}


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    environment_specs = yaml.safe_load(
        (repo / "environments/index.yaml").read_text(encoding="utf-8")
    )["environment_specs"]
    spec_dir = repo / "src" / "bridge" / "tool_packages" / "specs"
    card_dir = repo / "src" / "bridge" / "tool_packages" / "cards"
    for spec_path in sorted(spec_dir.glob("*.yaml")):
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        tool_id = spec["tool_id"]
        card_path = card_dir / f"{tool_id}.md"
        if tool_id in DETAILED_CARD_IDS:
            text = card_path.read_text(encoding="utf-8")
            environment_state = environment_specs[spec["environment_spec_id"]][
                "state"
            ]
            _validate_detailed_card(text, spec, environment_state)
        else:
            text = render(spec, DETAILS[tool_id])
        card_path.write_text(text, encoding="utf-8")
    return 0


def _validate_detailed_card(text: str, spec: dict, environment_state: str) -> None:
    required_fragments = (
        f"# {spec['tool_id']} {spec['name']}",
        f"| Package version | `{spec['version']}` |",
        f"| Runtime state | `{spec['implementation_state']}` |",
        f"| Scientific state | `{spec['scientific_status']}` |",
        f"| EnvironmentSpec | `{spec['environment_spec_id']}` (`{environment_state}`) |",
        f"| Input envelope | `{spec['input_schema_ref']}` |",
        f"| Output envelope | `{spec['output_schema_ref']}` |",
        f"| Result schema | `{spec['result_schema_ref']}` |",
        f"| Adapter | `{spec['adapter_ref']}` |",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    if missing:
        raise ValueError(
            f"detailed Tool Card for {spec['tool_id']} is stale: {missing}"
        )


def render(spec: dict, detail: dict) -> str:
    if spec["implementation_state"] != "implemented":
        runtime = "Discoverable contract only; `run` returns `not_implemented` without scientific results."
    elif spec["tool_id"] == "P0-08":
        runtime = (
            "Executable candidate; reads versioned upstream evidence objects and emits no "
            "measurements or domain score. Example commands: `bridge-tool validate --request "
            "examples/requests/p0_08_evidence_sufficiency.json` and `bridge-tool run --request "
            "examples/requests/p0_08_evidence_sufficiency.json`."
        )
    else:
        runtime = "Executable candidate; it emits raw measurements and never emits a domain score."
    optional = "yes" if spec.get("optional") else "no"
    is_cell_state = spec["tool_id"] == "P0-02"
    biology = """## Biological purpose

Test whether a pre-transplant product supports reviewed fetal ventral-midbrain cell
states while leaving unrelated neural and non-neural cells unresolved.

## Current biological status

- Broad fetal VM states can be explored in donor-held-out internal scRNA-seq data.
- Fine RG/Nb-derived states remain provisional because marker and external-source
  support are incomplete.
- Current inductive methods force cortical, motor-neuron, neural-crest and
  mesenchymal out-of-reference / out-of-distribution (OOD) controls into known
  fetal VM labels.
- Formal target, regional-fidelity and off-target composition conclusions are
  therefore unavailable.

Pseudobulk reference correlation is a reference-similarity summary, not
replicate-aware differential-expression inference. Marker/program evidence is a
complementary channel rather than an independent source because its curation
lineage overlaps the internal annotation.

No state or method is frozen. The next scientific step is review of the 25 state
definitions and marker cards, followed by locked external-source and OOD testing.

""" if is_cell_state else ""
    purpose_heading = "## Tool purpose" if is_cell_state else "## Purpose"
    freeze_row = "| Freeze state | `biological_review_in_progress` |\n" if is_cell_state else ""
    method_selection = (
        "\n\n**Method selection:** No method is selected while this package remains a scaffold."
        if spec["implementation_state"] == "scaffold"
        else ""
    )
    validation_boundary = (
        "\n\nThe unsealed scRNA pilot is complete. No state or method is frozen; biological review, signed gates and locked testing remain required."
        if is_cell_state
        else ""
    )
    method_documentation = (
        f"Method documentation and accessible sources do not constitute benchmark completion. The registered method IDs are returned by `bridge-tool describe {spec['tool_id']}`."
        if spec["method_ids"]
        else "Method documentation and accessible sources do not constitute benchmark completion. No method is registered or selected until benchmark-bound execution exists."
    )
    return f"""# {spec['tool_id']} {spec['name']}

{biology}{purpose_heading}

{spec['summary']}

## Contract

| Field | Value |
|---|---|
| Package version | `{spec['version']}` |
| Runtime state | `{spec['implementation_state']}` |
| Scientific state | `{spec['scientific_status']}` |
{freeze_row}| Optional | `{optional}` |
| EnvironmentSpec | `{spec['environment_spec_id']}` |
| Input schema | `{spec['input_schema_ref']}` |
| Output schema | `{spec['output_schema_ref']}` |

**Input:** {detail['input']}

**Output:** {detail['output']}

**Runtime behavior:** {runtime}{method_selection}

## Refusal Conditions

{detail['reject']}

Missing, unknown, unavailable, negative, and alert states remain distinct. No package may infer a clinical, safety, potency, GMP-release, or absolute product-ranking claim.

## Visualization Contract

{detail['visualization']}

Every formal chart must retain its data version, denominator, units, evidence references, and missing-state semantics.

## Validation Before Freeze

{detail['validation']}

{method_documentation}{validation_boundary}

## Detailed Scientific Requirement

Repository document: `{detail['details']}`.
"""


if __name__ == "__main__":
    raise SystemExit(main())
