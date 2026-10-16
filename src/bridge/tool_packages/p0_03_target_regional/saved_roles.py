"""Explicit product roles over a checked, non-overlapping saved partition."""
from typing import Literal
from pydantic import Field, RootModel, model_validator
from bridge.toolkit.contracts import FrozenModel
from bridge.tool_packages._configurable_contracts import ProductRole
from bridge.tool_packages.p0_05_off_target_control.native_models import NativeWholeProductContextProfile
from .exploratory_models import TargetRegionalResult

class SavedRoleRecord(FrozenModel):
    record_id: str
    state_id: str | None
    count: int = Field(ge=0)
    denominator: int = Field(gt=0)
    product_role: ProductRole
    source_refs: list[str]
    reason_code: str | None

class SavedTargetRoleProfile(NativeWholeProductContextProfile):
    object_version: Literal["0.1.0"] = "0.1.0"
    tool_id: Literal["P0-03"] = "P0-03"
    role_records: list[SavedRoleRecord]
    role_counts: dict[ProductRole, int]
    role_judgement_state: Literal["complete", "partial", "not_assessed"]
    target_fraction: float | None = Field(default=None,ge=0,le=1)
    state_role_map_ref: str | None
    state_role_map_sha256: str | None
    product_definition_ref: str | None
    product_definition_sha256: str | None
    regional_fidelity_fraction: None = None

    @model_validator(mode="after")
    def role_partition_matches(self):
        if len(self.role_records)!=len(self.whole_product_composition):
            raise ValueError("role_partition_mismatch")
        for role,row in zip(self.role_records,self.whole_product_composition):
            if (role.record_id,role.state_id,role.count,role.denominator)!=(row.record_id,row.state_id,row.count,row.whole_product_denominator):
                raise ValueError("role_partition_mismatch")
        counts={role:sum(r.count for r in self.role_records if r.product_role==role) for role in ProductRole}
        if counts!=self.role_counts:
            raise ValueError("role_counts_mismatch")
        unresolved=counts[ProductRole.ROLE_UNRESOLVED]
        expected="complete" if unresolved==0 else ("not_assessed" if unresolved==self.data_view.n_observations else "partial")
        if self.role_judgement_state!=expected:
            raise ValueError("role_judgement_state_mismatch")
        fraction=counts[ProductRole.TARGET]/self.data_view.n_observations if unresolved==0 else None
        if self.target_fraction!=fraction:
            raise ValueError("unresolved_roles_cannot_produce_purity")
        return self

class TargetRegionalResultV2(RootModel[TargetRegionalResult | SavedTargetRoleProfile]):
    pass

PUBLIC_SCHEMA_MODELS = {
    "bridge://schemas/saved-target-role-profile/v0.1": SavedTargetRoleProfile,
    "bridge://schemas/target-regional-result/v0.2": TargetRegionalResultV2,
}

def account_roles(rows, denominator, decisions, assignments, reviewed):
    """Map a checked partition to reviewed roles without inheriting parent roles.

    Rows and assignments are JSON forms of the existing typed contracts. Unknown
    mass stays in the whole-view denominator and makes target_fraction null.
    This pure calculation neither loads sources nor changes their review status.
    """
    if denominator<=0 or sum(r["count"] for r in rows)!=denominator:
        raise ValueError("whole_product_counts_not_conserved")
    records=[]
    counts={r.value:0 for r in ProductRole}
    for row in rows:
        state=row["state_id"]
        assignment=assignments.get(state)
        reason=("state_identity_unresolved" if state is None or row["record_kind"]!="state"
            else "state_role_review_required" if not reviewed
            else "source_definition_parent_only" if decisions.get(state)=="parent_only"
            else "source_definition_unavailable" if decisions.get(state)!="evaluate"
            else "state_role_missing" if assignment is None
            else "state_role_unresolved" if assignment["product_role"]=="role_unresolved"
            else "state_role_sources_required" if not assignment["source_refs"]
            else None)
        role=assignment["product_role"] if reason is None else "role_unresolved"
        counts[role]+=row["count"]
        records.append(dict(record_id=row["record_id"],state_id=state,count=row["count"],
            denominator=denominator,product_role=role,
            source_refs=assignment["source_refs"] if assignment else [],reason_code=reason))
    unresolved=counts["role_unresolved"]
    return dict(role_records=records,role_counts=counts,
        role_judgement_state="complete" if not unresolved else ("not_assessed" if unresolved==denominator else "partial"),
        target_fraction=None if unresolved else counts["target"]/denominator)
