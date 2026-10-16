from __future__ import annotations

import hashlib
import json
import math
import re
import secrets

from fastapi import HTTPException

from .presentation import ArtifactAccessState, ArtifactContentClass
from .sessions import ID, now, private_text, read_file, uid, write_file

PARQUET_MEDIA_TYPES = {"application/vnd.apache.parquet", "application/x-parquet"}


PARQUET_STORED_LIMIT = 8 * 1024 * 1024


PARQUET_ROW_GROUP_LIMIT = 32 * 1024 * 1024


PARQUET_ROW_LIMIT = 100


PARQUET_COLUMN_LIMIT = 24


PARQUET_RESPONSE_LIMIT = 200_000


PARQUET_TEXT_LIMIT = 1_000


PARQUET_TEXT_SUFFIX = "… [truncated]"


JSON_SAFE_INTEGER_LIMIT = (1 << 53) - 1


ARTIFACT_CONTENT_CLASSES = frozenset(
    {
        "research_report",
        "user_result",
        "developer_diagnostic",
    }
)


DEVELOPER_ARTIFACT_KINDS = frozenset(
    {
        "artifact_manifest",
        "developer_diagnostic",
        "diagnostic",
        "log",
        "provider_raw_request",
        "provider_raw_response",
        "provider_request",
        "provider_response",
        "raw_request",
        "raw_response",
        "receipt",
        "report_draft",
        "run_log",
        "tool_receipt",
        "trace",
    }
)


REPORT_BINDING_FIELDS = frozenset(
    {
        "input_revision",
        "graph_id",
        "graph_version",
        "graph_manifest_sha256",
        "snapshot_sha256",
        "renderer_id",
        "snapshot_object_version",
    }
)


HISTORICAL_REPORT_WARNING = (
    "这是历史报告，尚未按当前输入和证据重新核对。"
    "确认提示后可以下载原始文件；原始文件内容不会被改写。"
)


class ArtifactPreviewUnavailable(ValueError):
    pass


class ArtifactPreviewTooLarge(ArtifactPreviewUnavailable):
    pass


