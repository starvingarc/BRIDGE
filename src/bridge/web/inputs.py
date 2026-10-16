"""Private, contract-driven input binding. Scientific values remain caller-owned."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import math
import re
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field
from referencing import Registry as SchemaRegistry

from bridge.tool_packages._expression_contracts import EXPLORATION_SPEC, ExpressionAnalysis
from bridge.domain import CaseInputAsset, CaseInputBundle
from bridge.toolkit.contracts import StructuredInputRef, ToolRequest, ToolRequestV2
from bridge.toolkit.schemas import load_schema

OBJECT_LIMIT = 2 * 1024 * 1024
SESSION_OBJECT_LIMIT = 512
GRAPH_SCHEMAS = {
    "bridge://schemas/case-evidence-graph-manifest/v0.1",
    "bridge://schemas/comparison-evidence-graph-manifest/v0.1",
}
P006_SOURCE_BOUND_METADATA = (
    "P0-06",
    "method_runtime_source_bound",
    "process_method_input",
    "bridge://schemas/process-method-input/v0.2",
    "0.2.0",
)
P006_SOURCE_ARTIFACTS = {
    ("source_observations", "artifact_manifest_path"): (
        "artifact_manifest_sha256",
        "manifest",
    ),
    ("source_observations", "evidence_path"): (
        "evidence_sha256",
        "cell_state_evidence",
    ),
}


class InputBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectChoice(InputBody):
    role: str = Field(max_length=100)
    input_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Selection(InputBody):
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    mode_id: str | None
    asset_ids: list[str] = Field(max_length=8)
    # A five-domain gate can reference every registered measurement in a case.
    # Keep selection bounded by the existing registration budget, without truncation.
    object_inputs: list[ObjectChoice] = Field(max_length=SESSION_OBJECT_LIMIT)
    measurement_spec_ref: str | None = Field(max_length=200)
    expression_analysis: ExpressionAnalysis | None = None


class AssetDeclaration(InputBody):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    assay: str = Field(max_length=100)
    matrix_location: str = Field(max_length=100)
    matrix_semantics: str = Field(max_length=100)
    input_level: str = Field(max_length=100)
    metadata: dict = Field(default_factory=dict)


class PrepareAnalysis(InputBody):
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")


def strict_json(data: bytes, limit=OBJECT_LIMIT) -> dict:
    if len(data) > limit:
        raise ValueError("object_size_limit")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("non_finite_json")
    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid_json") from exc
    def check(item, depth=0):
        if depth > 32:
            raise ValueError("json_depth_limit")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("non_finite_json")
        if isinstance(item, dict):
            for child in item.values():
                check(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                check(child, depth + 1)
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    check(value)
    return value


def _checked_path(service, state, path, root=None):
    root = Path(root or service.directory(state["id"]))
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("input_path_invalid")
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError("input_outside_session") from None
    current = root
    if current.is_symlink():
        raise ValueError("input_symlink")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("input_symlink")
    return path


@contextmanager
def checked_file(service, state, path, expected, root=None, limit=128 * 1024 * 1024):
    from .sessions import open_private_file
    path = _checked_path(service, state, path, root)
    with open_private_file(path, limit) as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("input_integrity_mismatch")
        stream.seek(0)
        yield stream


def verify_checked_file(service, state, path, expected, root=None, limit=128 * 1024 * 1024):
    with checked_file(service, state, path, expected, root=root, limit=limit):
        pass


def integrity_limit(service, path, default=128 * 1024 * 1024):
    return service.settings.max_upload_bytes if Path(path).suffix.lower() == ".h5ad" else default


def checked_bytes(service, state, path, expected, root=None, limit=128 * 1024 * 1024):
    from .sessions import open_private_file
    path = _checked_path(service, state, path, root)
    with open_private_file(path, limit) as stream:
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("input_integrity_mismatch")
    return data


def _verification_operation(method):
    """Share receipt checks only within one synchronous input operation."""
    @wraps(method)
    def verified(self, state, *args, **kwargs):
        with self.verification(state):
            return method(self, state, *args, **kwargs)
    return verified


class Inputs:
    def __init__(self, service):
        self.service = service
        self._verification_context = ContextVar("input_verification", default=None)

    @contextmanager
    def verification(self, state):
        """Reuse producer checks while reading one session state synchronously.

        Nested calls for the same state share checks; exit always discards them.
        Keep artifacts immutable and do not await or start workers inside this
        scope. Object bytes, canonical bindings and invalidation are still checked
        on each use; failures retain the original verification error semantics.
        """
        current = self._verification_context.get()
        if current is not None and current[0] is state:
            yield
            return
        token = self._verification_context.set((state, {}))
        try:
            yield
        finally:
            self._verification_context.reset(token)

    def initialize(self, state):
        state.setdefault("_input_objects", {})
        state.setdefault("_input_selections", {})
        state.setdefault("_asset_declarations", {})
        state.setdefault("_canonical_artifacts", {})
        state.setdefault("_indexed_input_receipts", [])

    def contract_mode(self, tool_id, mode_id):
        contract = self.service.registry.describe_input(tool_id)
        modes = contract.object_input_modes
        mode = next((item for item in modes if item.mode_id == mode_id), None)
        if mode_id is not None and mode is None:
            raise ValueError("unknown_input_mode")
        return contract, mode

    def role(self, tool_id, mode_id, name, schema_ref, version):
        contract, mode = self.contract_mode(tool_id, mode_id)
        if mode is None:
            raise ValueError("input_mode_required")
        role = next((item for item in mode.roles if item.role == name), None)
        if role is None:
            raise ValueError("unknown_input_role")
        if schema_ref not in role.schema_refs:
            raise ValueError("input_schema_mismatch")
        if not version or len(version) > 200 or (role.object_version_policy == "fixed" and version not in role.object_versions):
            raise ValueError("input_version_mismatch")
        fixed = self.schema_version(schema_ref)
        if fixed is not None and version != fixed:
            raise ValueError("input_version_mismatch")
        return role

    def schema_version(self, schema_ref):
        """Resolve a fixed object version, not a dependency or graph revision."""
        properties = load_schema(schema_ref).get("properties", {})
        primary = {key: value for key, value in properties.items() if key in {"object_version", "version"}}
        fields = primary or {key: value for key, value in properties.items() if key.endswith("_version")}
        declared = {value["const"] for value in fields.values() if isinstance(value.get("const"), str)}
        if len(declared) > 1:
            raise ValueError("ambiguous_object_version")
        if declared:
            return declared.pop()
        # Some published payloads (QC, cell-state, MeasurementResult) have no
        # object version field. Their current role contract owns that version.
        fixed = {version for spec in self.service.registry.list()
                 for mode in self.service.registry.describe_input(spec.tool_id).object_input_modes
                 for role in mode.roles if schema_ref in role.schema_refs and role.object_version_policy == "fixed"
                 for version in role.object_versions}
        return next(iter(fixed)) if len(fixed) == 1 else None

    def object_version(self, payload, schema_ref):
        schema = load_schema(schema_ref)
        # Match the exact packaged Schema before resolving its version. No remote retrieval.
        if not Draft202012Validator(schema, registry=SchemaRegistry()).is_valid(payload):
            raise ValueError("input_schema_validation_failed")
        fixed = self.schema_version(schema_ref)
        properties = schema.get("properties", {})
        primary = {field for field in ("object_version", "version") if field in properties}
        values = {payload.get(field, properties[field].get("default")) for field in primary}
        if fixed is not None:
            values.add(fixed)
        elif not primary and schema_ref in GRAPH_SCHEMAS:
            values.add(str(payload["graph_version"]))
        if len(values) != 1:
            raise ValueError("input_version_mismatch")
        version = values.pop()
        if not isinstance(version, str) or not version or len(version) > 200:
            raise ValueError("input_version_mismatch")
        return version

    def validate_object(self, payload, schema_ref, version):
        if self.object_version(payload, schema_ref) != version:
            raise ValueError("input_version_mismatch")

    def receipt_artifacts(self, state, record):
        if record["receipt_file"] in state.get("_invalidated_receipts", {}):
            raise ValueError("input_revision_invalidated_output")
        return self._verified_receipt_artifacts(state, record)

    def historical_artifact_source_kind(self, state, record):
        """Read a verified source kind for display; never make an invalidated output reusable."""
        artifacts = self._verified_receipt_artifacts(state, record)
        return artifacts[record["artifact_id"]].get("kind")

    def _verified_receipt_artifacts(self, state, record):
        context = self._verification_context.get()
        verified_receipts = context[1] if context is not None and context[0] is state else None
        root = self.service.directory(state["id"])
        receipt = next((item for item in state["_tool_runs"] if item["file"] == record["receipt_file"]
                        and item["sha256"] == record["receipt_sha256"]), None)
        if receipt is None:
            raise ValueError("canonical_receipt_missing")
        key = (receipt["file"], receipt["sha256"], receipt["tool_id"])
        artifacts = verified_receipts.get(key) if verified_receipts is not None else None
        if artifacts is None:
            raw = checked_bytes(self.service, state, root / "receipts" / receipt["file"], receipt["sha256"])
            run = strict_json(raw, 128 * 1024 * 1024)
            if run["request"]["tool_id"] != receipt["tool_id"] or run["execution_state"] not in {"succeeded", "partial"}:
                raise ValueError("canonical_receipt_invalid")
            artifacts = {}
            for item in run["artifacts"]:
                verify_checked_file(
                    self.service,
                    state,
                    item["path"],
                    item["sha256"],
                    root / "runs",
                    integrity_limit(self.service, item["path"]),
                )
                artifacts[item["artifact_id"]] = item
            if verified_receipts is not None:
                verified_receipts[key] = artifacts
        artifact = artifacts.get(record["artifact_id"])
        if artifact is None or artifact["path"] != record["path"] or artifact["sha256"] != record["sha256"]:
            raise ValueError("canonical_artifact_mismatch")
        return artifacts

    @_verification_operation
    def verify(self, state, record):
        # Keep payload, revision and binding checks on every use. Only the full
        # producer artifact scan is shared within this operation; it is discarded
        # before another request, execution phase, session, or thread can use it.
        for identifier, sha256 in record.get("derivation_inputs", {}).items():
            dependency = state["_input_objects"].get(identifier)
            if dependency is None or dependency["sha256"] != sha256:
                raise ValueError("derived_source_binding_changed")
            self.verify(state, dependency)
        if record["source"] == "tool_output":
            self.receipt_artifacts(state, record)
        root = self.verify_system_resource(state, record) if record["source"] == "system_resource" else None
        data = checked_bytes(self.service, state, record["path"], record["sha256"], root=root, limit=OBJECT_LIMIT)
        payload = strict_json(data)
        self.validate_object(payload, record["schema_ref"], record["object_version"])
        for dependency in record.get("dependencies", []):
            if dependency.get("artifact_id"):
                self.receipt_artifacts(state, dependency)
            verify_checked_file(
                self.service,
                state,
                dependency["path"],
                dependency["sha256"],
                limit=integrity_limit(self.service, dependency["path"]),
            )
        return payload

    def reference_resources(self, state):
        """Enumerate only the server-configured P0-02 reference; never accept a root from a browser."""
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
        from bridge.tool_packages.p0_02_cell_state.reference import resolve_reference_snapshot, validate_reference_snapshot, validate_runtime_reference
        from .sessions import read_file
        import os
        ref = self.service.settings.cell_state_measurement_spec_ref
        if not ref:
            return None, []
        spec = load_measurement_spec(ref)
        if spec is None:
            raise ValueError("measurement_spec_not_found")
        configured = Path(os.environ.get("BRIDGE_REFERENCE_ROOT", "")).expanduser()
        for component in [configured, *configured.parents]:
            if component.is_symlink():
                raise ValueError("reference_symlink")
        root = resolve_reference_snapshot(spec.reference_refs[0])
        # Check all components before any scientific loader reads a descriptor.
        for component in [root, *root.parents]:
            if component.is_symlink():
                raise ValueError("reference_symlink")
        manifest_path = root / "reference_manifest.json"
        manifest_data = read_file(manifest_path, OBJECT_LIMIT)
        payload = strict_json(manifest_data)
        self.validate_object(payload, "bridge://schemas/reference-manifest/v0.1", payload["version"])
        dependencies = []
        for item in [payload, *payload["profiles"]]:
            for key, value in item.items():
                if key.endswith("_file") and value is not None:
                    relative = Path(value)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("reference_path_invalid")
                    checksum = item[key.removesuffix("_file") + "_sha256"]
                    path = root / relative
                    verify_checked_file(
                        self.service,
                        state,
                        path,
                        checksum,
                        root=root,
                        limit=integrity_limit(self.service, path),
                    )
                    dependencies.append({"path": str(path), "sha256": checksum})
        manifest = validate_reference_snapshot(root)
        validate_runtime_reference(manifest)
        from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CANDIDATE_SPEC, AUXILIARY_SPEC
        reference_spec = AUXILIARY_SPEC if spec.measurement_spec_id == CANDIDATE_SPEC else spec.measurement_spec_id
        if reference_spec not in manifest.measurement_spec_ids:
            raise ValueError("measurement_spec_not_supported_by_reference")
        vocabulary_path = root / manifest.vocabulary_file
        vocabulary_data = checked_bytes(self.service, state, vocabulary_path, manifest.vocabulary_sha256, root=root, limit=OBJECT_LIMIT)
        resources = []
        for label, path, data, schema_ref in (
            ("reference_manifest", manifest_path, manifest_data, "bridge://schemas/reference-manifest/v0.1"),
            ("annotation_vocabulary", vocabulary_path, vocabulary_data, "bridge://schemas/annotation-vocabulary/v0.1"),
        ):
            value = strict_json(data)
            version = value.get("object_version", value.get("version"))
            self.validate_object(value, schema_ref, version)
            resources.append({"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "label": label,
                "schema_ref": schema_ref, "object_version": version, "source": "system_resource",
                "producer_tool_id": None, "system_root": str(root), "system_dependencies": dependencies})
        return root, resources

    def verify_system_resource(self, state, record):
        root, resources = self.reference_resources(state)
        current = next((item for item in resources if item["path"] == record["path"]), None)
        if current != record:
            raise ValueError("system_resource_binding_changed")
        return root

    def bind_nested(self, state, payload, named_artifacts=None):
        dependencies = []
        named_artifacts = named_artifacts or {}
        bound_named = {}

        def canonical_artifact(value, expected_kind):
            if not isinstance(value, str):
                raise ValueError("opaque_artifact_reference_required")
            kind, sep, identifier = value.partition(":")
            if not sep or kind != "artifact":
                raise ValueError("opaque_artifact_reference_required")
            dependency = state["_canonical_artifacts"].get(identifier)
            if dependency is None:
                raise ValueError("unknown_nested_artifact")
            artifacts = self.receipt_artifacts(state, dependency)
            artifact = artifacts[dependency["artifact_id"]]
            if artifact["kind"] != expected_kind:
                raise ValueError("canonical_artifact_kind_mismatch")
            return dependency

        def walk(item, trail=()):
            if isinstance(item, list):
                return [walk(child, trail) for child in item]
            if not isinstance(item, dict):
                return item
            result = {}
            for key, value in item.items():
                location = trail + (key,)
                named = named_artifacts.get(location)
                locator = key == "path" or key.endswith(("_path", "_file")) or key in {"output_dir"}
                if named is not None and value is not None:
                    checksum_field, expected_kind = named
                    dependency = canonical_artifact(value, expected_kind)
                    if checksum_field not in item:
                        raise ValueError("nested_checksum_required")
                    supplied_checksum = item[checksum_field]
                    if (
                        supplied_checksum is not None
                        and supplied_checksum != ""
                        and supplied_checksum != dependency["sha256"]
                    ):
                        raise ValueError("nested_checksum_mismatch")
                    result[checksum_field] = dependency["sha256"]
                    result[key] = dependency["path"]
                    dependencies.append(dict(dependency))
                    bound_named[location] = dependency
                elif locator and value is not None:
                    if key != "path" or not isinstance(value, str):
                        raise ValueError("unsupported_file_binding:" + key)
                    kind, sep, identifier = value.partition(":")
                    if not sep or kind not in {"upload", "artifact"}:
                        raise ValueError("opaque_file_reference_required")
                    if kind == "upload":
                        upload = state["_uploads"].get(identifier)
                        if upload is None:
                            raise ValueError("unknown_nested_upload")
                        dependency = {"path": str(self.service.directory(state["id"]) / "uploads" / (identifier + ".h5ad")),
                                      "sha256": upload["sha256"]}
                    else:
                        dependency = state["_canonical_artifacts"].get(identifier)
                        if dependency is None:
                            raise ValueError("unknown_nested_artifact")
                        self.receipt_artifacts(state, dependency)
                    verify_checked_file(
                        self.service,
                        state,
                        dependency["path"],
                        dependency["sha256"],
                        limit=integrity_limit(self.service, dependency["path"]),
                    )
                    paired = [field for field in ("sha256", "checksum") if field in item]
                    if not paired:
                        raise ValueError("nested_checksum_required")
                    for field in paired:
                        if item[field] not in {None, "", dependency["sha256"]}:
                            raise ValueError("nested_checksum_mismatch")
                        result[field] = dependency["sha256"]
                    result[key] = dependency["path"]
                    dependencies.append(dict(dependency))
                elif key not in result:
                    result[key] = walk(value, location)
            return result

        result = walk(payload)
        if named_artifacts:
            if set(bound_named) != set(named_artifacts):
                raise ValueError("canonical_source_artifacts_required")
            receipts = {
                (record["receipt_file"], record["receipt_sha256"])
                for record in bound_named.values()
            }
            if len(receipts) != 1:
                raise ValueError("canonical_source_receipt_mismatch")
            receipt_file, receipt_sha256 = next(iter(receipts))
            receipt = next(
                (
                    item
                    for item in state["_tool_runs"]
                    if item["file"] == receipt_file
                    and item["sha256"] == receipt_sha256
                ),
                None,
            )
            if receipt is None or receipt["tool_id"] != "P0-02":
                raise ValueError("canonical_source_producer_mismatch")
        return result, dependencies

    def add_object(self, state, *, tool_id, mode_id, role, schema_ref, object_version, data):
        from .sessions import uid, write_file
        self.package_options(state)
        self.role(tool_id, mode_id, role, schema_ref, object_version)
        if schema_ref in GRAPH_SCHEMAS:
            raise ValueError("canonical_graph_output_required")
        if len(state["_input_objects"]) >= SESSION_OBJECT_LIMIT:
            raise ValueError("object_count_limit")
        original = strict_json(data)
        metadata = (tool_id, mode_id, role, schema_ref, object_version)
        named_artifacts = (
            P006_SOURCE_ARTIFACTS
            if metadata == P006_SOURCE_BOUND_METADATA
            else None
        )
        payload, dependencies = self.bind_nested(
            state, original, named_artifacts=named_artifacts
        )
        self.validate_object(payload, schema_ref, object_version)
        encoded = data if payload == original else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > OBJECT_LIMIT:
            raise ValueError("object_size_limit")
        identifier = uid()
        path = self.service.directory(state["id"]) / "objects" / (identifier + ".json")
        write_file(path, encoded)
        state["_input_objects"][identifier] = {
            "path": str(path), "sha256": hashlib.sha256(encoded).hexdigest(),
            "schema_ref": schema_ref, "object_version": object_version,
            "source": "user_upload", "producer_tool_id": None, "label": role,
            "dependencies": dependencies,
        }
        return identifier

    def package_options(self, state):
        from .sessions import uid, write_file
        from importlib.resources import files
        from bridge.tool_packages._structured_runtime import canonical_json_bytes
        from bridge.tool_packages.p0_08_evidence_sufficiency.adapter import load_gate_rule
        from bridge.tool_packages.p0_10_claim_verifier.verifier import load_release_contract
        self.initialize(state)
        release = load_release_contract()
        for label, schema, model in (
            ("gate_rule_spec", "evidence-sufficiency-gate-rule-spec/v0.2", load_gate_rule()),
            ("claim_policy_spec", "claim-policy-spec/v0.1", release.claim_policy),
            ("statement_registry", "statement-registry/v0.1", release.statement_registry),
        ):
            if any(item["source"] == "package_resource" and item["label"] == label for item in state["_input_objects"].values()):
                continue
            if len(state["_input_objects"]) >= SESSION_OBJECT_LIMIT:
                raise ValueError("object_count_limit")
            data = (files("bridge.tool_packages.p0_08_evidence_sufficiency.resources").joinpath("gate_rule_spec_v0.2.json").read_bytes()
                    if label == "gate_rule_spec" else canonical_json_bytes(model.model_dump(mode="json")))
            payload = strict_json(data)
            version = payload.get("object_version", payload.get("version"))
            schema_ref = "bridge://schemas/" + schema
            self.validate_object(payload, schema_ref, version)
            identifier = uid()
            path = self.service.directory(state["id"]) / "objects" / (identifier + ".json")
            write_file(path, data)
            state["_input_objects"][identifier] = {
                "path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "label": label,
                "schema_ref": schema_ref, "object_version": version,
                "source": "package_resource", "producer_tool_id": None,
            }

    def register_outputs(self, state, outcome, receipt):
        from .sessions import uid
        self.initialize(state)
        if receipt["file"] in state["_indexed_input_receipts"]:
            return
        if outcome.execution_state.value not in {"succeeded", "partial"}:
            return
        schemas = {schema for spec in self.service.registry.list()
                   for mode in self.service.registry.describe_input(spec.tool_id).object_input_modes
                   for role in mode.roles for schema in role.schema_refs}
        schemas.update({"bridge://schemas/cell-state-candidate-profile/v1.0",
                        "bridge://schemas/native-cell-state-context-profile/v0.1",
                        "bridge://schemas/native-cell-state-context-profile/v0.2",
                        "bridge://schemas/saved-target-role-profile/v0.1",
                        "bridge://schemas/exploratory-process-profile/v0.1",
                        "bridge://schemas/exploratory-program-profile/v0.1",
                        "bridge://schemas/exploratory-program-profile/v0.2",
                        "bridge://schemas/research-claim-verification-result/v0.2",
                        "bridge://schemas/research-analysis-snapshot/v0.2",
                        "bridge://schemas/research-analysis-snapshot/v0.3",
                        "bridge://schemas/research-analysis-snapshot/v0.4", "bridge://schemas/research-analysis-snapshot/v0.5"})
        verified = False
        pending_artifacts, pending_objects = {}, {}
        for artifact in outcome.artifacts:
            base = {"path": str(artifact.path), "sha256": artifact.sha256, "artifact_id": artifact.artifact_id,
                    "receipt_file": receipt["file"], "receipt_sha256": receipt["sha256"]}
            if not verified:
                self.receipt_artifacts(state, base)
                verified = True
            aid = uid()
            pending_artifacts[aid] = base
            if artifact.path.suffix.lower() != ".json":
                continue
            try:
                payload = strict_json(checked_bytes(self.service, state, artifact.path, artifact.sha256, limit=OBJECT_LIMIT))
            except ValueError:
                continue
            for schema in sorted(schemas):
                try:
                    version = self.object_version(payload, schema)
                except ValueError:
                    continue
                identifier = uid()
                pending_artifacts[identifier] = base
                pending_objects[identifier] = {**base, "schema_ref": schema, "object_version": version,
                    "source": "tool_output", "producer_tool_id": outcome.request.tool_id,
                    "label": outcome.request.tool_id + " " + schema.split("/")[-2]}
                break
        if len(state["_input_objects"]) + len(pending_objects) > SESSION_OBJECT_LIMIT:
            raise ValueError("object_count_limit")
        state["_canonical_artifacts"].update(pending_artifacts)
        state["_input_objects"].update(pending_objects)
        state["_indexed_input_receipts"].append(receipt["file"])

    def sync_outputs(self, state):
        from bridge.toolkit.contracts import ToolRun, ToolRunV2
        root = self.service.directory(state["id"])
        for receipt in state["_tool_runs"]:
            if receipt["file"] in state["_indexed_input_receipts"] or receipt["state"] not in {"succeeded", "partial"}:
                continue
            payload = strict_json(checked_bytes(self.service, state, root / "receipts" / receipt["file"],
                receipt["sha256"]), 128 * 1024 * 1024)
            model = ToolRunV2 if "result_schema_ref" in payload else ToolRun
            self.register_outputs(state, model.model_validate(payload), receipt)

    def system_options(self, state):
        from .sessions import uid
        try:
            _, resources = self.reference_resources(state)
        except (ValueError, OSError, KeyError):
            return
        for record in resources:
            if record not in state["_input_objects"].values() and len(state["_input_objects"]) < SESSION_OBJECT_LIMIT:
                state["_input_objects"][uid()] = record

    def measurement_specs(self):
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
        ref = self.service.settings.cell_state_measurement_spec_ref
        spec = load_measurement_spec(ref)
        return [{"id": EXPLORATION_SPEC, "label": "UMAP、群标记与样本条件比较"}] + (
            [] if spec is None else [{"id": spec.measurement_spec_id, "label": "候选细胞状态分析"}])

    def selected_asset(self, state, tool_id, asset_id, *, register_qc=False, manual_exploratory=False,
                       raw_similarity=False):
        if raw_similarity:
            declaration = state["_asset_declarations"].get(asset_id)
            if declaration is None:
                raise ValueError("asset_declaration_required")
            asset = CaseInputAsset.model_validate(declaration)
            views = []
            for receipt in reversed(state.get("_tool_runs", [])):
                if (receipt["file"] in state.get("_invalidated_receipts", {})
                        or receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded"
                        or self.service.qc.receipt_asset_id(state, receipt) != asset_id):
                    continue
                _, outputs = self.producer_objects(state, receipt, "P0-01", {"qc_profile_v2"})
                views = [payload["selected_data_view"] for _, payload in outputs.get("qc_profile_v2", [])
                         if payload.get("selected_data_view")]
                break
            if (len(views) != 1 or views[0]["parent_asset_id"] != asset_id
                    or views[0]["parent_asset_sha256"] != asset.checksum
                    or views[0]["matrix_location"] != asset.matrix_location):
                raise ValueError("scientific_selected_view_mismatch")
            return asset.model_copy(update={"metadata": {**asset.metadata,
                "data_view_id": views[0]["view_id"]}})
        declared_only = (tool_id == "P0-06" and manual_exploratory and not any(
            row["tool_id"] == "P0-01" and row["state"] == "succeeded"
            and self.service.qc.receipt_asset_id(state, row) == asset_id for row in state.get("_tool_runs", [])))
        if tool_id in {"P0-02", "P0-03", "P0-04", "P0-06"} and not declared_only:
            if not state["_uploads"][asset_id].get("source_family_id"):
                raise ValueError("source_family_id_required")
            asset = self.service.qc.asset(state, asset_id, register=register_qc)
            if tool_id == "P0-02":
                return asset
            views = []
            for receipt in reversed(state.get("_tool_runs", [])):
                if receipt["file"] in state.get("_invalidated_receipts", {}):
                    continue
                if (receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded"
                        or self.service.qc.receipt_asset_id(state, receipt) != asset_id):
                    continue
                _, outputs = self.producer_objects(state, receipt, "P0-01", {"qc_profile_v2"})
                views = [payload["selected_data_view"] for _, payload in outputs.get("qc_profile_v2", [])
                         if payload.get("selected_data_view")
                         and payload["selected_data_view"]["view_id"] == asset.metadata.get("data_view_id")]
                break
            if len(views) != 1 or views[0]["sha256"] != asset.checksum or views[0]["parent_asset_id"] != asset_id:
                raise ValueError("scientific_selected_view_mismatch")
            view = views[0]
            return asset.model_copy(update={"asset_id": view["artifact_id"],
                "metadata": {**asset.metadata, "parent_asset_id": view["parent_asset_id"]}})
        declaration = state["_asset_declarations"].get(asset_id)
        if declaration is None:
            raise ValueError("asset_declaration_required")
        return CaseInputAsset.model_validate(declaration)

    def selection_reasons(self, state, selection, verify=False):
        reasons, _ = self._selection(
            state, selection, verify=verify, register_qc=False
        )
        return reasons

    @_verification_operation
    def _selection(self, state, selection, *, verify, register_qc):
        self.initialize(state)
        contract, mode = self.contract_mode(selection.tool_id, selection.mode_id)
        reasons = []
        if selection.expression_analysis is not None and (
                selection.tool_id != 'P0-02' or selection.measurement_spec_ref != EXPLORATION_SPEC):
            raise ValueError('expression_options_require_exploration')
        if contract.object_input_modes and mode is None:
            if selection.object_inputs:
                raise ValueError("input_mode_required")
            reasons.append("input_mode_required")
        roles = {item.role: item for item in mode.roles} if mode else {}
        counts = {}
        identifiers = []
        for choice in selection.object_inputs:
            record = state["_input_objects"].get(choice.input_id)
            if record is None:
                raise ValueError("unknown_input_object")
            self.role(selection.tool_id, selection.mode_id, choice.role, record["schema_ref"], record["object_version"])
            if record["schema_ref"] in GRAPH_SCHEMAS and record["source"] != "tool_output":
                raise ValueError("canonical_graph_output_required")
            if verify:
                self.verify(state, record)
            counts[choice.role] = counts.get(choice.role, 0) + 1
            identifiers.append(choice.input_id)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate_input_object")
        for name, role in roles.items():
            count = counts.get(name, 0)
            if role.max_count is not None and count > role.max_count:
                raise ValueError("input_cardinality_exceeded:" + name)
            if count < role.min_count:
                reasons.append("object_required:" + name)
        asset_contract = (mode.asset_input if mode and mode.asset_input else contract.asset_input)
        if len(selection.asset_ids) != len(set(selection.asset_ids)):
            raise ValueError("duplicate_input_asset")
        maximum = asset_contract.max_count if asset_contract else 0
        if maximum is not None and len(selection.asset_ids) > maximum:
            raise ValueError("asset_cardinality_exceeded")
        if asset_contract and len(selection.asset_ids) < asset_contract.min_count:
            reasons.append("asset_required")
        assets = []
        manual_exploratory = None
        if (selection.tool_id, selection.mode_id) == ("P0-06", "exploratory_process") and len(selection.object_inputs) == 1:
            choice = selection.object_inputs[0]
            record = state["_input_objects"][choice.input_id]
            if choice.role == "exploratory_process_input" and record["source"] == "user_upload":
                manual_exploratory = self.verify(state, record)["data_view"]
        for aid in selection.asset_ids:
            if aid not in state["_uploads"]:
                raise ValueError("unknown_input_asset")
            try:
                asset = self.selected_asset(
                    state,
                    selection.tool_id,
                    aid,
                    register_qc=register_qc,
                    raw_similarity=(selection.tool_id, selection.mode_id) == (
                        "P0-03", "reference_similarity_exploratory"),
                    manual_exploratory=bool(manual_exploratory
                        and manual_exploratory["artifact_id"] == aid
                        and manual_exploratory["parent_asset_id"] == aid
                        and manual_exploratory["sha256"] == state["_uploads"][aid]["sha256"]
                        and manual_exploratory["parent_asset_sha256"] == state["_uploads"][aid]["sha256"]),
                )
            except ValueError as exc:
                reason = str(exc)
                if reason == "asset_declaration_required" or (
                    selection.tool_id == "P0-02"
                    and reason in {
                        "source_family_id_required",
                        "completed_qc_required",
                        "qc_artifacts_missing",
                        "qc_artifact_integrity_mismatch",
                        "qc_declaration_retracted",
                    }
                ):
                    reasons.append(reason)
                    continue
                raise
            except (OSError, KeyError):
                if selection.tool_id != "P0-02":
                    raise
                reasons.append("qc_artifacts_unavailable")
                continue
            assets.append(asset)
            for field, allowed in (("format", asset_contract.formats), ("assay", asset_contract.assays),
                                   ("input_level", asset_contract.input_levels), ("matrix_semantics", asset_contract.matrix_semantics)):
                if allowed and getattr(asset, field) not in allowed:
                    raise ValueError("asset_contract_mismatch:" + field)
            for key in asset_contract.required_metadata_keys:
                if key not in asset.metadata:
                    reasons.append("asset_metadata_required:" + key)
            if verify:
                verify_checked_file(
                    self.service,
                    state,
                    asset.path,
                    asset.checksum,
                    limit=self.service.settings.max_upload_bytes,
                )
        ref = selection.measurement_spec_ref
        if ref and (contract.measurement_spec_ref_policy == "forbidden" or ref not in {item["id"] for item in self.measurement_specs()}):
            raise ValueError("unknown_measurement_spec")
        if not ref and contract.measurement_spec_ref_policy == "required":
            reasons.append("measurement_spec_required")
        if not selection.asset_ids and not state.get("_bundle", {}).get("assets") and not state["_asset_declarations"]:
            reasons.append("product_analysis_context_required")
        return reasons, assets

    def declare_asset(self, state, declaration):
        self.initialize(state)
        upload = state["_uploads"].get(declaration.upload_id)
        if upload is None:
            raise ValueError("unknown_input_asset")
        if declaration.matrix_location not in upload["locations"]:
            raise ValueError("matrix_not_registered")
        from bridge.tool_packages.p0_01_input_qc.io import LINEAGE_METADATA_KEY, DeclaredLineageMetadata
        keys = {"sample_id", "capture_id", "source_family_id", LINEAGE_METADATA_KEY,
                "sample_id_column", "capture_id_column", "gene_symbol_column"}
        for spec in self.service.registry.list():
            contract = self.service.registry.describe_input(spec.tool_id)
            for item in [contract.asset_input, *(mode.asset_input for mode in contract.object_input_modes)]:
                if item:
                    keys.update(item.required_metadata_keys)
        metadata = strict_json(json.dumps(declaration.metadata, allow_nan=False).encode(), 32768)
        if set(metadata) - keys:
            raise ValueError("unknown_asset_metadata")
        if LINEAGE_METADATA_KEY in metadata:
            DeclaredLineageMetadata.model_validate(metadata[LINEAGE_METADATA_KEY])
        # Metadata is declaration-only, never a file-loading channel.
        self.bind_nested(state, metadata)
        path = self.service.directory(state["id"]) / "uploads" / (declaration.upload_id + ".h5ad")
        verify_checked_file(
            self.service,
            state,
            path,
            upload["sha256"],
            limit=self.service.settings.max_upload_bytes,
        )
        asset = CaseInputAsset(asset_id=declaration.upload_id, path=path, format="h5ad", checksum=upload["sha256"],
            **declaration.model_dump(exclude={"upload_id"}))
        state["_asset_declarations"][asset.asset_id] = asset.model_dump(mode="json")

    def construct(self, state, selection):
        from .sessions import uid
        reasons, assets = self._selection(
            state,
            selection,
            verify=True,
            register_qc=selection.tool_id == "P0-02",
        )
        if reasons:
            raise ValueError(reasons[0])
        contract, mode = self.contract_mode(selection.tool_id, selection.mode_id)
        context = assets or [CaseInputAsset.model_validate(item) for item in
            (state.get("_bundle", {}).get("assets") or list(state["_asset_declarations"].values()))]
        bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=context)
        arguments = dict(request_id=uid(), tool_id=selection.tool_id,
            tool_version=self.service.registry.describe(selection.tool_id).version,
            assets=[item.to_toolkit_asset() for item in assets], measurement_spec_ref=selection.measurement_spec_ref,
            output_dir=self.service.directory(state["id"]) / "runs", parameters={}, random_seed=0)
        if selection.tool_id == "P0-02":
            arguments["parameters"] = (
                (selection.expression_analysis or ExpressionAnalysis()).model_dump(mode="json")
                if selection.measurement_spec_ref == EXPLORATION_SPEC else self.service.cell_state_runtime_parameters())
        if contract.request_schema_ref.endswith("/v0.2"):
            objects = [StructuredInputRef(input_id=choice.input_id, role=choice.role,
                **{key: state["_input_objects"][choice.input_id][key] for key in
                   ("schema_ref", "object_version", "path", "sha256")}) for choice in selection.object_inputs]
            request = ToolRequestV2(**arguments, object_inputs=objects)
        else:
            request = ToolRequest(**arguments)
        return bundle, request


    @_verification_operation
    def producer_objects(self, state, receipt, tool_id, kinds):
        """Read canonical objects from one verified producer, never from Schema alone."""
        from bridge.toolkit.contracts import ToolRun, ToolRunV2
        if receipt["tool_id"] != tool_id or receipt["state"] not in {"succeeded", "partial"}:
            raise ValueError("canonical_source_producer_mismatch")
        raw = strict_json(checked_bytes(self.service, state,
            self.service.directory(state["id"]) / "receipts" / receipt["file"], receipt["sha256"]),
            128 * 1024 * 1024)
        model = ToolRunV2 if "object_inputs" in raw["request"] else ToolRun
        run = model.model_validate(raw)
        self.service.registry.validate_historical_result(run, run.request)
        if run.request.tool_id != tool_id or run.execution_state.value != receipt["state"]:
            raise ValueError("canonical_source_producer_mismatch")
        artifacts = {item.artifact_id: item for item in run.artifacts}
        result = {}
        for identifier, record in state["_input_objects"].items():
            if (record.get("source") != "tool_output" or record.get("producer_tool_id") != tool_id
                    or record.get("receipt_file") != receipt["file"]
                    or record.get("receipt_sha256") != receipt["sha256"]):
                continue
            artifact = artifacts.get(record["artifact_id"])
            if artifact is None or artifact.kind not in kinds:
                continue
            payload = self.verify(state, record)
            result.setdefault(artifact.kind, []).append((identifier, payload))
        return run, result

    def assessment_selections(self, state, allowed_modes):
        """Only explicit dependency-source selections for the fixed P0 chain."""
        wanted = {(row.tool_id, row.mode_id) for row in allowed_modes}
        sources = set()
        for row in allowed_modes:
            if row.mode_id == "legacy_aggregation":
                continue
            if row.tool_id in {"P0-02", "P0-03", "P0-04", "P0-05", "P0-06", "P0-08", "P0-09"}:
                sources.update({"P0-01", "P0-02"})
            if row.tool_id in {"P0-04", "P0-05", "P0-06", "P0-08", "P0-09"}:
                sources.add("P0-03")
            if row.tool_id in {"P0-06", "P0-08", "P0-09"}:
                sources.add("P0-04")
            if row.tool_id in {"P0-08", "P0-09"}:
                sources.update({"P0-05", "P0-06"})
            if row.tool_id == "P0-09":
                sources.update({"P0-08", "P0-09"})
        return {tool: value for tool, value in state["_input_selections"].items()
                if (tool, value["mode_id"]) in wanted or tool in sources}

    @_verification_operation
    def assessment_resource_ids(self, state, upload_id, allowed_modes):
        """Freeze roots before consent; this never authorizes a producer execution."""
        self.initialize(state)
        self.sync_outputs(state)
        selections = self.assessment_selections(state, allowed_modes)
        identifiers = {row["input_id"] for selected in selections.values()
                       for row in selected["object_inputs"]}
        if not any(row.mode_id != "legacy_aggregation" for row in allowed_modes):
            return sorted(identifiers)
        self.system_options(state)
        identifiers.update(identifier for identifier, record in state["_input_objects"].items()
                           if record["source"] == "system_resource")
        view, qc_id, qc_receipt = None, None, None
        for receipt in reversed(state.get("_tool_runs", [])):
            if receipt["file"] in state.get("_invalidated_receipts", {}):
                continue
            if (receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded"
                    or self.service.qc.receipt_asset_id(state, receipt) != upload_id):
                continue
            _, outputs = self.producer_objects(state, receipt, "P0-01",
                {"qc_profile_v2", "biological_unit_manifest", "biological_unit_assignment"})
            profiles = outputs.get("qc_profile_v2", [])
            if len(profiles) != 1:
                raise ValueError("canonical_qc_profile_required")
            view = profiles[0][1]["selected_data_view"]
            qc_id, qc_receipt = profiles[0][0], receipt
            identifiers.update(identifier for rows in outputs.values() for identifier, _ in rows)
            break
        if view is not None and any(row.tool_id == "P0-06" and row.mode_id == "exploratory_programs"
                                    for row in allowed_modes):
            identifiers.add(self.service.scientific_inputs.register_program_input(
                state, upload_id, view, qc_id, qc_receipt))
        if view is not None and any(row.tool_id == "P0-06" and row.mode_id == "directed_programs"
                                    for row in allowed_modes):
            identifiers.update(self.service.scientific_inputs.register_directed_program_inputs(
                state, upload_id, view, qc_id, qc_receipt))
        p002_receipt, p002_profile_id = None, None
        if view is not None:
            for receipt in reversed(state.get("_tool_runs", [])):
                if receipt["file"] in state.get("_invalidated_receipts", {}):
                    continue
                if receipt["tool_id"] != "P0-02" or receipt["state"] not in {"succeeded", "partial"}:
                    continue
                run, outputs = self.producer_objects(state, receipt, "P0-02", {"cell_state_profile_v3", "cell_state_candidate_profile"})
                profiles = outputs.get("cell_state_profile_v3", []) + outputs.get("cell_state_candidate_profile", [])
                if len(profiles) != 1 or len(run.request.assets) != 1:
                    continue
                profile, asset = profiles[0][1], run.request.assets[0]
                if (profile.get("input_data_view") != view or asset.checksum != view["sha256"]
                        or asset.metadata.get("data_view_id") != view["view_id"]
                        or asset.metadata.get("source_family_id") != state["_uploads"][upload_id].get("source_family_id")
                        or run.request.measurement_spec_ref != self.service.settings.cell_state_measurement_spec_ref):
                    continue
                if (profile["producer_run_ref"] != run.run_id or profile["producer_tool_id"] != "P0-02"
                        or profile["producer_tool_version"] != run.tool_version):
                    raise ValueError("canonical_source_producer_mismatch")
                identifiers.update(identifier for identifier, record in state["_input_objects"].items()
                    if record.get("receipt_file") == receipt["file"] and record.get("receipt_sha256") == receipt["sha256"])
                p002_receipt, p002_profile_id = receipt, profiles[0][0]
                break
        if (p002_receipt is not None and any(row.tool_id in {"P0-03", "P0-04", "P0-05"}
                and row.mode_id == "saved_cell_state_context" for row in allowed_modes)):
            identifiers.add(self.register_saved_cell_state_run(state, p002_receipt, p002_profile_id, view))
        if view is not None and self.service.settings.cell_state_candidate_runtime_ref:
            from .native_evidence import case_context_key
            facts = self.service.intake.current_facts(state, upload_id, include_draft=False).model_dump(mode="json")
            case_id = "product-case:native-" + case_context_key(view, facts)[:24]
            if any(row.tool_id == "P0-09" and row.mode_id in {
                    "case_initial_v2", "case_append_v2"} for row in allowed_modes):
                from .report_inputs import SUFFICIENCY_SCHEMAS
                for receipt in reversed(state.get("_tool_runs", [])):
                    if (receipt["file"] in state.get("_invalidated_receipts", {})
                            or receipt["tool_id"] != "P0-08"
                            or receipt["state"] not in {"succeeded", "partial"}):
                        continue
                    run, outputs = self.producer_objects(state, receipt, "P0-08",
                        {"evidence_sufficiency_run_result"})
                    refs = {role: [ref for ref in run.request.object_inputs if ref.role == role]
                            for role in ("product_case", "qc_readiness_profile")}
                    if any(len(found) != 1 for found in refs.values()):
                        continue
                    values = {}
                    for role, found in refs.items():
                        ref = found[0]
                        record = state["_input_objects"].get(ref.input_id)
                        if (record is None or record["path"] != str(ref.path)
                                or any(record[key] != getattr(ref, key)
                                       for key in ("sha256", "schema_ref", "object_version"))):
                            raise ValueError("canonical_source_binding_mismatch")
                        values[role] = self.verify(state, record)
                    case, qc = values["product_case"], values["qc_readiness_profile"]
                    if (case["product_case_id"] != case_id or case["case_version"] != "0.1.0"
                            or qc.get("selected_data_view") != view
                            or case["sample_or_preparation_ref"] != {
                                "object_id": view["sample_or_preparation_ref"].rsplit("@", 1)[0],
                                "object_version": view["sample_or_preparation_ref"].rsplit("@", 1)[1]}):
                        continue
                    results = outputs.get("evidence_sufficiency_run_result", [])
                    if len(results) != 1:
                        raise ValueError("canonical_sufficiency_result_required")
                    result_id, result = results[0]
                    original = run.result.model_dump(mode="json") if hasattr(run.result, "model_dump") else run.result
                    if (state["_input_objects"][result_id]["schema_ref"] not in SUFFICIENCY_SCHEMAS
                            or result != original
                            or result["case_summary"]["product_case_ref"] != {
                                "object_id": case_id, "object_version": "0.1.0"}):
                        raise ValueError("canonical_sufficiency_result_mismatch")
                    identifiers.add(result_id)
                    break
            pinned_kinds = set()
            for receipt in reversed(state.get("_tool_runs", [])):
                if (receipt["file"] in state.get("_invalidated_receipts", {})
                        or receipt["state"] not in {"succeeded", "partial"}
                        or receipt["tool_id"] not in {"P0-03", "P0-04", "P0-05", "P0-06", "P0-09"}):
                    continue
                rows = [(key, row) for key, row in state["_input_objects"].items()
                        if row.get("receipt_file") == receipt["file"]]
                eligible = False
                kind = receipt["tool_id"]
                for _, row in rows:
                    if row["schema_ref"] == "bridge://schemas/exploratory-process-profile/v0.1":
                        eligible = self.verify(state, row)["input_contract"]["data_view"] == view
                        kind = "P0-06:exploratory_process"
                    elif row["schema_ref"] in {"bridge://schemas/exploratory-program-profile/v0.1",
                                               "bridge://schemas/exploratory-program-profile/v0.2"}:
                        profile = self.verify(state, row)
                        eligible = profile["input_contract"]["data_view"] == view
                        kind = ("P0-06", tuple(sorted(program["source_gene_set"]
                            for program in profile["input_contract"]["programs"])))
                    elif (row["schema_ref"] in {"bridge://schemas/native-cell-state-context-profile/v0.1",
                                               "bridge://schemas/native-cell-state-context-profile/v0.2",
                                               "bridge://schemas/saved-target-role-profile/v0.1"}
                            and receipt["tool_id"] in {"P0-03", "P0-04", "P0-05"}):
                        eligible = self.verify(state, row)["data_view"] == view
                    elif row["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1":
                        eligible = self.verify(state, row)["product_case_ref"] == {"object_id": case_id, "object_version": "0.1.0"}
                    if eligible:
                        break
                if eligible and kind not in pinned_kinds:
                    identifiers.update(key for key, _ in rows)
                    pinned_kinds.add(kind)
        identifiers.update(self.service.report_inputs.assessment_resource_ids(state, upload_id, selections, view))
        return sorted(identifiers)

    def register_saved_cell_state_run(self, state, receipt, profile_id, view):
        """Expose one verified in-session P002 receipt as an exact, read-only input."""
        from .scientific_inputs import digest
        run, outputs = self.producer_objects(state, receipt, "P0-02", {"cell_state_candidate_profile"})
        profiles = outputs.get("cell_state_candidate_profile", [])
        if (len(profiles) != 1 or profiles[0][0] != profile_id
                or profiles[0][1].get("input_data_view") != view):
            raise ValueError("canonical_saved_cell_state_required")
        path = self.service.directory(state["id"]) / "receipts" / receipt["file"]
        payload = strict_json(checked_bytes(self.service, state, path, receipt["sha256"]), 128 * 1024 * 1024)
        schema = "bridge://schemas/tool-run/v0.1"
        self.validate_object(payload, schema, "0.1.0")
        identifier = digest({"saved_p002_receipt": receipt["sha256"], "profile": profile_id})[:32]
        record = {"path": str(path), "sha256": receipt["sha256"], "schema_ref": schema,
            "object_version": "0.1.0", "source": "agent_constructed", "producer_tool_id": None,
            "label": "saved_cell_state_run", "derivation_inputs": {
                profile_id: state["_input_objects"][profile_id]["sha256"]},
            "dependencies": [{"path": str(item.path), "sha256": item.sha256} for item in run.artifacts]}
        existing = state["_input_objects"].get(identifier)
        if existing is not None and existing != record:
            raise ValueError("saved_run_identity_conflict")
        if existing is None:
            if len(state["_input_objects"]) >= SESSION_OBJECT_LIMIT:
                raise ValueError("object_count_limit")
            state["_input_objects"][identifier] = record
        self.verify(state, record)
        return identifier

    def evidence_sources(self, state):
        """Adapt verified storage reads to the independent source-selection module."""
        from .evidence_sources import EvidenceSources
        return EvidenceSources(
            records=state["_input_objects"], receipts=state.get("_tool_runs", []),
            invalidated=state.get("_invalidated_receipts", {}),
            read_producer=lambda receipt: self.producer_objects(
                state, receipt, receipt["tool_id"], set())[0],
            verify=lambda record: self.verify(state, record),
        )

    def assessment_pool(self, state, scope):
        return self.evidence_sources(state).pool(
            scope.binding["resources"], state.get("_assessment", {}).get("admissions", []))

    def add_derived_object(self, state, *, tool_id, mode_id, role, schema_ref, payload, dependencies,
                           artifact_dependencies=(), file_dependencies=()):
        """Append content-addressed objects without pretending the researcher authored them."""
        from .sessions import write_file
        from .scientific_inputs import encoded, digest
        self.initialize(state)
        version = self.object_version(payload, schema_ref)
        self.role(tool_id, mode_id, role, schema_ref, version)
        bound = {}
        for identifier in sorted(set(dependencies)):
            record = state["_input_objects"][identifier]
            self.verify(state, record)
            bound[identifier] = record["sha256"]
        artifacts = sorted(artifact_dependencies, key=lambda row: (row["receipt_file"], row["artifact_id"]))
        for artifact in artifacts:
            self.receipt_artifacts(state, artifact)
            verify_checked_file(
                self.service,
                state,
                artifact["path"],
                artifact["sha256"],
                limit=integrity_limit(self.service, artifact["path"]),
            )
        files = sorted(file_dependencies, key=lambda row: row["path"])
        for file in files:
            verify_checked_file(self.service, state, file["path"], file["sha256"],
                                limit=integrity_limit(self.service, file["path"]))
        raw = encoded(payload)
        identity_parts = {"schema_ref": schema_ref, "object_version": version,
                          "payload": payload, "dependencies": bound, "artifacts": artifacts}
        if files:
            identity_parts["files"] = files
        identity = digest(identity_parts)[:32]
        record = {"path": str(self.service.directory(state["id"]) / "objects" / (identity + ".json")),
            "sha256": hashlib.sha256(raw).hexdigest(), "schema_ref": schema_ref, "object_version": version,
            "source": "agent_constructed", "producer_tool_id": None, "label": role,
            "derivation_inputs": bound, "dependencies": [*artifacts, *files]}
        existing = state["_input_objects"].get(identity)
        if existing is not None:
            if existing != record:
                raise ValueError("derived_object_identity_collision")
            self.verify(state, existing)
            return identity
        if len(state["_input_objects"]) >= SESSION_OBJECT_LIMIT:
            raise ValueError("object_count_limit")
        write_file(Path(record["path"]), raw)
        state["_input_objects"][identity] = record
        return identity

    @_verification_operation
    def assessment_candidates(self, state, scope):
        """Concrete registered selections; scientific materialization joins here."""
        from .scientific_inputs import digest
        candidates = []
        for allowed in scope.allowed_modes:
            append_key = ({("P0-08", "default"): "append_p008",
                           ("P0-09", "case_append_v2"): "append_p009"}
                          .get((allowed.tool_id, allowed.mode_id)))
            append = scope.binding.get(append_key) if append_key else None
            saved = ((append.get("selection") if append else None)
                     or state["_input_selections"].get(allowed.tool_id))
            if append and append.get("after_sufficiency"):
                saved = None
            row = {"tool_id": allowed.tool_id, "mode_id": allowed.mode_id,
                   "bundle": None, "request": None, "fingerprint": None, "blockers": []}
            if append and append.get("blocker"):
                row["blockers"] = [append["blocker"]]
                candidates.append(row)
                continue
            automatic = (allowed.tool_id, allowed.mode_id) in {
                ("P0-01", None), ("P0-02", None), ("P0-08", "default"), ("P0-10", "default"),
                ("P0-09", "case_initial_v2"), ("P0-09", "case_append_v2"), ("P0-09", "case_query"),
                ("P0-03", "default"), ("P0-04", "default"), ("P0-05", "hard_count_accounting"),
                ("P0-03", "saved_cell_state_context"), ("P0-04", "saved_cell_state_context"), ("P0-05", "saved_cell_state_context"),
                ("P0-06", "exploratory_process"), ("P0-06", "exploratory_programs"),
                ("P0-06", "directed_programs"),
                ("P0-06", "method_runtime_source_bound")}
            if (saved is None or saved["mode_id"] != allowed.mode_id) and not automatic:
                row["blockers"] = ["registered_selection_required"]
            else:
                try:
                    selection = Selection.model_validate((saved if saved and saved["mode_id"] == allowed.mode_id else None) or dict(tool_id=allowed.tool_id, mode_id=allowed.mode_id,
                        asset_ids=[], object_inputs=[], measurement_spec_ref=None))
                    if saved is None and allowed.tool_id in {"P0-01", "P0-02"} and allowed.mode_id is None:
                        selection = selection.model_copy(update={"asset_ids": [scope.upload_id],
                            "measurement_spec_ref": scope.binding["measurement_spec_ref"] if allowed.tool_id == "P0-02" else None})
                        if allowed.tool_id == "P0-02":
                            reasons = (self.service.intake.cell_state_reasons(state, scope.upload_id)
                                       or self.service.cell_state_config_reasons())
                            if reasons:
                                raise ValueError(reasons[0])
                    if any(aid != scope.upload_id for aid in selection.asset_ids):
                        raise ValueError("assessment_upload_mismatch")
                    blocker = (self.service.scientific_inputs.selected_blocker(state, allowed.tool_id, selection)
                               or self.service.report_inputs.selected_blocker(state, allowed.tool_id)
                               or self.service.conditional_blocker(state, allowed.tool_id))
                    if blocker:
                        raise ValueError(blocker)
                    if not (append and append.get("selection")):
                        selection = self.service.scientific_inputs.assessment_selection(state, scope, allowed, selection)
                        selection = self.service.report_inputs.assessment_selection(state, scope, allowed, selection)
                    blocker = self.service.scientific_inputs.selected_blocker(state, allowed.tool_id, selection)
                    if blocker:
                        raise ValueError(blocker)
                    bundle, request = self.construct(state, selection)
                    if (allowed.tool_id, allowed.mode_id) == ("P0-06", "directed_programs"):
                        refs = [ref for ref in request.object_inputs if ref.role == "directed_program_input"]
                        if len(refs) != 1:
                            raise ValueError("canonical_directed_program_input_required")
                        ref = refs[0]
                        record = state["_input_objects"][ref.input_id]
                        if (str(ref.path) != record["path"] or ref.sha256 != record["sha256"]):
                            raise ValueError("canonical_directed_program_input_required")
                        source = self.verify(state, record)
                        row["source_gene_set"] = source["programs"][0]["source_gene_set"]
                        row["source_resource_sha256"] = source["resource"]["sha256"]
                    if allowed.tool_id in {"P0-08", "P0-09"}:
                        from .sessions import uid
                        # Canonical producer artifacts stay at their original paths.
                        # Each consumer writes to a sibling, never above an input.
                        request = request.model_copy(update={"output_dir":
                            self.service.directory(state["id"]) / "runs" / ("assessment-" + uid())})
                    eligibility = self.service.registry.check_eligibility(request)
                    row["blockers"] = list(eligibility.reason_codes) if not eligibility.eligible else []
                    meaning = request.model_dump(mode="json", exclude={"request_id", "output_dir"})
                    # IDs/paths are registration details; scientific content is checksum-bound.
                    for ref in meaning.get("object_inputs", []):
                        ref.pop("input_id", None)
                        ref.pop("path", None)
                    row.update(bundle=bundle, request=request, fingerprint=digest(meaning))
                except (ValueError, OSError) as exc:
                    reason = str(exc)
                    from .runtime import record_degradation
                    record_degradation(state, reason)
                    row["blockers"] = [reason if re.fullmatch(r"[a-z_]+(?::[a-z_]+)?", reason)
                                       else "registered_input_invalid"]
            try:
                row["gaps"] = self.service.report_inputs.assessment_gaps(state, scope, allowed)
            except (ValueError, OSError, KeyError):
                row["gaps"] = []
            row["gaps"] += self.service.scientific_inputs.spatial_link_gaps(state, scope, allowed)
            row["blockers"] = sorted(set(row["blockers"] +
                self.service.scientific_inputs.assessment_blockers(state, scope, allowed)))
            candidates.append(row)
        return candidates

    @_verification_operation
    def verify_plan(self, state, plan):
        self.initialize(state)
        for step in plan.steps:
            if step.approved_request_json is None:
                continue
            payload = json.loads(step.approved_request_json)
            for ref in payload.get("object_inputs", []):
                record = state["_input_objects"].get(ref["input_id"])
                if record is None or any(record[key] != ref[key] for key in ("path", "sha256", "schema_ref", "object_version")):
                    raise ValueError("approved_object_binding_mismatch")
                self.verify(state, record)
            for asset in payload.get("assets", []):
                verify_checked_file(
                    self.service,
                    state,
                    asset["path"],
                    asset["checksum"],
                    limit=self.service.settings.max_upload_bytes,
                )

    def public(self, state, *, refresh=True):
        self.initialize(state)
        if refresh and state["status"] not in {"thinking", "running"}:
            self.package_options(state)
            self.sync_outputs(state)
            self.system_options(state)
        return {"tools": [{"tool_id": spec.tool_id, "label": spec.name,
                    "input_contract": self.service.registry.describe_input(spec.tool_id).model_dump(mode="json")}
                    for spec in self.service.registry.list()],
                "objects": [{"id": identifier, **{key: item[key] for key in
                    ("label", "schema_ref", "object_version", "source", "producer_tool_id")},
                    **({"source_gene_set": self.verify(state, item)["programs"][0]["source_gene_set"],
                       "source_resource_sha256": self.verify(state, item)["resource"]["sha256"]}
                       if item["schema_ref"] == "bridge://schemas/exploratory-process-input/v0.3" else {})}
                    for identifier, item in state["_input_objects"].items()
                    if item.get("receipt_file") not in state.get("_invalidated_receipts", {})],
                "assets": [{"id": item["id"], "label": item["name"],
                    "declaration": {key: value for key, value in state["_asset_declarations"][item["id"]].items()
                        if key in {"assay", "matrix_location", "matrix_semantics", "input_level"}} if item["id"] in state["_asset_declarations"] else None}
                    for item in state["uploads"]],
                "selections": state["_input_selections"], "measurement_specs": self.measurement_specs()}
