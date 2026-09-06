"""Private, contract-driven input binding. Scientific values remain caller-owned."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field
from referencing import Registry as SchemaRegistry

from bridge.domain import CaseInputAsset, CaseInputBundle
from bridge.toolkit.contracts import StructuredInputRef, ToolRequest, ToolRequestV2
from bridge.toolkit.schemas import load_schema

OBJECT_LIMIT = 2 * 1024 * 1024
GRAPH_SCHEMAS = {
    "bridge://schemas/case-evidence-graph-manifest/v0.1",
    "bridge://schemas/comparison-evidence-graph-manifest/v0.1",
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
    object_inputs: list[ObjectChoice] = Field(max_length=128)
    measurement_spec_ref: str | None = Field(max_length=200)


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


def checked_bytes(service, state, path, expected, root=None, limit=128 * 1024 * 1024):
    from .app import read_file
    root = root or service.directory(state["id"])
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
    data = read_file(path, limit)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("input_integrity_mismatch")
    return data


class Inputs:
    def __init__(self, service):
        self.service = service

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
        root = self.service.directory(state["id"])
        receipt = next((item for item in state["_tool_runs"] if item["file"] == record["receipt_file"]
                        and item["sha256"] == record["receipt_sha256"]), None)
        if receipt is None:
            raise ValueError("canonical_receipt_missing")
        raw = checked_bytes(self.service, state, root / "receipts" / receipt["file"], receipt["sha256"])
        run = strict_json(raw, 128 * 1024 * 1024)
        if run["request"]["tool_id"] != receipt["tool_id"] or run["execution_state"] not in {"succeeded", "partial"}:
            raise ValueError("canonical_receipt_invalid")
        artifacts = {}
        for item in run["artifacts"]:
            checked_bytes(self.service, state, item["path"], item["sha256"], root / "runs")
            artifacts[item["artifact_id"]] = item
        artifact = artifacts.get(record["artifact_id"])
        if artifact is None or artifact["path"] != record["path"] or artifact["sha256"] != record["sha256"]:
            raise ValueError("canonical_artifact_mismatch")
        return artifacts

    def verify(self, state, record):
        if record["source"] == "tool_output":
            self.receipt_artifacts(state, record)
        root = self.verify_system_resource(state, record) if record["source"] == "system_resource" else None
        data = checked_bytes(self.service, state, record["path"], record["sha256"], root=root, limit=OBJECT_LIMIT)
        payload = strict_json(data)
        self.validate_object(payload, record["schema_ref"], record["object_version"])
        for dependency in record.get("dependencies", []):
            if dependency.get("artifact_id"):
                self.receipt_artifacts(state, dependency)
            checked_bytes(self.service, state, dependency["path"], dependency["sha256"])
        return payload

    def reference_resources(self, state):
        """Enumerate only the server-configured P0-02 reference; never accept a root from a browser."""
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
        from bridge.tool_packages.p0_02_cell_state.reference import resolve_reference_snapshot, validate_reference_snapshot, validate_runtime_reference
        from .app import read_file
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
                    checked_bytes(self.service, state, path, checksum, root=root)
                    dependencies.append({"path": str(path), "sha256": checksum})
        manifest = validate_reference_snapshot(root)
        validate_runtime_reference(manifest)
        if spec.measurement_spec_id not in manifest.measurement_spec_ids:
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

    def bind_nested(self, state, payload):
        dependencies = []
        def walk(item):
            if isinstance(item, list):
                return [walk(child) for child in item]
            if not isinstance(item, dict):
                return item
            result = {}
            for key, value in item.items():
                locator = key == "path" or key.endswith(("_path", "_file")) or key in {"output_dir"}
                if locator and value is not None:
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
                    checked_bytes(self.service, state, dependency["path"], dependency["sha256"])
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
                    result[key] = walk(value)
            return result
        return walk(payload), dependencies

    def add_object(self, state, *, tool_id, mode_id, role, schema_ref, object_version, data):
        from .app import uid, write_file
        self.package_options(state)
        self.role(tool_id, mode_id, role, schema_ref, object_version)
        if schema_ref in GRAPH_SCHEMAS:
            raise ValueError("canonical_graph_output_required")
        if len(state["_input_objects"]) >= 128:
            raise ValueError("object_count_limit")
        original = strict_json(data)
        payload, dependencies = self.bind_nested(state, original)
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
        from .app import uid, write_file
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
            if len(state["_input_objects"]) >= 128:
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
        from .app import uid
        self.initialize(state)
        if receipt["file"] in state["_indexed_input_receipts"]:
            return
        if outcome.execution_state.value not in {"succeeded", "partial"}:
            return
        schemas = {schema for spec in self.service.registry.list()
                   for mode in self.service.registry.describe_input(spec.tool_id).object_input_modes
                   for role in mode.roles for schema in role.schema_refs}
        verified = False
        for artifact in outcome.artifacts:
            base = {"path": str(artifact.path), "sha256": artifact.sha256, "artifact_id": artifact.artifact_id,
                    "receipt_file": receipt["file"], "receipt_sha256": receipt["sha256"]}
            if not verified:
                self.receipt_artifacts(state, base)
                verified = True
            aid = uid()
            state["_canonical_artifacts"][aid] = base
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
                if len(state["_input_objects"]) >= 128:
                    break
                identifier = uid()
                state["_canonical_artifacts"][identifier] = base
                state["_input_objects"][identifier] = {**base, "schema_ref": schema, "object_version": version,
                    "source": "tool_output", "producer_tool_id": outcome.request.tool_id,
                    "label": outcome.request.tool_id + " " + schema.split("/")[-2]}
                break
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
        from .app import uid
        try:
            _, resources = self.reference_resources(state)
        except (ValueError, OSError, KeyError):
            return
        for record in resources:
            if record not in state["_input_objects"].values() and len(state["_input_objects"]) < 128:
                state["_input_objects"][uid()] = record

    def measurement_specs(self):
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
        ref = self.service.settings.cell_state_measurement_spec_ref
        spec = load_measurement_spec(ref)
        return [] if spec is None else [{"id": spec.measurement_spec_id, "label": "Configured cell-state MeasurementSpec"}]

    def selection_reasons(self, state, selection, verify=False):
        self.initialize(state)
        contract, mode = self.contract_mode(selection.tool_id, selection.mode_id)
        reasons = []
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
        for aid in selection.asset_ids:
            if aid not in state["_uploads"]:
                raise ValueError("unknown_input_asset")
            declaration = state["_asset_declarations"].get(aid)
            if declaration is None:
                reasons.append("asset_declaration_required")
                continue
            asset = CaseInputAsset.model_validate(declaration)
            for field, allowed in (("format", asset_contract.formats), ("assay", asset_contract.assays),
                                   ("input_level", asset_contract.input_levels), ("matrix_semantics", asset_contract.matrix_semantics)):
                if allowed and getattr(asset, field) not in allowed:
                    raise ValueError("asset_contract_mismatch:" + field)
            for key in asset_contract.required_metadata_keys:
                if key not in asset.metadata:
                    reasons.append("asset_metadata_required:" + key)
            if verify:
                checked_bytes(self.service, state, asset.path, asset.checksum)
        ref = selection.measurement_spec_ref
        if ref and (contract.measurement_spec_ref_policy == "forbidden" or ref not in {item["id"] for item in self.measurement_specs()}):
            raise ValueError("unknown_measurement_spec")
        if not ref and contract.measurement_spec_ref_policy == "required":
            reasons.append("measurement_spec_required")
        if not selection.asset_ids and not state.get("_bundle", {}).get("assets") and not state["_asset_declarations"]:
            reasons.append("product_analysis_context_required")
        return reasons

    def declare_asset(self, state, declaration):
        self.initialize(state)
        upload = state["_uploads"].get(declaration.upload_id)
        if upload is None:
            raise ValueError("unknown_input_asset")
        if declaration.matrix_location not in upload["locations"]:
            raise ValueError("matrix_not_registered")
        from bridge.tool_packages.p0_01_input_qc.io import LINEAGE_METADATA_KEY, DeclaredLineageMetadata
        keys = {"sample_id", "capture_id", "source_family_id", LINEAGE_METADATA_KEY}
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
        checked_bytes(self.service, state, path, upload["sha256"])
        asset = CaseInputAsset(asset_id=declaration.upload_id, path=path, format="h5ad", checksum=upload["sha256"],
            **declaration.model_dump(exclude={"upload_id"}))
        state["_asset_declarations"][asset.asset_id] = asset.model_dump(mode="json")

    def construct(self, state, selection):
        from .app import uid
        reasons = self.selection_reasons(state, selection, verify=True)
        if reasons:
            raise ValueError(reasons[0])
        contract, mode = self.contract_mode(selection.tool_id, selection.mode_id)
        assets = [CaseInputAsset.model_validate(state["_asset_declarations"][aid]) for aid in selection.asset_ids]
        context = assets or [CaseInputAsset.model_validate(item) for item in
            (state.get("_bundle", {}).get("assets") or list(state["_asset_declarations"].values()))]
        bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=context)
        arguments = dict(request_id=uid(), tool_id=selection.tool_id,
            tool_version=self.service.registry.describe(selection.tool_id).version,
            assets=[item.to_toolkit_asset() for item in assets], measurement_spec_ref=selection.measurement_spec_ref,
            output_dir=self.service.directory(state["id"]) / "runs", parameters={}, random_seed=0)
        if contract.request_schema_ref.endswith("/v0.2"):
            objects = [StructuredInputRef(input_id=choice.input_id, role=choice.role,
                **{key: state["_input_objects"][choice.input_id][key] for key in
                   ("schema_ref", "object_version", "path", "sha256")}) for choice in selection.object_inputs]
            request = ToolRequestV2(**arguments, object_inputs=objects)
        else:
            request = ToolRequest(**arguments)
        return bundle, request

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
                checked_bytes(self.service, state, asset["path"], asset["checksum"])

    def public(self, state):
        self.initialize(state)
        if state["status"] not in {"thinking", "running"}:
            self.package_options(state)
            self.sync_outputs(state)
            self.system_options(state)
        return {"tools": [{"tool_id": spec.tool_id, "label": spec.name,
                    "input_contract": self.service.registry.describe_input(spec.tool_id).model_dump(mode="json")}
                    for spec in self.service.registry.list()],
                "objects": [{"id": identifier, **{key: item[key] for key in
                    ("label", "schema_ref", "object_version", "source", "producer_tool_id")}}
                    for identifier, item in state["_input_objects"].items()],
                "assets": [{"id": item["id"], "label": item["name"],
                    "declaration": {key: value for key, value in state["_asset_declarations"][item["id"]].items()
                        if key in {"assay", "matrix_location", "matrix_semantics", "input_level"}} if item["id"] in state["_asset_declarations"] else None}
                    for item in state["uploads"]],
                "selections": state["_input_selections"], "measurement_specs": self.measurement_specs()}