def parquet_preview(data: bytes) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(pa.BufferReader(data))
    metadata = parquet.metadata
    schema = parquet.schema_arrow
    total_rows = metadata.num_rows
    total_columns = len(schema)
    columns = schema.names[:PARQUET_COLUMN_LIMIT]
    if len(set(columns)) != len(columns):
        raise ArtifactPreviewUnavailable
    for field in list(schema)[:PARQUET_COLUMN_LIMIT]:
        data_type = field.type
        if not (
            pa.types.is_null(data_type)
            or pa.types.is_boolean(data_type)
            or pa.types.is_integer(data_type)
            or pa.types.is_floating(data_type)
            or pa.types.is_string(data_type)
            or pa.types.is_large_string(data_type)
        ):
            raise ArtifactPreviewUnavailable

    row_groups = []
    rows_accounted = 0
    declared_size = 0
    if total_rows:
        for index in range(metadata.num_row_groups):
            row_group = metadata.row_group(index)
            if row_group.num_rows < 0 or row_group.total_byte_size < 0:
                raise ArtifactPreviewUnavailable
            row_groups.append(index)
            rows_accounted += row_group.num_rows
            declared_size += row_group.total_byte_size
            if declared_size > PARQUET_ROW_GROUP_LIMIT:
                raise ArtifactPreviewTooLarge
            if rows_accounted >= PARQUET_ROW_LIMIT:
                break

    rows = []
    text_truncated = False
    for batch in parquet.iter_batches(
        batch_size=PARQUET_ROW_LIMIT,
        row_groups=row_groups,
        columns=columns,
        use_threads=False,
    ):
        for values in zip(*(column.to_pylist() for column in batch.columns)):
            rendered = []
            for value in values:
                if value is None or isinstance(value, bool):
                    rendered.append(value)
                elif isinstance(value, int):
                    rendered.append(
                        value
                        if -JSON_SAFE_INTEGER_LIMIT <= value <= JSON_SAFE_INTEGER_LIMIT
                        else str(value)
                    )
                elif isinstance(value, float):
                    if not math.isfinite(value):
                        rendered.append(
                            "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
                        )
                    elif value.is_integer() and not (
                        -JSON_SAFE_INTEGER_LIMIT <= value <= JSON_SAFE_INTEGER_LIMIT
                    ):
                        rendered.append(str(value))
                    else:
                        rendered.append(value)
                elif isinstance(value, str):
                    if len(value) > PARQUET_TEXT_LIMIT:
                        value = (
                            value[: PARQUET_TEXT_LIMIT - len(PARQUET_TEXT_SUFFIX)]
                            + PARQUET_TEXT_SUFFIX
                        )
                        text_truncated = True
                    rendered.append(value)
                else:
                    raise ArtifactPreviewUnavailable
            rows.append(rendered)
            if len(rows) >= PARQUET_ROW_LIMIT:
                break
        if len(rows) >= PARQUET_ROW_LIMIT:
            break

    payload = {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "truncated": text_truncated or total_rows > len(rows) or total_columns > len(columns),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > PARQUET_RESPONSE_LIMIT:
        raise ArtifactPreviewTooLarge
    return encoded


class ArtifactStore:
    """Own artifact provenance, visibility, registration and verified reads."""

    def __init__(self, sessions, inputs):
        self.sessions = sessions
        self.inputs = inputs

    @staticmethod
    def _developer_artifact_kind(source_kind: str | None) -> bool:
        if not isinstance(source_kind, str):
            return False
        value = source_kind.casefold()
        return (
            value in DEVELOPER_ARTIFACT_KINDS
            or value.startswith(("developer_", "provider_"))
            or value.endswith(("_diagnostic", "_log", "_receipt", "_trace"))
        )

    def _artifact_records(self, state, aid):
        if not ID.fullmatch(aid) or aid not in state.get("_artifacts", {}):
            raise HTTPException(404, "not_found")
        matches = [
            item
            for item in state.get("artifacts", [])
            if isinstance(item, dict) and item.get("id") == aid
        ]
        if len(matches) != 1:
            raise HTTPException(404, "not_found")
        public = matches[0]
        record = state["_artifacts"][aid]
        if not isinstance(record, dict):
            raise HTTPException(404, "not_found")
        return public, record

    def _artifact_source_kind(self, state, aid, record) -> str | None:
        source_kind = record.get("source_kind")
        if isinstance(source_kind, str):
            return source_kind
        canonical = state.get("_canonical_artifacts", {}).get(aid)
        if not isinstance(canonical, dict):
            return None
        if (
            not isinstance(record.get("source_artifact_id"), str)
            or record["source_artifact_id"] != canonical.get("artifact_id")
            or not isinstance(record.get("source_sha256"), str)
            or record["source_sha256"] != canonical.get("sha256")
            or (
                record.get("projection") == "identity"
                and record.get("sha256") != canonical.get("sha256")
            )
        ):
            return None
        try:
            source_kind = self.inputs.historical_artifact_source_kind(state, canonical)
        except (KeyError, OSError, TypeError, ValueError):
            return None
        return source_kind if isinstance(source_kind, str) else None

    def _artifact_content_class(self, state, aid, public, record) -> ArtifactContentClass:
        source_kind = self._artifact_source_kind(state, aid, record)
        if self._developer_artifact_kind(source_kind):
            return "developer_diagnostic"
        declared = record.get("content_class")
        if declared in ARTIFACT_CONTENT_CLASSES:
            return declared
        if "content_class" in record:
            return "developer_diagnostic"
        if (
            public.get("tool_id") == "P0-10"
            and isinstance(public.get("research_report"), dict)
            and record.get("projection") == "identity"
            and source_kind == "research_report"
        ):
            return "research_report"
        if source_kind is not None and record.get("projection") in {
            "identity",
            "path_redacted_display",
        }:
            return "user_result"
        return "developer_diagnostic"

    def _report_binding_current(self, state, binding) -> bool:
        if not isinstance(binding, dict) or not REPORT_BINDING_FIELDS <= set(binding):
            return False
        if state.get("input_review_required") or state.get("pending_input_change"):
            return False
        if binding.get("input_revision") != str(state.get("_input_revision")):
            return False
        if (
            not isinstance(binding.get("graph_id"), str)
            or not binding["graph_id"]
            or type(binding.get("graph_version")) is not int
            or binding["graph_version"] < 1
            or not isinstance(binding.get("renderer_id"), str)
            or not binding["renderer_id"]
            or not isinstance(binding.get("snapshot_object_version"), str)
            or not binding["snapshot_object_version"]
            or any(
                not isinstance(binding.get(field), str)
                or re.fullmatch(r"[a-f0-9]{64}", binding[field]) is None
                for field in (
                    "graph_manifest_sha256",
                    "snapshot_sha256",
                )
            )
        ):
            return False
        candidates = []
        invalidated = state.get("_invalidated_receipts", {})
        for record in state.get("_input_objects", {}).values():
            if (
                not isinstance(record, dict)
                or record.get("schema_ref") != "bridge://schemas/case-evidence-graph-manifest/v0.1"
                or record.get("receipt_file") in invalidated
            ):
                continue
            try:
                graph = self.inputs.verify(state, record)
            except (KeyError, OSError, TypeError, ValueError):
                continue
            if (
                graph.get("graph_id") == binding["graph_id"]
                and type(graph.get("graph_version")) is int
            ):
                candidates.append((graph["graph_version"], record.get("sha256")))
        if not candidates:
            return False
        current_version = max(version for version, _ in candidates)
        current_hashes = {sha256 for version, sha256 in candidates if version == current_version}
        return binding["graph_version"] == current_version and current_hashes == {
            binding["graph_manifest_sha256"]
        }

    @staticmethod
    def _artifact_acknowledged(state, aid, record) -> bool:
        acknowledgement = state.get("_artifact_acknowledgements", {}).get(aid)
        return (
            isinstance(acknowledgement, dict)
            and isinstance(record.get("sha256"), str)
            and secrets.compare_digest(
                acknowledgement.get("artifact_sha256", ""),
                record["sha256"],
            )
        )

    def projection(self, state, aid):
        public, record = self._artifact_records(state, aid)
        content_class = self._artifact_content_class(state, aid, public, record)
        access_state: ArtifactAccessState
        if content_class == "developer_diagnostic":
            access_state = "denied"
        elif content_class == "research_report":
            binding = record.get("report_binding")
            if not isinstance(binding, dict):
                binding = public.get("research_report")
            access_state = (
                "current"
                if self._report_binding_current(state, binding)
                else "historical_unreviewed"
            )
        else:
            binding = None
            access_state = "available"
        acknowledged = self._artifact_acknowledged(state, aid, record)
        value = dict(public)
        value["content_class"] = content_class
        value["access_state"] = access_state
        value["acknowledged"] = acknowledged
        value["acknowledgement_required"] = (
            access_state == "historical_unreviewed" and not acknowledged
        )
        if content_class == "research_report" and isinstance(binding, dict):
            value["research_report"] = dict(binding)
        if access_state == "historical_unreviewed":
            value["warning"] = HISTORICAL_REPORT_WARNING
            value["acknowledgement_url"] = value["url"] + "/acknowledge"
        return value

    def public(self, state):
        values = []
        for item in state.get("artifacts", []):
            try:
                projected = self.projection(state, item["id"])
            except (HTTPException, KeyError, OSError, TypeError, ValueError):
                continue
            if projected["access_state"] != "denied":
                values.append(projected)
        return values

    def report_context(self, state):
        """Share version/access metadata only, never report prose or private paths."""
        reports = []
        for item in self.public(state):
            if (item.get("content_class") != "research_report"
                    or item.get("media_type") != "text/html"
                    or item.get("access_state") not in {"current", "historical_unreviewed"}):
                continue
            binding = item.get("research_report")
            if not isinstance(binding, dict):
                continue
            revision, version = binding.get("input_revision"), binding.get("graph_version")
            if (not isinstance(revision, str) or re.fullmatch(r"[0-9]{1,9}", revision) is None
                    or type(version) is not int or version < 1):
                continue
            row = {"input_revision": revision, "graph_version": version,
                   "access_state": item["access_state"]}
            if row not in reports:
                reports.append(row)
        return {"reports": reports[-24:]}

    def _read_artifact_bytes(self, state, record, limit):
        path = self.sessions.directory(state["id"]) / "artifacts" / record["file"]
        if path.parent.is_symlink():
            raise HTTPException(404, "not_found")
        data = read_file(path, limit)
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise HTTPException(409, "artifact_integrity_mismatch")
        return data

    def read(self, state, aid, limit=128 * 1024 * 1024):
        _, record = self._artifact_records(state, aid)
        public = self.projection(state, aid)
        if public["access_state"] == "denied":
            raise HTTPException(404, "not_found")
        if public["access_state"] == "historical_unreviewed" and not public["acknowledged"]:
            raise HTTPException(409, "historical_report_acknowledgement_required")
        return public, self._read_artifact_bytes(state, record, limit)

    def acknowledge(self, state, aid):
        _, record = self._artifact_records(state, aid)
        public = self.projection(state, aid)
        if public["access_state"] == "denied":
            raise HTTPException(404, "not_found")
        if public["access_state"] != "historical_unreviewed":
            raise HTTPException(409, "historical_report_acknowledgement_not_required")
        self._read_artifact_bytes(state, record, 128 * 1024 * 1024)
        state.setdefault("_artifact_acknowledgements", {})[aid] = {
            "artifact_sha256": record["sha256"],
            "acknowledged_at": now(),
        }
        self.sessions.save(state)
        return self.projection(state, aid)

    def register(self, state, outcome):
        root = self.sessions.directory(state["id"])
        verified_reports = {}
        report_metadata = {}
        if (
            outcome.request.tool_id == "P0-10"
            and getattr(outcome, "result_schema_ref", None)
            == "bridge://schemas/research-claim-verification-result/v0.2"
        ):
            from bridge.tool_packages.p0_10_claim_verifier.research import (
                research_snapshot_model,
                ResearchClaimVerificationResult,
                render_research_snapshot,
            )

            from .inputs import checked_bytes

            snapshots = [
                item for item in outcome.artifacts if item.path.name == "research_snapshot.json"
            ]
            if snapshots:
                if len(snapshots) != 1:
                    raise ValueError("research_snapshot_binding_invalid")
                source = snapshots[0]
                raw_snapshot = checked_bytes(
                    self.sessions, state, source.path, source.sha256, root=root / "runs"
                )
                snapshot_model = research_snapshot_model(json.loads(raw_snapshot).get("object_version"))
                snapshot = snapshot_model.model_validate_json(raw_snapshot)
                verification = ResearchClaimVerificationResult.model_validate(outcome.result)
                verified_reports = render_research_snapshot(snapshot=snapshot, result=verification)
                report_metadata = {
                    "input_revision": snapshot.input_revision,
                    "graph_id": snapshot.graph_id,
                    "graph_version": snapshot.graph_version,
                    "graph_manifest_sha256": snapshot.graph_manifest_sha256,
                    "snapshot_sha256": snapshot.snapshot_sha256,
                    "renderer_id": snapshot.renderer_id,
                    "snapshot_object_version": snapshot.object_version,
                }

        for artifact in outcome.artifacts:
            path = artifact.path
            try:
                relative = path.relative_to(root / "runs")
            except ValueError:
                raise ValueError("artifact_outside_run")
            current = root / "runs"
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("artifact_symlink")
            suffix = path.suffix.lower()
            if suffix == ".pdf" and artifact.kind != "expression_figure":
                continue
            media = {
                ".png": "image/png",
                ".pdf": "application/pdf",
                ".svg": "image/svg+xml",
                ".json": "application/json",
                ".csv": "text/csv",
                ".tsv": "text/tab-separated-values",
                ".parquet": "application/octet-stream",
                ".html": "text/html",
            }.get(suffix)
            if not media or (suffix == ".html" and path.name not in verified_reports):
                continue
            data = read_file(path, 128 * 1024 * 1024)
            if hashlib.sha256(data).hexdigest() != artifact.sha256:
                raise ValueError("artifact_integrity_mismatch")
            is_research_report = path.name in verified_reports
            if is_research_report and data != verified_reports[path.name]:
                raise ValueError("research_report_content_mismatch")
            if suffix == ".json" and not is_research_report:

                def redact(value):
                    if isinstance(value, dict):
                        return {
                            key: redact(item)
                            for key, item in value.items()
                            if "path" not in key.lower() and key not in {"output_dir"}
                        }
                    if isinstance(value, list):
                        return [redact(item) for item in value]
                    return private_text(value) if isinstance(value, str) else value

                data = json.dumps(redact(json.loads(data)), ensure_ascii=False).encode()
            aid = uid()
            write_file(root / "artifacts" / (aid + suffix), data)
            kind = (
                "download"
                if is_research_report or suffix == ".pdf"
                else (
                    "figure"
                    if suffix in {".png", ".svg"}
                    else "evidence"
                    if suffix == ".json"
                    else "table"
                )
            )
            content_class: ArtifactContentClass = (
                "research_report"
                if is_research_report
                else (
                    "developer_diagnostic"
                    if self._developer_artifact_kind(artifact.kind)
                    else "user_result"
                )
            )
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", path.name)[:100]
            if suffix == ".json" and not is_research_report:
                name = name.removesuffix(".json") + ".display-redacted.json"
            state["artifacts"].append(
                {
                    "id": aid,
                    "name": name,
                    "kind": kind,
                    "media_type": media,
                    "url": f"/api/sessions/{state['id']}/artifacts/{aid}",
                    "tool_id": outcome.request.tool_id,
                    "content_class": content_class,
                    **({"research_report": report_metadata} if is_research_report else {}),
                }
            )
            self.inputs.initialize(state)
            state["_canonical_artifacts"][aid] = {
                "path": str(artifact.path),
                "sha256": artifact.sha256,
                "artifact_id": artifact.artifact_id,
                "receipt_file": state["_tool_runs"][-1]["file"],
                "receipt_sha256": state["_tool_runs"][-1]["sha256"],
            }
            state["_artifacts"][aid] = {
                "file": aid + suffix,
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_artifact_id": artifact.artifact_id,
                "source_sha256": artifact.sha256,
                "projection": (
                    "path_redacted_display"
                    if suffix == ".json" and not is_research_report
                    else "identity"
                ),
                "source_kind": artifact.kind,
                "content_class": content_class,
                **({"report_binding": report_metadata} if is_research_report else {}),
            }
            self.sessions.save(state)
