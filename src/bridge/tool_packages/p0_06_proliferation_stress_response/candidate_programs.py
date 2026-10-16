"""Source-defined expression summaries without product/stage qualification."""
from __future__ import annotations

import hashlib
import csv
import json
import math
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, RootModel, StrictInt, field_validator, model_validator

from bridge.toolkit.contracts import DataViewBinding, FrozenModel
from bridge.tool_packages._configurable_contracts import observation_ids_sha256
from bridge.tool_packages._structured_runtime import read_regular_bytes, strict_json_loads
from .exploratory_models import ExploratoryProcessProfile, ExploratoryProgramSummary
from .method_models import MethodExecutionRecord, ProcessMethodId
from .models import SafeId, Sha256, PublishedRef, _aware_utc, ProliferationStressResponseProfileV3

INPUT_SCHEMA = "bridge://schemas/exploratory-process-input/v0.2"
PROFILE_SCHEMA = "bridge://schemas/exploratory-program-profile/v0.1"
RESULT_SCHEMA = "bridge://schemas/proliferation-stress-response-result/v0.2"
DIRECTED_INPUT_SCHEMA = "bridge://schemas/exploratory-process-input/v0.3"
DIRECTED_PROFILE_SCHEMA = "bridge://schemas/exploratory-program-profile/v0.2"
DIRECTED_RESULT_SCHEMA = "bridge://schemas/proliferation-stress-response-result/v0.3"


class ProgramResourceBinding(FrozenModel):
    resource_ref: PublishedRef
    resource_version: str = Field(min_length=1)
    source_family_id: SafeId
    path: Path
    sha256: Sha256
    source_url: str = Field(pattern=r"^https://\S+$")
    license_ref: str = Field(min_length=1)
    format: Literal["msigdb_hallmark_json"]


class CandidateProgramSelection(FrozenModel):
    program_id: SafeId
    source_gene_set: str = Field(pattern=r"^HALLMARK_[A-Z0-9_]+$")


class ExploratoryProgramInput(FrozenModel):
    object_version: Literal["0.2.0"]
    input_id: SafeId
    source_family_id: SafeId
    data_view: DataViewBinding
    gene_symbol_column: str | None = Field(default=None, min_length=1)
    resource: ProgramResourceBinding
    programs: list[CandidateProgramSelection] = Field(min_length=1, max_length=50)
    gene_coverage_policy: Literal["complete_only", "observed_subset"]
    created_at: datetime

    @model_validator(mode="after")
    def unique_program_bindings(self) -> Self:
        for values in ([p.program_id.lower() for p in self.programs], [p.source_gene_set for p in self.programs]):
            if len(values) != len(set(values)):
                raise ValueError("program identifiers and source gene sets must be unique")
        return self

    _created_at_utc = field_validator("created_at")(_aware_utc)


class ProgramParameters(FrozenModel):
    scanpy_ctrl_size: Literal[50] = 50
    scanpy_n_bins: Literal[25] = 25
    scanpy_ctrl_as_ref: Literal[True] = True
    decoupler_tmin: Literal[5] = 5
    random_seed: StrictInt
    use_raw: Literal[False] = False
    layer: None = None
    decoupler_empty: Literal[False] = False
    lower_quantile: Literal[0.1] = 0.1
    upper_quantile: Literal[0.9] = 0.9


class DirectedResourceBinding(ProgramResourceBinding):
    format: Literal["hu_pluripotency_csv", "oflanagan_core_csv"]


class DirectedProgramSelection(CandidateProgramSelection):
    source_gene_set: SafeId


class DirectedProgramInput(ExploratoryProgramInput):
    object_version: Literal["0.3.0"]
    resource: DirectedResourceBinding
    # Each original CSV defines one source set; never relabel it as Hallmark.
    programs: list[DirectedProgramSelection] = Field(min_length=1, max_length=1)


class SourceProgramMember(FrozenModel):
    source_member_id: str = Field(min_length=1)
    gene_symbol: str | None
    direction: Literal[-1, 1]
    unresolved_reason: Literal["source_gene_symbol_missing"] | None = None


class ScoredProgramTarget(FrozenModel):
    source_member_id: str
    gene_symbol: str
    feature_id: str
    direction: Literal[-1, 1]


