"""Validated M1 write contracts; identities and accepted editions are server-owned."""
from datetime import date
import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from .sessions import uid

ObjectID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Revision = Annotated[int, Field(strict=True, ge=1)]
Day = Annotated[int, Field(strict=True, ge=0, le=3660)]
Name = Annotated[str, Field(min_length=1, max_length=160)]
Note = Annotated[str, Field(max_length=2000)]


def calendar_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid_calendar_date")
    date.fromisoformat(value)
    return value


DateText = Annotated[str, AfterValidator(calendar_date)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)

    @field_validator("*")
    @classmethod
    def text_controls(cls, value):
        if isinstance(value, str) and re.search(r"[\x00-\x08\x0b-\x1f\x7f]", value):
            raise ValueError("invalid_text")
        return value


class Mutation(Body):
    expected_version: Revision


class Creation(Body):
    expected_version: Annotated[int, Field(strict=True, ge=0, le=0)]


class Citation(Body):
    title: Name
    doi: Annotated[str, Field(min_length=1, max_length=256)] | None = None


class ProtocolCreate(Creation):
    name: Name | None = None
    origin: Literal["lab", "literature"] | None = None
    citation: Citation | None = None
    material_id: ObjectID | None = None

    @model_validator(mode="after")
    def source(self):
        if self.material_id:
            if self.name is not None or self.origin is not None or self.citation is not None:
                raise ValueError("protocol_creation_source_conflict")
        elif self.name is None or self.origin is None:
            raise ValueError("protocol_identity_required")
        return self


class Stage(Body):
    index: Annotated[int, Field(strict=True, ge=1, le=4)]
    start_day: Day
    end_day: Day

    @model_validator(mode="after")
    def window(self):
        if self.end_day < self.start_day:
            raise ValueError("invalid_stage_window")
        return self


class FieldProvenance(Body):
    field: Literal["dose_text", "start_day", "end_day"]
    kind: Literal["direct", "recipe_reference"]
    source_ref: Annotated[str, Field(min_length=1, max_length=500)]
    source_locator: Annotated[str, Field(min_length=1, max_length=500)]
    recipe_locator: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    @model_validator(mode="after")
    def referenced_recipe(self):
        if self.kind == "recipe_reference" and self.recipe_locator is None:
            raise ValueError("recipe_locator_required")
        return self


class SourceReview(Mutation):
    note: Annotated[str, Field(min_length=1, max_length=2000)]


class Reagent(Body):
    id: ObjectID = Field(default_factory=uid)
    name: Name
    short: Annotated[str, Field(min_length=1, max_length=80)]
    pathway: Literal["smad", "wnt", "fgf", "shh", "notch", "maturation", "other"]
    kind: Literal["molecule", "protein", "supplement"]
    dose_text: Annotated[str, Field(max_length=256)]
    start_day: Day | None
    end_day: Day | None
    catalog_id: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    unconfirmed: list[Literal["name", "short", "pathway", "kind", "dose_text", "start_day",
                            "end_day", "catalog_id", "source_locator"]] = Field(default_factory=list, max_length=9)
    source_locator: Annotated[str, Field(max_length=500)] | None = None
    timing_text: Note = ""
    field_provenance: list[FieldProvenance] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def window(self):
        if self.start_day is not None and self.end_day is not None and self.end_day < self.start_day:
            raise ValueError("invalid_reagent_window")
        if len({entry.field for entry in self.field_provenance}) != len(self.field_provenance):
            raise ValueError("duplicate_field_provenance")
        if any(getattr(self, entry.field) in (None, "") for entry in self.field_provenance):
            raise ValueError("unknown_field_provenance")
        return self


class Operation(Body):
    day: Day | None
    kind: Literal["feed", "passage", "sample", "freeze", "other"]
    note: Note = ""
    timing_text: Note = ""
    source_locator: Annotated[str, Field(max_length=500)] | None = None


ReviewFields = list[Literal["source_review", "total_days", "stages", "operations"]]


