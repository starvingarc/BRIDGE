"""Read-only scope and producer selection shared by interpretation and reports.

Callers supply registered records and verified-read adapters, never a Service.
Use an instance only within one synchronous operation; it does not cache file
verification or own a second persistent result store.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any
from hashlib import sha256

from bridge.tool_packages._structured_runtime import canonical_json_bytes


def producer_identity(run):
    """Execution name, version and canonical content jointly identify a producer."""
    return ("tool-run:" + run.run_id, run.tool_version,
            sha256(canonical_json_bytes(run.model_dump(mode="json"))).hexdigest())


class EvidenceSources:
    def __init__(self, *, records: Mapping[str, dict], receipts: Sequence[dict],
                 invalidated: Collection[str], read_producer: Callable[[dict], Any],
                 verify: Callable[[dict], dict]):
        self._records = records
        self._receipts = receipts
        self._invalidated = invalidated
        self._read_producer = read_producer
        self._verify = verify

    @staticmethod
    def _belongs(record, receipt):
        return (record.get("source") == "tool_output"
                and record.get("producer_tool_id") == receipt["tool_id"]
                and record.get("receipt_file") == receipt["file"]
                and record.get("receipt_sha256") == receipt["sha256"])

    def _usable(self, receipt):
        return (receipt["file"] not in self._invalidated
                and receipt["state"] in {"succeeded", "partial"})

    def assessment_receipts(self, roots, admissions):
        """Current admissions first, then exactly pinned history; no implicit reuse."""
        plans = {row["plan_id"]: row for row in admissions}
        admitted, reused = [], []
        for receipt in self._receipts:
            if not self._usable(receipt):
                continue
            admission = plans.get(receipt.get("plan_id"))
            if admission is not None:
                if admission["tool_id"] != receipt["tool_id"]:
                    raise ValueError("assessment_producer_mismatch")
                admitted.append(receipt)
            elif any(self._belongs(record, receipt) for record in roots.values()):
                reused.append(receipt)
        return admitted + reused

    def outputs(self, pool, tool_id, schema):
        """Resolve verified canonical outputs by exact receipt, never run name alone."""
        schemas = (schema,) if isinstance(schema, str) else schema
        found = []
        for receipt in self._receipts:
            if receipt["tool_id"] != tool_id or not self._usable(receipt):
                continue
            identifiers = [key for key, record in pool.items()
                           if self._belongs(record, receipt) and record["schema_ref"] in schemas]
            if identifiers:
                run = self._read_producer(receipt)
                found.extend((key, self._verify(pool[key]), run) for key in identifiers)
        return found

    def pool(self, roots, admissions):
        """Pinned roots plus verified results of this scope's actual admissions."""
        pool = dict(roots)
        graph_producers = set()
        # A pinned historical graph carries its exact compiler inputs in the
        # verified receipt. Append must read that provenance, not invent it.
        for record in tuple(pool.values()):
            if (record.get("producer_tool_id") != "P0-09"
                    or record.get("schema_ref") != "bridge://schemas/case-evidence-graph-manifest/v0.1"):
                continue
            receipt = next((item for item in self._receipts
                if item["file"] == record["receipt_file"]
                and item["sha256"] == record["receipt_sha256"]), None)
            if receipt is None:
                raise ValueError("canonical_graph_history_required")
            if receipt["tool_id"] != "P0-09" or receipt["state"] not in {"succeeded", "partial"}:
                raise ValueError("canonical_source_producer_mismatch")
            run = self._read_producer(receipt)
            for ref in run.request.object_inputs:
                if ref.role not in {"compilation_bundle", "claim_registry", "evidence_family_registry"}:
                    continue
                source = self._records.get(ref.input_id)
                if (source is None or source["sha256"] != ref.sha256
                        or source["schema_ref"] != ref.schema_ref or source["path"] != str(ref.path)):
                    raise ValueError("canonical_graph_history_mismatch")
                value = self._verify(source)
                pool[ref.input_id] = source
                if ref.role == "compilation_bundle":
                    graph_producers.update((row["object_id"], row["object_version"], row["content_hash"])
                        for row in value["object_catalog"] if row["node_type"] == "ToolRun")
        # A pinned graph authorizes its immutable provenance, including a
        # historical native profile hidden by the latest-result root selection.
        # Names alone are insufficient for legacy execution-ID collisions.
        if graph_producers:
            for receipt in self._receipts:
                if not self._usable(receipt) or receipt["tool_id"] not in {"P0-02", "P0-06"}:
                    continue
                run = self._read_producer(receipt)
                if producer_identity(run) not in graph_producers:
                    continue
                for identifier, record in self._records.items():
                    if self._belongs(record, receipt):
                        self._verify(record)
                        pool[identifier] = record
        for receipt in self.assessment_receipts({}, admissions):
            run = self._read_producer(receipt)
            for ref in getattr(run.request, "object_inputs", []):
                record = self._records[ref.input_id]
                self._verify(record)
                pool[ref.input_id] = record
            for identifier, record in self._records.items():
                if self._belongs(record, receipt):
                    self._verify(record)
                    pool[identifier] = record
        return pool