class CandidateProgramSummary(ExploratoryProgramSummary):
    program_id: SafeId
    source_gene_set: str
    gene_symbols_sha256: Sha256
    observed_gene_symbols: list[str]
    gene_coverage_fraction: float = Field(ge=0.0, le=1.0)
    signature_scope: Literal["complete", "observed_feature_subset", "not_estimable"]

    @model_validator(mode="after")
    def measurement_state_is_coherent(self) -> Self:
        values = (self.mean, self.median, self.lower_quantile, self.upper_quantile)
        if self.assessment_state == "available":
            if any(v is None or not math.isfinite(v) for v in values) or self.reason_codes or self.ambiguous_genes:
                raise ValueError("available scores need finite values and unambiguous features")
            expected_scope = "observed_feature_subset" if self.missing_genes else "complete"
            if self.signature_scope != expected_scope:
                raise ValueError("signature scope must disclose missing features")
        elif any(v is not None for v in values) or not self.reason_codes or self.signature_scope != "not_estimable":
            raise ValueError("unassessed scores require null values, scope and reasons")
        if self.observed_gene_count + len(self.missing_genes) + len(self.ambiguous_genes) != self.declared_gene_count:
            raise ValueError("gene coverage denominator mismatch")
        if len(set(self.observed_gene_symbols)) != self.observed_gene_count:
            raise ValueError("observed gene identity/count mismatch")
        if self.gene_coverage_fraction != self.observed_gene_count / self.declared_gene_count:
            raise ValueError("gene coverage fraction mismatch")
        expected_unit = ("scanpy_control_adjusted_expression" if self.method_id == "PROC-SCORE-SCANPY"
                         else "decoupler_ulm_t_value")
        if self.score_unit != expected_unit:
            raise ValueError("score unit must match the native method")
        if self.assessment_state == "available" and self.lower_quantile > self.upper_quantile:
            raise ValueError("descriptive quantiles must be ordered")
        return self