class ProtocolContent(Body):
    unconfirmed: ReviewFields = Field(default_factory=list, max_length=4)
    change_note: Note = ""
    total_days: Day | None = None
    stages: list[Stage] = Field(default_factory=list, max_length=4)
    reagents: list[Reagent] = Field(default_factory=list, max_length=256)
    operations: list[Operation] = Field(default_factory=list, max_length=512)

    @field_validator("total_days")
    @classmethod
    def unknown_duration(cls, value):
        return None if value == 0 else value

    @model_validator(mode="after")
    def timeline(self):
        stages = sorted(self.stages, key=lambda s: s.start_day)
        if (len({s.index for s in stages}) != len(stages)
                or any(a.end_day >= b.start_day or a.index >= b.index for a, b in zip(stages, stages[1:]))):
            raise ValueError("invalid_stage_order")
        if len({r.id for r in self.reagents}) != len(self.reagents):
            raise ValueError("duplicate_reagent_id")
        if self.total_days and (
            any(s.end_day > self.total_days for s in stages)
            or any(day is not None and day > self.total_days
                   for r in self.reagents for day in (r.start_day, r.end_day))
            or any(o.day is not None and o.day > self.total_days for o in self.operations)
        ):
            raise ValueError("protocol_window_outside_duration")
        return self


class ProtocolChanges(Body):
    unconfirmed: ReviewFields | None = Field(default=None, max_length=4)
    change_note: Note | None = None
    total_days: Day | None = None
    stages: list[Stage] | None = Field(default=None, max_length=4)
    reagents: list[Reagent] | None = Field(default=None, max_length=256)
    operations: list[Operation] | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def no_explicit_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set - {"total_days"}):
            raise ValueError("protocol_field_cannot_be_null")
        return self


class ProtocolPatch(ProtocolChanges, Mutation):
    @model_validator(mode="after")
    def has_changes(self):
        if self.model_fields_set == {"expected_version"}:
            raise ValueError("protocol_changes_required")
        return self


class VersionCreate(Mutation):
    based_on_version_id: ObjectID
    changes: ProtocolChanges = Field(default_factory=ProtocolChanges)


RunState = Literal["planned", "expanding", "differentiating", "frozen", "grafted", "ended"]


class Graft(Body):
    date: DateText
    host: Name
    site: Name


class RunCreate(Creation):
    purpose: Literal["execution", "retrospective"] = "execution"
    protocol_version_id: ObjectID
    name: Name
    cell_line: Name | None = None
    start_date: DateText | None = None
    state: RunState
    graft: Graft | None = None


class RunPatch(Mutation):
    state: RunState | None = None
    start_date: DateText | None = None
    graft: Graft | None = None

    @model_validator(mode="after")
    def changes(self):
        if self.model_fields_set == {"expected_version"} or ("state" in self.model_fields_set and self.state is None):
            raise ValueError("run_changes_required")
        return self


class MappingInput(Body):
    matrix_location: Annotated[str, Field(pattern=r"^(X|layers/[A-Za-z0-9_.-]{1,80})$")]
    matrix_semantics: Literal["raw_counts"]
    sample_context: Literal["pre_graft", "post_graft"]
    source_family_id: Annotated[Name, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
    capture_id: Name | None = None
    capture_id_column: Name | None = None
    gene_symbol_column: Name | None = None

    @model_validator(mode="after")
    def capture_declaration(self):
        if self.capture_id is not None and self.capture_id_column is not None:
            raise ValueError("capture_declaration_conflict")
        return self


class MappingStart(Mutation):
    mapping_input: MappingInput | None = None


class SampleCreate(Mutation):
    day: Day
    collected_on: DateText | None = None
    mapping_input: MappingInput | None = None
    assay: Literal["scRNA-seq", "snRNA-seq"]
    material_id: ObjectID | None = None


class SamplePatch(Mutation):
    material_id: ObjectID
    mapping_input: MappingInput | None = None


class Decision(Body):
    expected_version: Revision | None = None

    @model_validator(mode="after")
    def no_null_revision(self):
        if "expected_version" in self.model_fields_set and self.expected_version is None:
            raise ValueError("expected_version_required")
        return self


class LeadCreate(Body):
    run_id: ObjectID
    sample_id: ObjectID | None = None
    chain_level: Annotated[int, Field(strict=True, ge=0, le=4)] | None = None
    summary: Annotated[str, Field(min_length=1, max_length=2000)]
    created_by: Literal["agent", "system"]


class LeadPatch(Mutation):
    status: Literal["resolved", "dismissed"]