class ExploratoryProgramProfile(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    runtime_mode: Literal["exploratory_programs"] = "exploratory_programs"
    profile_id: SafeId
    tool_id: Literal["P0-06"] = "P0-06"
    tool_version: str
    input_sha256: Sha256
    expression_asset_sha256: Sha256
    input_contract: ExploratoryProgramInput
    method_parameters: ProgramParameters
    normalization_recipe: Literal["normalize_total_10000_log1p", "declared_normalized_expression"]
    evidence_family_id: SafeId
    n_observations: StrictInt = Field(gt=0)
    n_features: StrictInt = Field(gt=0)
    target_feature_ids: dict[str, str]
    independence_state: Literal["unknown"] = "unknown"
    n_independent_replicates: None = None
    interpretation_scope: Literal["descriptive_only"] = "descriptive_only"
    score_state: Literal["unavailable"] = "unavailable"
    domain_score: None = None
    executions: list[MethodExecutionRecord]
    program_summaries: list[CandidateProgramSummary]
    limitations: list[SafeId]
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @model_validator(mode="after")
    def summaries_match_request(self) -> Self:
        expected = {(p.program_id, method): p.source_gene_set
                    for p in self.input_contract.programs
                    for method in ("PROC-SCORE-SCANPY", "PROC-SCORE-DECOUPLER")}
        actual = {(s.program_id, s.method_id): s.source_gene_set for s in self.program_summaries}
        if actual != expected or len(actual) != len(self.program_summaries):
            raise ValueError("summaries must match every requested program and method exactly once")
        if any(s.n_observations != self.n_observations for s in self.program_summaries):
            raise ValueError("summary observation count mismatch")
        if self.n_observations != self.input_contract.data_view.n_observations:
            raise ValueError("profile data-view observation count mismatch")
        if self.expression_asset_sha256 != self.input_contract.data_view.sha256:
            raise ValueError("profile expression hash mismatch")
        return self


class DirectedProgramSummary(CandidateProgramSummary):
    source_members: list[SourceProgramMember]
    unresolved_members: list[SourceProgramMember]
    scored_targets: list[ScoredProgramTarget]
    scored_targets_sha256: Sha256
    direction_definition: Literal["candidate_membership_plus_one", "sign_of_source_logFC"]

    @model_validator(mode="after")
    def measurement_state_is_coherent(self) -> Self:
        # Reuse the old numerical/method checks with unresolved IDs represented as
        # missing only inside validation. Public fields retain the distinction.
        base = self.model_dump(exclude={"source_members", "unresolved_members", "scored_targets",
                                      "scored_targets_sha256", "direction_definition"})
        base["missing_genes"] += [m.source_member_id for m in self.unresolved_members]
        CandidateProgramSummary.model_validate(base)
        if len(self.source_members) != self.declared_gene_count:
            raise ValueError("source membership denominator mismatch")
        if self.unresolved_members != [m for m in self.source_members if m.gene_symbol is None]:
            raise ValueError("unresolved source membership mismatch")
        expected = [m.gene_symbol for m in self.source_members if m.gene_symbol in self.observed_gene_symbols]
        if expected != self.observed_gene_symbols:
            raise ValueError("observed source membership mismatch")
        target_symbols = [t.gene_symbol for t in self.scored_targets]
        if target_symbols != (self.observed_gene_symbols if self.assessment_state == "available" else []):
            raise ValueError("scored targets must bind only actual available scores")
        members = {m.source_member_id: m for m in self.source_members}
        if any(t.source_member_id not in members or t.gene_symbol != members[t.source_member_id].gene_symbol
               or t.direction != members[t.source_member_id].direction for t in self.scored_targets):
            raise ValueError("scored target direction/source mismatch")
        if self.scored_targets_sha256 != _targets_digest(self.scored_targets):
            raise ValueError("scored target checksum mismatch")
        return self


class DirectedProgramProfile(ExploratoryProgramProfile):
    object_version: Literal["0.2.0"] = "0.2.0"
    input_contract: DirectedProgramInput
    program_summaries: list[DirectedProgramSummary]


def _targets_digest(targets):
    return hashlib.sha256(json.dumps([t.model_dump(mode="json") for t in targets],
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class ProliferationStressResponseResultV2(RootModel[
    ProliferationStressResponseProfileV3 | ExploratoryProcessProfile | ExploratoryProgramProfile
]):
    pass


class ProliferationStressResponseResultV3(RootModel[
    ProliferationStressResponseProfileV3 | ExploratoryProcessProfile | ExploratoryProgramProfile | DirectedProgramProfile
]):
    pass


PUBLIC_SCHEMA_MODELS = {INPUT_SCHEMA: ExploratoryProgramInput, PROFILE_SCHEMA: ExploratoryProgramProfile,
                        RESULT_SCHEMA: ProliferationStressResponseResultV2,
                        DIRECTED_INPUT_SCHEMA: DirectedProgramInput,
                        DIRECTED_PROFILE_SCHEMA: DirectedProgramProfile,
                        DIRECTED_RESULT_SCHEMA: ProliferationStressResponseResultV3}


def load_program_resource(source):
    from .method_runtime import ProcessMethodError

    try:
        raw = read_regular_bytes(source.resource.path)
    except (OSError, ValueError) as exc:
        raise ProcessMethodError("program_resource_unreadable") from exc
    if hashlib.sha256(raw).hexdigest() != source.resource.sha256:
        raise ProcessMethodError("program_resource_checksum_mismatch")
    try:
        if isinstance(source, DirectedProgramInput):
            members = []
            for i, row in enumerate(csv.DictReader(StringIO(raw.decode("utf-8-sig")))):
                if source.resource.format == "hu_pluripotency_csv":
                    symbol, member_id, direction = row["external_gene.x"], f"row:{i+1}", 1
                else:
                    symbol, member_id = row["gene_symbol"], row["ensembl_gene_id"]
                    value = float(row["logFC"])
                    if not math.isfinite(value) or value == 0:
                        raise ValueError("nonfinite or zero source direction")
                    direction = 1 if value > 0 else -1
                symbol = None if symbol in ("", "NA") else symbol
                if symbol is not None and any(c.isspace() for c in symbol):
                    raise ValueError("invalid source symbol")
                members.append(SourceProgramMember(source_member_id=member_id, gene_symbol=symbol,
                    direction=direction, unresolved_reason="source_gene_symbol_missing" if symbol is None else None))
            ids = [m.source_member_id for m in members]
            symbols = [m.gene_symbol for m in members if m.gene_symbol is not None]
            if not members or len(ids) != len(set(ids)) or len(symbols) != len(set(symbols)):
                raise ValueError("empty or duplicate source membership")
            return {source.programs[0].program_id: members}
        payload = strict_json_loads(raw)
        result = {}
        for selection in source.programs:
            row = payload[selection.source_gene_set]
            genes = row["geneSymbols"]
            if (row["collection"] != "H" or not isinstance(genes, list) or not genes
                    or any(not isinstance(g, str) or not g or any(c.isspace() for c in g) for g in genes)
                    or len(genes) != len(set(genes))):
                raise ValueError("invalid source membership")
            result[selection.program_id] = genes
    except (ValueError, KeyError, TypeError) as exc:
        raise ProcessMethodError("program_resource_membership_invalid") from exc
    return result


def measure_candidate_programs(*, source, asset, tool_version, input_sha256, run_id, random_seed):
    import numpy as np
    import pandas as pd
    from .exploratory import native_scanpy_scores, native_ulm_scores
    from .method_runtime import ProcessMethodError, _execution, _package_versions, load_expression_matrix

    programs = load_program_resource(source)
    directed = isinstance(source, DirectedProgramInput)
    members = programs if directed else {}
    if directed:
        programs = {p: [m.gene_symbol for m in rows if m.gene_symbol is not None] for p, rows in members.items()}
    adata = load_expression_matrix(asset=asset, gene_symbol_column=None)
    obs = adata.obs_names.astype(str).tolist()
    if len(obs) != source.data_view.n_observations or observation_ids_sha256(obs) != source.data_view.observation_ids_sha256:
        raise ProcessMethodError("expression_observation_set_mismatch")
    if source.gene_symbol_column is None:
        symbols = adata.var_names.astype(str).tolist()
    else:
        if source.gene_symbol_column not in adata.var:
            raise ProcessMethodError("gene_symbol_column_missing")
        column = adata.var[source.gene_symbol_column]
        if column.isna().any():
            raise ProcessMethodError("gene_symbols_invalid")
        symbols = column.astype(str).tolist()
    if any(not g or any(c.isspace() for c in g) for g in symbols):
        raise ProcessMethodError("gene_symbols_invalid")
    by_symbol = {}
    for feature, symbol in zip(adata.var_names, symbols, strict=True):
        by_symbol.setdefault(symbol, []).append(str(feature))
    mapping, coverage, blocked = {}, {}, {}
    for program, genes in programs.items():
        missing = sorted(set(genes) - by_symbol.keys())
        ambiguous = sorted(g for g in genes if len(by_symbol.get(g, [])) > 1)
        observed = [g for g in genes if len(by_symbol.get(g, [])) == 1]
        mapping.update({g: by_symbol[g][0] for g in observed})
        coverage[program] = (observed, missing, ambiguous)
        blocked[program] = ("program_gene_identifier_ambiguous" if ambiguous else
            "program_gene_coverage_insufficient" if len(observed) < 5 or
            ((missing or (directed and any(m.gene_symbol is None for m in members[program])))
             and source.gene_coverage_policy == "complete_only") else None)
    params = ProgramParameters(random_seed=random_seed)
    scores, errors = {}, {}
    for program, (observed, _, _) in coverage.items():
        if directed and any(m.direction < 0 for m in members[program]):
            errors[(program, "PROC-SCORE-SCANPY")] = "scanpy_signed_signature_not_supported"
            continue
        if blocked[program]:
            continue
        try:
            scores[(program, "PROC-SCORE-SCANPY")] = native_scanpy_scores(
                adata, [mapping[g] for g in observed], score_name=f"scanpy_{program}", params=params)
        except Exception:
            errors[(program, "PROC-SCORE-SCANPY")] = "scanpy_score_genes_failed"
    weights = {(p, m.gene_symbol): float(m.direction) for p, rows in members.items() for m in rows}
    net = [{"source": program, "target": mapping[g], "weight": weights.get((program, g), 1.0)}
           for program, (observed, _, _) in coverage.items() if not blocked[program] for g in observed]
    if net:
        try:
            activities = native_ulm_scores(adata, net, params=params)
            for program in programs:
                if not blocked[program]:
                    if program in activities:
                        scores[(program, "PROC-SCORE-DECOUPLER")] = activities[program].to_numpy()
                    else:
                        errors[(program, "PROC-SCORE-DECOUPLER")] = "decoupler_program_output_missing"
        except Exception:
            for program in programs:
                errors[(program, "PROC-SCORE-DECOUPLER")] = "decoupler_ulm_failed"
    rows = pd.DataFrame({"observation_id": obs})
    summaries = []
    for selection in source.programs:
        program = selection.program_id
        observed, missing, ambiguous = coverage[program]
        for method in ("PROC-SCORE-SCANPY", "PROC-SCORE-DECOUPLER"):
            reason = errors.get((program, method)) or blocked[program]
            values = scores.get((program, method))
            if values is not None and (values.shape != (len(obs),) or not np.isfinite(values).all()):
                reason = "method_scores_nonfinite_or_misaligned"
            available = values is not None and not reason
            rows[f"{method}:{program}"] = values if available else np.nan
            unresolved = [m for m in members.get(program, []) if m.gene_symbol is None]
            targets = [ScoredProgramTarget(source_member_id=m.source_member_id, gene_symbol=m.gene_symbol,
                        feature_id=mapping[m.gene_symbol], direction=m.direction)
                       for m in members.get(program, []) if available and m.gene_symbol in observed]
            declared = len(members[program]) if directed else len(programs[program])
            extra = dict(source_members=members[program], unresolved_members=unresolved,
                         scored_targets=targets, scored_targets_sha256=_targets_digest(targets),
                         direction_definition="candidate_membership_plus_one" if source.resource.format == "hu_pluripotency_csv"
                         else "sign_of_source_logFC") if directed else {}
            summaries.append((DirectedProgramSummary if directed else CandidateProgramSummary)(
                **extra,
                program_id=program, method_id=method, source_gene_set=selection.source_gene_set,
                gene_symbols_sha256=hashlib.sha256(("\n".join(programs[program])+"\n").encode()).hexdigest(),
                observed_gene_symbols=observed, signature_scope=("observed_feature_subset" if missing or unresolved else "complete") if available else "not_estimable",
                n_observations=len(obs), observed_gene_count=len(observed), declared_gene_count=declared,
                gene_coverage_fraction=len(observed)/declared,
                missing_genes=missing, ambiguous_genes=ambiguous,
                score_unit="scanpy_control_adjusted_expression" if method == "PROC-SCORE-SCANPY" else "decoupler_ulm_t_value",
                assessment_state="available" if available else "not_assessed", reason_codes=[] if available else [reason or "method_output_unavailable"],
                **(dict(mean=float(values.mean()),median=float(np.median(values)),
                        lower_quantile=float(np.quantile(values,0.1)),upper_quantile=float(np.quantile(values,0.9))) if available else {}),
            ))
    versions = _package_versions()
    profile = (DirectedProgramProfile if directed else ExploratoryProgramProfile)(
        profile_id=f"exploratory-programs:{run_id.removeprefix('run-')}",tool_version=tool_version,
        input_sha256=input_sha256,expression_asset_sha256=asset.checksum,input_contract=source,method_parameters=params,
        normalization_recipe="normalize_total_10000_log1p" if asset.matrix_semantics == "raw_counts" else "declared_normalized_expression",
        evidence_family_id="evidence-family:query-" + hashlib.sha256(json.dumps({"sha256":source.data_view.parent_asset_sha256},sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24],
        n_observations=len(obs),n_features=adata.n_vars,target_feature_ids=mapping,
        program_summaries=summaries,created_at=source.created_at,
        executions=[_execution(ProcessMethodId(method),sum(s.assessment_state=="available" for s in summaries if s.method_id==method),
                    [r for s in summaries if s.method_id==method for r in s.reason_codes],versions)
                    for method in ("PROC-SCORE-SCANPY","PROC-SCORE-DECOUPLER")],
        limitations=["source_defined_candidate_not_product_validated","observed_subset_not_complete_signature",
                     "same_query_rna_not_independent_evidence","quantiles_not_confidence_intervals",
                     "different_method_units_not_combined","no_activation_fraction_or_stage_assignment",
                     "no_potency_safety_or_release_assessment","qc_not_reassessed"],
    )
    output=BytesIO();rows.to_parquet(output,index=False)
    return profile,output.getvalue()
