"""Bind scoped canonical measurements and preserve candidate-only report paths."""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from fastapi import HTTPException

from bridge.tool_packages.p0_08_evidence_sufficiency.models import DomainGateInput, P0DomainId
from .inputs import Selection
from .scientific_inputs import DraftIdentity, encoded


DOMAIN_LABELS = {"target_identity": "目标身份", "regional_fidelity": "区域一致性",
    "developmental_compatibility": "发育阶段兼容性", "off_target_control": "非目标细胞控制",
    "proliferation_stress_response": "增殖与应激"}


class ReportPreparation(DraftIdentity):
    tool_id: Literal["P0-08", "P0-09", "P0-10"] = "P0-08"


class ReportInputs:
    def __init__(self, service):
        self.service = service


    @staticmethod
    def _identity(pointer):
        return None if pointer is None else (pointer["object_id"], pointer["object_version"])

    def _producer(self, state, receipt):
        """Return an actual source-bound producer; Schema resemblance is insufficient."""
        inputs = self.service.inputs
        run, outputs = inputs.producer_objects(state, receipt, receipt["tool_id"], {"measurement_result_v2"})
        refs = {ref.role: ref for ref in getattr(run.request, "object_inputs", [])}
        if not {"product_case", "product_definition_card", "measurement_spec"} <= set(refs):
            return None
        if "qc_readiness_profile" not in refs:
            if receipt["tool_id"] != "P0-06" or not {
                    "process_method_input", "biological_unit_attestation_receipt",
                    "biological_unit_manifest", "biological_unit_assignment"} <= set(refs):
                return None
            # P0-06's source-bound mode carries the selected view via its
            # producer-derived case, rather than a direct QC input role.
            case_record = state["_input_objects"][refs["product_case"].input_id]
            qc_ids = [identifier for identifier in case_record.get("derivation_inputs", {})
                if state["_input_objects"][identifier]["schema_ref"] == "bridge://schemas/qc-readiness-profile/v0.2"
                and state["_input_objects"][identifier].get("producer_tool_id") == "P0-01"]
            if len(qc_ids) != 1:
                return None
            from bridge.toolkit.contracts import StructuredInputRef
            record = state["_input_objects"][qc_ids[0]]
            refs["qc_readiness_profile"] = StructuredInputRef(input_id=qc_ids[0], role="qc_readiness_profile",
                **{key: record[key] for key in ("path", "sha256", "schema_ref", "object_version")})
        values = {}
        for role, ref in refs.items():
            record = state["_input_objects"].get(ref.input_id)
            if (record is None or record["path"] != str(ref.path)
                    or any(record[key] != getattr(ref, key)
                           for key in ("sha256", "schema_ref", "object_version"))):
                raise ValueError("canonical_source_binding_mismatch")
            values[role] = inputs.verify(state, record)
        case, definition, qc = (values[role] for role in
                                ("product_case", "product_definition_card", "qc_readiness_profile"))
        view = qc.get("selected_data_view")
        if (view is None or case["product_definition_ref"] != {
                "object_id": definition["product_definition_id"], "object_version": definition["definition_version"]}
                or view["sample_or_preparation_ref"] != case["sample_or_preparation_ref"]["object_id"] + "@" + case["sample_or_preparation_ref"]["object_version"]
                or view.get("biological_unit_manifest_sha256") != case.get("biological_unit_manifest_sha256")
                or ("cell_state_evidence_profile" in values and values["cell_state_evidence_profile"].get("input_data_view") != view)):
            raise ValueError("measured_source_case_view_mismatch")
        canonical = outputs.get("measurement_result_v2", [])
        receipt_values = {value.measurement_id: value.model_dump(mode="json") for value in run.measurements}
        for _, value in canonical:
            original = receipt_values.get(value["measurement_id"])
            if (original is None or any(value.get(key) != item for key, item in original.items())
                    or value.get("source_run_ref") != "tool-run:" + run.run_id + "@" + run.tool_version
                    or value.get("source_execution_state") != receipt["state"]):
                raise ValueError("canonical_measurement_binding_mismatch")
        return {"run": run, "receipt": receipt, "refs": refs, "values": values,
                "case": (case["product_case_id"], case["case_version"]), "view": view,
                "measurements": canonical}

    def assessment_resource_ids(self, state, upload_id, selections, view):
        """Pin only producer roots applicable to explicitly selected measured requirements."""
        selected = selections.get("P0-08", {})
        domains = [self.service.inputs.verify(state, state["_input_objects"][row["input_id"]])
                   for row in selected.get("object_inputs", []) if row["role"] == "domain_gate_input"]
        case_refs = {self._identity(row.get("product_case")) for row in domains
                     if row.get("measurement_spec_input_id")}
        if not case_refs or view is None:
            return []
        identifiers = set()
        for receipt in state.get("_tool_runs", []):
            if receipt["tool_id"] not in {"P0-03", "P0-04", "P0-05", "P0-06"} or receipt["state"] not in {"succeeded", "partial"}:
                continue
            source = self._producer(state, receipt)
            if source is None or source["case"] not in case_refs or source["view"] != view:
                continue
            if view["parent_asset_id"] != upload_id:
                continue
            identifiers.update(ref.input_id for ref in source["refs"].values())
            identifiers.update(identifier for identifier, _ in source["measurements"])
        return sorted(identifiers)

    def _measured_sources(self, state, scope):
        pool = self.service.inputs.assessment_pool(state, scope)
        receipts = {record.get("receipt_file") for record in pool.values()
                    if record.get("source") == "tool_output"
                    and record.get("producer_tool_id") in {"P0-03", "P0-04", "P0-05", "P0-06"}
                    and record["schema_ref"] == "bridge://schemas/measurement-result/v0.2"}
        sources = []
        for receipt in state.get("_tool_runs", []):
            if receipt["file"] not in receipts:
                continue
            source = self._producer(state, receipt)
            if source is None:
                continue
            view = source["view"]
            if (view["parent_asset_id"] != scope.upload_id
                    or view["parent_asset_sha256"] != scope.binding["upload"]["sha256"]
                    or (scope.binding["data_view"] is not None and view != scope.binding["data_view"])):
                raise ValueError("measured_source_case_view_mismatch")
            if any(ref.input_id not in pool for ref in source["refs"].values()):
                raise ValueError("measured_source_outside_scope")
            source["measurements"] = [(identifier, value) for identifier, value in source["measurements"] if identifier in pool]
            sources.append(source)
        return pool, sources

    def assessment_selection(self, state, scope, allowed, selection):
        if allowed.tool_id == "P0-09" and allowed.mode_id in {"case_initial_v2", "case_append_v2", "case_query"}:
            # Existing explicitly prepared missingness stages keep their release path.
            if any(row.role == "evidence_sufficiency_run_result" for row in selection.object_inputs):
                return selection
            return self._graph_selection(state, scope, allowed, selection)
        if (allowed.tool_id, allowed.mode_id) != ("P0-08", "default"):
            return selection
        inputs = self.service.inputs
        templates = [(choice.input_id, inputs.verify(state, state["_input_objects"][choice.input_id]))
                     for choice in selection.object_inputs if choice.role == "domain_gate_input"]
        if not templates:
            raise ValueError("measured_domain_requirements_required")
        # The separately approved missingness-only flow retains its original contract.
        if all(not value.get("measurement_spec_input_id") for _, value in templates):
            return selection
        pool, sources = self._measured_sources(state, scope)
        choices = {(choice.role, choice.input_id) for choice in selection.object_inputs
                   if choice.role != "domain_gate_input"}
        single_domain = {"P0-04": "developmental_compatibility", "P0-05": "off_target_control",
                         "P0-06": "proliferation_stress_response"}
        for template_id, template in templates:
            if template_id not in pool:
                raise ValueError("measured_requirements_outside_scope")
            spec_id = template.get("measurement_spec_input_id")
            if spec_id not in pool:
                raise ValueError("measured_measurement_spec_required")
            spec = inputs.verify(state, pool[spec_id])
            matching = [source for source in sources
                        if source["case"] == self._identity(template.get("product_case"))
                        and self._identity(source["values"]["product_case"]["product_definition_ref"])
                            == self._identity(template.get("product_definition"))
                        and source["refs"]["measurement_spec"].input_id == spec_id]
            if not matching:
                raise ValueError("applicable_measured_source_required")
            explicit = template["measurement_result_input_ids"]
            if not explicit and any(source["run"].request.tool_id == "P0-03" for source in matching):
                raise ValueError("measured_domain_metric_binding_required")
            matching = [source for source in matching
                        if single_domain.get(source["run"].request.tool_id, template["domain_id"]) == template["domain_id"]]
            if not matching:
                raise ValueError("measured_producer_domain_mismatch")
            # Multiple reruns are not independent replicates. An explicit subset resolves ambiguity.
            if explicit:
                matching = [source for source in matching if set(explicit) <= {identifier for identifier, _ in source["measurements"]}]
            if len(matching) != 1:
                raise ValueError("canonical_measurement_source_ambiguous" if matching else "canonical_measurement_subset_mismatch")
            source, = matching
            measurements = [(identifier, value) for identifier, value in source["measurements"]
                            if not explicit or identifier in explicit]
            if not measurements:
                raise ValueError("canonical_measurement_required")
            if any(value["measurement_spec_id"] != spec["measurement_spec_id"]
                   or value["measurement_spec_version"] != spec["version"] for _, value in measurements):
                raise ValueError("canonical_measurement_spec_mismatch")
            qc_id = source["refs"]["qc_readiness_profile"].input_id
            if template.get("qc_profile_input_id") not in {None, qc_id}:
                raise ValueError("measured_qc_binding_mismatch")
            # Keep all scientific requirements, validation/prior/sensitivity records and evidence refs.
            bindings = [("measurement_spec", spec_id), ("qc_readiness_profile", qc_id),
                        ("product_case", source["refs"]["product_case"].input_id),
                        *(("measurement_result", identifier) for identifier, _ in measurements)]
            for field, role in (("validation_record_input_ids", "validation_record"),
                                ("prior_record_input_ids", "prior_applicability_record"),
                                ("sensitivity_record_input_ids", "sensitivity_record")):
                for identifier in template[field]:
                    if identifier not in pool:
                        raise ValueError("measured_requirement_record_outside_scope")
                    bindings.append((role, identifier))
            payload = {**template, "measurement_result_input_ids": sorted(identifier for identifier, _ in measurements),
                       "qc_profile_input_id": qc_id}
            from .scientific_inputs import digest
            payload["domain_gate_input_id"] = "domain-gate-input:assessment-" + digest(payload)[:24]
            identifier = inputs.add_derived_object(state, tool_id="P0-08", mode_id="default",
                role="domain_gate_input", schema_ref="bridge://schemas/domain-gate-input/v0.1",
                payload=payload, dependencies=[template_id, *(identifier for _, identifier in bindings)])
            choices.update(bindings)
            choices.add(("domain_gate_input", identifier))
        from .inputs import ObjectChoice
        return selection.model_copy(update={"object_inputs": [ObjectChoice(role=role, input_id=identifier)
                                     for role, identifier in sorted(choices)]})


    def _canonical_outputs(self, state, pool, tool_id, schema):
        inputs = self.service.inputs
        found = []
        for receipt in state.get("_tool_runs", []):
            if receipt["tool_id"] != tool_id or receipt["state"] not in {"succeeded", "partial"}:
                continue
            identifiers = [identifier for identifier, record in pool.items()
                if record.get("source") == "tool_output" and record.get("producer_tool_id") == tool_id
                and record.get("receipt_file") == receipt["file"] and record.get("receipt_sha256") == receipt["sha256"]
                and record["schema_ref"] == schema]
            for identifier in identifiers:
                run, _ = inputs.producer_objects(state, receipt, tool_id, set())
                found.append((identifier, inputs.verify(state, pool[identifier]), run))
        return found

    def _latest_graph(self, state, pool, case_ref):
        found = [row for row in self._canonical_outputs(state, pool, "P0-09",
                 "bridge://schemas/case-evidence-graph-manifest/v0.1")
                 if self._identity(row[1]["product_case_ref"]) == case_ref]
        if not found:
            return None
        latest = max(found, key=lambda row: row[1]["graph_version"])
        if len({pool[identifier]["sha256"] for identifier, graph, _ in found
                if graph["graph_version"] == latest[1]["graph_version"]}) != 1:
            raise ValueError("canonical_graph_version_ambiguous")
        return latest

    @staticmethod
    def _assertion_signature(bundle):
        """Registration/base bookkeeping does not make supplied assertions new."""
        from .scientific_inputs import digest
        value = {key: item for key, item in bundle.items()
                 if key not in {"bundle_id", "base_graph_ref", "prior_evidence_records", "prior_requirements"}}
        value["candidate_records"] = [{key: item for key, item in row.items()
            if key not in {"candidate_id", "created_at", "sufficiency_profile_input_id"}}
            for row in value["candidate_records"]]
        return digest(value)

    def assessment_gaps(self, state, scope, allowed):
        """Keep unresolved interpretation visible without suppressing a useful append."""
        if allowed.tool_id != "P0-09" or allowed.mode_id not in {"case_initial_v2", "case_append_v2"}:
            return []
        inputs = self.service.inputs
        roots = {row["role"]: row["input_id"] for row in
                 scope.binding["selections"].get("P0-09", {}).get("object_inputs", [])}
        pool = inputs.assessment_pool(state, scope)
        if roots.get("compilation_bundle") not in pool:
            return []
        template = inputs.verify(state, pool[roots["compilation_bundle"]])
        case_ref = self._identity(template["product_case_ref"])
        results = [value for _, value, _ in self._canonical_outputs(state, pool, "P0-08",
            "bridge://schemas/evidence-sufficiency-run-result/v0.2")
            if self._identity(value["case_summary"]["product_case_ref"]) == case_ref]
        if not results:
            return []
        asserted = {self._identity(row["measurement_result_ref"]) for row in template["candidate_records"]}
        return ["measured_claim_binding_required"] if any(
            self._identity(ref) not in asserted
            for profile in results[-1]["profiles"] for ref in profile["measurement_result_refs"]) else []

    def _graph_selection(self, state, scope, allowed, selection):
        from .inputs import ObjectChoice
        from .scientific_inputs import digest
        from bridge.tool_packages.p0_09_evidence_compiler.models import EvidenceCompilationBundle, EvidenceCandidate, MissingEvidenceObservation
        inputs = self.service.inputs
        pool = inputs.assessment_pool(state, scope)
        source_selection = scope.binding["selections"].get("P0-09", {})
        roots = {row["role"]: row["input_id"] for row in source_selection.get("object_inputs", [])}
        if allowed.mode_id == "case_query" and "evidence_graph_query" in roots:
            if roots.get("evidence_graph_manifest") not in pool:
                raise ValueError("canonical_case_graph_required")
            if roots["evidence_graph_query"] not in pool:
                raise ValueError("canonical_graph_query_required")
            query = inputs.verify(state, pool[roots["evidence_graph_query"]])
            supplied_graph = inputs.verify(state, pool[roots["evidence_graph_manifest"]])
            latest = self._latest_graph(state, pool, self._identity(supplied_graph["product_case_ref"]))
            return selection.model_copy(update={"object_inputs": [
                ObjectChoice(role="evidence_graph_query", input_id=roots["evidence_graph_query"]),
                ObjectChoice(role="evidence_graph_manifest", input_id=latest[0] if latest else roots["evidence_graph_manifest"])]})
        if "compilation_bundle" not in roots:
            raise ValueError("measured_graph_assertions_required")
        template_id = roots["compilation_bundle"]
        if template_id not in pool:
            raise ValueError("measured_graph_policy_outside_scope")
        template = inputs.verify(state, pool[template_id])
        if template["graph_kind"] != "case":
            raise ValueError("measured_graph_case_required")
        case_ref = self._identity(template["product_case_ref"])
        latest = self._latest_graph(state, pool, case_ref)
        if allowed.mode_id == "case_query":
            if latest is None:
                raise ValueError("canonical_case_graph_required")
            query = {"object_version": "0.1.0", "query_name": "get_case_evidence_subgraph",
                "product_case_id": case_ref[0], "evidence_tiers": ["formal", "shadow", "exploratory"],
                "max_depth": 2, "max_nodes": 100}
            identifier = inputs.add_derived_object(state, tool_id="P0-09", mode_id="case_query",
                role="evidence_graph_query", schema_ref="bridge://schemas/evidence-graph-query/v0.1",
                payload=query, dependencies=[template_id])
            return selection.model_copy(update={"object_inputs": [
                ObjectChoice(role="evidence_graph_query", input_id=identifier),
                ObjectChoice(role="evidence_graph_manifest", input_id=latest[0])]})
        registries = {}
        for role in ("evidence_family_registry", "claim_registry", "reconciliation_spec_registry"):
            if roots.get(role) not in pool:
                raise ValueError("measured_graph_resource_required:" + role)
            registries[role] = inputs.verify(state, pool[roots[role]])
        _, sources = self._measured_sources(state, scope)
        sources = [source for source in sources if source["case"] == case_ref]
        if not sources:
            raise ValueError("applicable_measured_source_required")
        case = sources[0]["values"]["product_case"]
        definition_ref = self._identity(case["product_definition_ref"])
        claims = {self._identity({"object_id": claim["claim_id"], "object_version": claim["version"]}): claim
                  for claim in registries["claim_registry"]["claims"]}
        for claim in claims.values():
            if (claim["claim_target_ref"] != case_ref[0] + "@" + case_ref[1]
                    or self._identity(claim["biological_context_ref"]) != definition_ref):
                raise ValueError("measured_graph_policy_case_mismatch")
        sufficiency = [row for row in self._canonical_outputs(state, pool, "P0-08",
                       "bridge://schemas/evidence-sufficiency-run-result/v0.2")
                       if self._identity(row[1]["case_summary"]["product_case_ref"]) == case_ref]
        if not sufficiency:
            raise ValueError("canonical_sufficiency_result_required")
        suff_id, result, _ = sufficiency[-1]
        profiles = {profile["domain_id"]: profile for profile in result["profiles"]}
        if any(self._identity(profile["product_definition_ref"]) != definition_ref for profile in profiles.values()):
            raise ValueError("measured_sufficiency_definition_mismatch")
        if allowed.mode_id == "case_initial_v2" and latest is not None:
            raise ValueError("canonical_graph_append_required")
        if allowed.mode_id == "case_append_v2" and latest is None:
            raise ValueError("canonical_base_graph_required")
        choices = [(role, roots[role]) for role in registries]
        choices.append(("evidence_sufficiency_run_result", suff_id))
        payload = deepcopy(template)
        dependencies = {template_id, suff_id, *(roots[role] for role in registries)}
        prior = []
        if latest is not None:
            graph_id, graph, graph_run = latest
            prior_suff = next((ref.input_id for ref in graph_run.request.object_inputs
                               if ref.role == "evidence_sufficiency_run_result"), None)
            prior_bundle = next(ref.input_id for ref in graph_run.request.object_inputs if ref.role == "compilation_bundle")
            prior_templates = [inputs.verify(state, state["_input_objects"][identifier])
                for identifier in state["_input_objects"][prior_bundle].get("derivation_inputs", {})
                if state["_input_objects"][identifier]["schema_ref"] == "bridge://schemas/evidence-compilation-bundle/v0.1"]
            prior_resources = {ref.role: ref.sha256 for ref in graph_run.request.object_inputs}
            same_assertions = any(self._assertion_signature(value) == self._assertion_signature(template)
                                  for value in prior_templates)
            if (prior_suff == suff_id and same_assertions and
                    all(prior_resources.get(role) == pool[roots[role]]["sha256"] for role in registries)):
                raise ValueError("canonical_graph_inputs_unchanged")
            graph_record = pool[graph_id]
            same_receipt = {identifier: record for identifier, record in pool.items()
                            if record.get("receipt_file") == graph_record["receipt_file"]}
            for role, schema, field in (
                ("base_evidence_record_set", "evidence-record-set", "records"),
                ("base_evidence_requirement_set", "evidence-requirement-set", "requirements")):
                found = [(identifier, inputs.verify(state, record)) for identifier, record in same_receipt.items()
                         if record["schema_ref"] == "bridge://schemas/" + schema + "/v0.1"]
                if len(found) != 1:
                    raise ValueError("canonical_graph_history_required")
                identifier, value = found[0]
                if value["graph_id"] != graph["graph_id"] or value["graph_version"] != graph["graph_version"]:
                    raise ValueError("canonical_graph_history_mismatch")
                choices.append((role, identifier))
                payload["prior_evidence_records" if field == "records" else "prior_requirements"] = value[field]
                if field == "records":
                    prior = value[field]
            choices.append(("base_graph_manifest", graph_id))
            base_roles = dict(choices)
            payload["base_graph_ref"] = {"graph_id": graph["graph_id"], "graph_version": graph["graph_version"],
                "manifest_sha256": graph_record["sha256"], "manifest_input_id": graph_id,
                "record_set_input_id": base_roles["base_evidence_record_set"],
                "requirement_set_input_id": base_roles["base_evidence_requirement_set"]}
        elif template.get("base_graph_ref") is not None:
            raise ValueError("canonical_base_graph_required")
        catalog = {self._identity(row): row for row in template["object_catalog"]}
        measurements = {self._identity({"object_id": value["measurement_id"], "object_version": pool[identifier]["object_version"]}):
                        (identifier, value, source)
                        for source in sources for identifier, value in source["measurements"]}
        families = {(row["evidence_family_id"], row["version"]): row for row in registries["evidence_family_registry"]["families"]}
        candidates = []
        asserted = set()
        for raw in template["candidate_records"]:
            candidate = EvidenceCandidate.model_validate(raw).model_dump(mode="json")
            key = self._identity(candidate["measurement_result_ref"])
            if key not in measurements:
                raise ValueError("measured_claim_binding_required")
            identifier, measurement, source = measurements[key]
            source_case = source["values"]["product_case"]
            spec = source["values"]["measurement_spec"]
            expected = {"value": measurement["raw_value"], "unit": measurement["unit"],
                "numerator": measurement["numerator"], "denominator": measurement["denominator"],
                "metric_id": measurement["metric_name"], "evidence_state": measurement["evidence_state"],
                "tool_run_execution_state": measurement["source_execution_state"],
                "measurement_spec_ref": {"object_id": spec["measurement_spec_id"], "object_version": spec["version"]},
                "product_case_ref": {"object_id": case_ref[0], "object_version": case_ref[1]},
                "sample_or_preparation_ref": source_case["sample_or_preparation_ref"],
                "tool_run_ref": {"object_id": "tool-run:" + source["run"].run_id, "object_version": source["run"].tool_version},
                "interval": None if measurement["interval"] is None else {
                    "lower": measurement["interval"][0], "upper": measurement["interval"][1],
                    "confidence_level": measurement.get("interval_confidence_level"), "method_ref": measurement.get("interval_method_ref")}}
            if any(candidate[field] != value for field, value in expected.items()):
                raise ValueError("measured_assertion_value_or_source_mismatch")
            profile = profiles.get(candidate["domain_id"])
            if (profile is None or key not in {self._identity(ref) for ref in profile["measurement_result_refs"]}
                    or self._identity(profile["measurement_spec_ref"]) != self._identity(candidate["measurement_spec_ref"])):
                raise ValueError("measured_assertion_domain_mismatch")
            family = self._identity(candidate["evidence_family_ref"])
            if family not in families or family[0] not in profile["deduplicated_evidence_family_ids"]:
                raise ValueError("measured_assertion_family_mismatch")
            context = candidate["biological_context"]
            if (context["context_id"], context["context_version"]) != definition_ref:
                raise ValueError("measured_assertion_context_mismatch")
            facts = scope.binding["intake"]["facts"]
            for field, value in context.items():
                if field not in {"context_id", "context_version"} and value is not None and facts.get(field) != value:
                    raise ValueError("measured_assertion_context_mismatch")
            if not set(measurement["provenance_refs"]) <= set(candidate["provenance_refs"]):
                raise ValueError("measured_assertion_provenance_mismatch")
            record = pool[identifier]
            expected_catalog = [(key, record["sha256"]),
                (self._identity(candidate["tool_run_ref"]), source["receipt"]["sha256"]),
                (self._identity(candidate["measurement_spec_ref"]), source["refs"]["measurement_spec"].sha256),
                (case_ref, source["refs"]["product_case"].sha256),
                (definition_ref, source["refs"]["product_definition_card"].sha256)]
            artifact_refs = [ref for ref in candidate["artifact_refs"] if ref["object_id"] == record["artifact_id"]
                             and ref["object_version"] == record["object_version"]]
            if len(artifact_refs) != 1:
                raise ValueError("measured_assertion_artifact_binding_required")
            expected_catalog.append((self._identity(artifact_refs[0]), record["sha256"]))
            if any(key not in catalog or catalog[key]["content_hash"] != checksum for key, checksum in expected_catalog):
                raise ValueError("measured_assertion_catalog_mismatch")
            dependencies.update([identifier, *(ref.input_id for ref in source["refs"].values())])
            asserted.add(key)
            # Existing immutable observations keep their original profile association.
            fields = set(candidate) - {"candidate_id", "sufficiency_profile_input_id", "created_at", "revision_action", "predecessor_ref"}
            if not any(all(old.get(field) == candidate[field] for field in fields) for old in prior):
                candidates.append({**candidate, "sufficiency_profile_input_id": suff_id})
        missing_domains = set()
        for raw in template["missing_observations"]:
            observation = MissingEvidenceObservation.model_validate(raw).model_dump(mode="json")
            claim = claims.get(self._identity(observation["claim_ref"]))
            if claim is None or self._identity(observation["product_case_ref"]) != case_ref:
                raise ValueError("measured_missing_observation_case_mismatch")
            profile = profiles.get(claim["domain_id"])
            if profile is None:
                raise ValueError("measured_missing_observation_domain_mismatch")
            if profile["measurement_result_refs"] and observation["reason_code"] == "measurement_not_provided":
                raise ValueError("measured_missing_observation_contradicts_source")
            if observation["reason_code"] == "required_channel_not_provided":
                missing_domains.add(claim["domain_id"])
        for domain, profile in profiles.items():
            if any(self._identity(ref) not in asserted for ref in profile["measurement_result_refs"]) and domain not in missing_domains:
                raise ValueError("measured_claim_binding_required")
        payload["candidate_records"] = candidates
        payload["bundle_id"] = "evidence-compilation-bundle:assessment-" + digest({
            "template": pool[template_id]["sha256"], "sufficiency": pool[suff_id]["sha256"],
            "base": payload.get("base_graph_ref")})[:24]
        payload = EvidenceCompilationBundle.model_validate(payload).model_dump(mode="json")
        dependencies.update(identifier for _, identifier in choices)
        identifier = inputs.add_derived_object(state, tool_id="P0-09", mode_id=allowed.mode_id,
            role="compilation_bundle", schema_ref="bridge://schemas/evidence-compilation-bundle/v0.1",
            payload=payload, dependencies=dependencies)
        choices.append(("compilation_bundle", identifier))
        return selection.model_copy(update={"object_inputs": [ObjectChoice(role=role, input_id=identifier)
                                     for role, identifier in choices]})

    def _draft(self, state, body):
        draft = next((row for row in state.get("_scientific_drafts", []) if row["id"] == body.draft_id), None)
        if draft is None or draft["digest"] != body.draft_digest or draft["status"] != "confirmed":
            raise HTTPException(409, "confirmed_scientific_draft_required")
        # Confirmed retry validates dependencies and objects but never registers new objects.
        self.service.scientific_inputs.confirm(state, body.draft_id, body.draft_digest)
        if any(row["tool_id"] in {"P0-03", "P0-04", "P0-05", "P0-06"}
               and row["state"] in {"succeeded", "partial"} for row in state.get("_tool_runs", [])):
            raise HTTPException(409, "measured_report_binding_required")
        return draft

    def _saved(self, state, draft_id, tool_id):
        record = state.get("_report_inputs", {}).get(draft_id)
        return record if tool_id == "P0-08" or not record else record.get("stages", {}).get(tool_id)

    def _verify_saved(self, state, draft_id, saved):
        self._draft(state, DraftIdentity(draft_id=draft_id, draft_digest=saved["draft_digest"]))
        tool_id = saved["selection"]["tool_id"]
        chain = [self._saved(state, draft_id, prior) for prior in ("P0-08", "P0-09") if prior < tool_id]
        checked = set()
        for record in [*chain, saved]:
            if record is None:
                raise ValueError("report_upstream_stage_missing")
            for row in record["selection"]["object_inputs"]:
                if row["input_id"] not in checked:
                    self.service.inputs.verify(state, state["_input_objects"][row["input_id"]])
                    checked.add(row["input_id"])

    def selected_blocker(self, state, tool_id):
        if tool_id not in {"P0-08", "P0-09", "P0-10"}:
            return None
        selection = state.get("_input_selections", {}).get(tool_id, {})
        selected = {row["input_id"] for row in selection.get("object_inputs", [])}
        for identifier in state.get("_report_inputs", {}):
            record = self._saved(state, identifier, tool_id)
            if not record:
                continue
            owned = {row["input_id"] for row in record["selection"]["object_inputs"]
                if state["_input_objects"].get(row["input_id"], {}).get("source") != "package_resource"}
            if not selected.intersection(owned):
                continue
            if selection != record["selection"]:
                return "report_draft_selection_mismatch"
            try:
                self._verify_saved(state, identifier, record)
            except (HTTPException, ValueError, OSError, KeyError):
                return "report_draft_invalid_or_stale"
        return None

    def _result(self, state, draft, tool_id, schema):
        saved = self._saved(state, draft["id"], tool_id)
        if not saved:
            return None
        self._verify_saved(state, draft["id"], saved)
        receipts = {row["file"] for row in state.get("_tool_runs", [])
            if row.get("plan_id") in saved["plan_ids"] and row["tool_id"] == tool_id
            and row["state"] in {"succeeded", "partial"}}
        matches = [(identifier, record) for identifier, record in state["_input_objects"].items()
            if record["source"] == "tool_output" and record.get("producer_tool_id") == tool_id
            and record.get("receipt_file") in receipts and record["schema_ref"] == schema]
        if not matches:
            return None
        identifier, record = matches[-1]
        return identifier, self.service.inputs.verify(state, record)

    def _prepare_downstream(self, state, body):
        from .app import now
        from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard
        from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyRunResultV2
        from bridge.tool_packages.p0_09_evidence_compiler.candidate_policy import build_missingness_policy
        if body.tool_id == "P0-10":
            return self._prepare_verification(state, body)
        draft = self._draft(state, body)
        try:
            upstream = self._result(state, draft, "P0-08", "bridge://schemas/evidence-sufficiency-run-result/v0.2")
            if upstream is None:
                raise ValueError("canonical_missingness_result_required")
            trial = deepcopy(state)
            saved = self._saved(trial, draft["id"], body.tool_id)
            if saved is None:
                case = self.service.inputs.verify(trial, trial["_input_objects"][draft["object_ids"]["product_case"]])
                definition = self.service.inputs.verify(trial, trial["_input_objects"][draft["object_ids"]["product_definition_card"]])
                objects = build_missingness_policy(ProductCase.model_validate(case),
                    ProductDefinitionCard.model_validate(definition),
                    EvidenceSufficiencyRunResultV2.model_validate(upstream[1]), created_at=now())
                choices = [{"role": "evidence_sufficiency_run_result", "input_id": upstream[0]}]
                schemas = {"compilation_bundle": "evidence-compilation-bundle",
                    "evidence_family_registry": "evidence-family-registry", "claim_registry": "claim-registry",
                    "reconciliation_spec_registry": "reconciliation-spec-registry"}
                for role, model in objects.items():
                    identifier = self.service.inputs.add_object(trial, tool_id=body.tool_id, mode_id="case_initial_v2",
                        role=role, schema_ref="bridge://schemas/" + schemas[role] + "/v0.1",
                        object_version="0.1.0", data=encoded(model.model_dump(mode="json")))
                    choices.append({"role": role, "input_id": identifier})
                selection = Selection(tool_id=body.tool_id, mode_id="case_initial_v2", asset_ids=[],
                    object_inputs=choices, measurement_spec_ref=None).model_dump(mode="json")
                saved = {"draft_digest": draft["digest"], "selection": selection, "plan_ids": []}
                trial["_report_inputs"][draft["id"]].setdefault("stages", {})[body.tool_id] = saved
            self._verify_saved(trial, draft["id"], saved)
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "canonical_missingness_result_or_candidate_policy_invalid") from None
        self._propose_downstream(state, trial, saved, body.tool_id)

    def _propose_downstream(self, state, trial, saved, tool_id):
        trial["_input_selections"][tool_id] = saved["selection"]
        self.service.controls.fence(trial)
        trial["_input_revision"] += 1
        self.service.prepare_analysis(trial, tool_id)
        if trial.get("plan") and trial["plan"]["status"] == "proposed":
            trial["plan"]["summary"] = {
                "P0-09": "P0-09 整理当前证据：使用候选、未审阅规则，将本样本五个未评估域登记为缺失要求。不生成测量，不建立独立重复，不给产品打分或判定合格。请单独确认。",
                "P0-10": "P0-10 核验内部报告：报告仅说明当前缺失证据，使用现有发布规则逐条核对。规则尚未支持此类表述，预计会保留发布受阻结果；不会公开导出。请单独确认。",
            }[tool_id]
            saved["plan_ids"].append(trial["plan"]["id"])
        self.service.save(trial)
        state.update(trial)

    def _prepare_verification(self, state, body):
        from .app import now
        from bridge.tool_packages.p0_10_claim_verifier.models import ClaimBlock, ReportDraft, report_content_hash
        from bridge.tool_packages.p0_10_claim_verifier.verifier import load_release_contract
        draft = self._draft(state, body)
        try:
            graph = self._result(state, draft, "P0-09", "bridge://schemas/case-evidence-graph-manifest/v0.1")
            records = self._result(state, draft, "P0-09", "bridge://schemas/evidence-record-set/v0.1")
            requirements = self._result(state, draft, "P0-09", "bridge://schemas/evidence-requirement-set/v0.1")
            if graph is None or records is None or requirements is None:
                raise ValueError("canonical_candidate_graph_required")
            if (records[1]["records"] or len(requirements[1]["requirements"]) != 5
                    or any(row["state"] != "open" for row in requirements[1]["requirements"])
                    or any(row[1]["graph_id"] != graph[1]["graph_id"] or row[1]["graph_version"] != graph[1]["graph_version"]
                           for row in (records, requirements))):
                raise ValueError("unmeasured_candidate_graph_required")
            trial = deepcopy(state)
            saved = self._saved(trial, draft["id"], "P0-10")
            if saved is None:
                policy_saved = self._saved(trial, draft["id"], "P0-09")
                claim_id = next(row["input_id"] for row in policy_saved["selection"]["object_inputs"] if row["role"] == "claim_registry")
                claims = self.service.inputs.verify(trial, trial["_input_objects"][claim_id])["claims"]
                if {row["claim_ref"]["object_id"] + "@" + row["claim_ref"]["object_version"] for row in requirements[1]["requirements"]} != {
                        row["claim_id"] + "@" + row["version"] for row in claims}:
                    raise ValueError("candidate_claim_requirements_mismatch")
                case = self.service.inputs.verify(trial, trial["_input_objects"][draft["object_ids"]["product_case"]])
                release = load_release_contract()
                report = {
                    "object_version": "0.1.0", "report_id": "report:web-" + draft["id"],
                    "report_version": "0.1.0", "audience": "internal_research", "language": "zh",
                    "evidence_record_set_ref": records[1]["record_set_id"] + "@" + records[1]["record_set_version"],
                    "claim_policy_ref": release.claim_policy.ref, "statement_registry_ref": release.statement_registry.ref,
                    "claim_blocks": [{
                        "claim_id": "claim-block:web-" + draft["id"] + ":" + claim["domain_id"], "claim_version": "0.1.0",
                        "claim_ref": claim["claim_id"] + "@" + claim["version"],
                        "product_case_ref": case["product_case_id"] + "@" + case["case_version"],
                        "claim_type": "availability_claim", "language": "zh",
                        "text": DOMAIN_LABELS[claim["domain_id"]] + "：当前未提供正式测量，尚未评估。缺失不等于阴性。",
                        "authoring_channel": "deterministic_renderer",
                    } for claim in claims],
                    "renderer_id": "BRIDGE-WEB-MISSINGNESS-DRAFT", "renderer_version": "0.1.0",
                    "authoring_channel": "deterministic_renderer", "created_at": now().replace("+00:00", "Z"),
                }
                boundary = next(row for row in release.statement_registry.statements if row.ref == "statement:safety-boundary@0.1.0")
                report["claim_blocks"].append({
                    "claim_id": "claim-block:web-" + draft["id"] + ":boundary", "claim_version": "0.1.0",
                    "claim_ref": report["claim_blocks"][0]["claim_ref"],
                    "product_case_ref": report["claim_blocks"][0]["product_case_ref"],
                    "claim_type": "policy_or_boundary_statement", "language": "zh",
                    "text": boundary.texts["zh"], "statement_refs": [boundary.ref],
                    "authoring_channel": "deterministic_renderer",
                })
                report["claim_blocks"] = [ClaimBlock.model_validate(row).model_dump(mode="json") for row in report["claim_blocks"]]
                report["content_hash"] = report_content_hash(report)
                report = ReportDraft.model_validate(report)
                identifier = self.service.inputs.add_object(trial, tool_id="P0-10", mode_id="default",
                    role="report_draft", schema_ref="bridge://schemas/report-draft/v0.1",
                    object_version="0.1.0", data=encoded(report.model_dump(mode="json")))
                self.service.inputs.package_options(trial)
                choices = [{"role": "report_draft", "input_id": identifier},
                           {"role": "evidence_graph_manifest", "input_id": graph[0]}]
                for role in ("claim_policy_spec", "statement_registry"):
                    resource_id = next(key for key, row in trial["_input_objects"].items()
                        if row["source"] == "package_resource" and row["label"] == role)
                    choices.append({"role": role, "input_id": resource_id})
                saved = {"draft_digest": draft["digest"], "plan_ids": [],
                    "selection": Selection(tool_id="P0-10", mode_id="default", asset_ids=[],
                        object_inputs=choices, measurement_spec_ref=None).model_dump(mode="json")}
                trial["_report_inputs"][draft["id"]].setdefault("stages", {})["P0-10"] = saved
            self._verify_saved(trial, draft["id"], saved)
        except (ValueError, OSError, KeyError, StopIteration):
            raise HTTPException(409, "canonical_candidate_graph_or_report_invalid") from None
        self._propose_downstream(state, trial, saved, "P0-10")

    def public_report(self, state, draft):
        saved = self._saved(state, draft["id"], "P0-10")
        if not saved or draft["status"] != "confirmed":
            return None
        try:
            self._verify_saved(state, draft["id"], saved)
            identifier = next(row["input_id"] for row in saved["selection"]["object_inputs"] if row["role"] == "report_draft")
            report = self.service.inputs.verify(state, state["_input_objects"][identifier])
            verification = self._result(state, draft, "P0-10", "bridge://schemas/claim-verification-result/v0.1")
            if verification and (verification[1]["report_draft_ref"] != report["report_id"] + "@" + report["report_version"]
                    or verification[1]["report_content_hash"] != report["content_hash"]):
                raise ValueError("report_verification_binding_mismatch")
            return {
                "audience": report["audience"], "policy_state": "candidate_unreviewed",
                "sections": [{"domain_id": row["claim_id"].rsplit(":", 1)[-1],
                    "title": DOMAIN_LABELS[row["claim_id"].rsplit(":", 1)[-1]], "text": row["text"],
                    "evidence_state": "not_assessed"} for row in report["claim_blocks"] if row["claim_type"] == "availability_claim"],
                "boundaries": [row["text"] for row in report["claim_blocks"] if row["claim_type"] == "policy_or_boundary_statement"],
                "verification": None if verification is None else {
                    "release_state": verification[1]["release_state"],
                    "public_export_eligibility": verification[1]["public_export_eligibility"],
                    "reason_codes": sorted({row["reason_code"] for row in verification[1]["check_records"]})},
                "next_actions": ["完成候选来源与产品角色的生物学审阅，再准备正式域测量。",
                    "确认样本、制备与独立分组关系；不能用细胞数代替独立重复。",
                    "缺失性报告表述需通过声明规则评审；当前不可公开导出。"],
            }
        except (HTTPException, ValueError, OSError, KeyError, StopIteration):
            return None


    def prepare(self, state, body):
        if body.tool_id != "P0-08":
            return self._prepare_downstream(state, body)
        from .app import now
        draft = self._draft(state, body)
        trial = deepcopy(state)
        saved = trial.setdefault("_report_inputs", {}).get(draft["id"])
        if saved is None:
            case_id = draft["object_ids"]["product_case"]
            case = self.service.inputs.verify(trial, trial["_input_objects"][case_id])
            self.service.inputs.package_options(trial)
            gate_id = next(identifier for identifier, record in trial["_input_objects"].items()
                           if record["source"] == "package_resource" and record["label"] == "gate_rule_spec")
            self.service.inputs.verify(trial, trial["_input_objects"][gate_id])
            provenance = [item["object_id"] for item in case["provenance_refs"]]
            choices = [{"role": "product_case", "input_id": case_id}, {"role": "gate_rule_spec", "input_id": gate_id}]
            domains = [DomainGateInput(domain_gate_input_id="domain-gate-input:" + draft["id"] + ":" + domain.value,
                object_version="0.1.0", created_at=now(), domain_id=domain,
                product_case={"object_id": case["product_case_id"], "object_version": case["case_version"], "provenance_refs": provenance},
                product_definition={**case["product_definition_ref"], "provenance_refs": provenance},
                provenance_refs=provenance) for domain in P0DomainId]
            schema = "bridge://schemas/domain-gate-input/v0.1"
            for domain in domains:
                self.service.inputs.validate_object(domain.model_dump(mode="json"), schema, "0.1.0")
            for domain in domains:
                identifier = self.service.inputs.add_object(trial, tool_id="P0-08", mode_id="default",
                    role="domain_gate_input", schema_ref=schema, object_version="0.1.0",
                    data=encoded(domain.model_dump(mode="json")))
                choices.append({"role": "domain_gate_input", "input_id": identifier})
            selection = Selection(tool_id="P0-08", mode_id="default", asset_ids=[],
                object_inputs=choices, measurement_spec_ref=None).model_dump(mode="json")
            saved = {"draft_digest": draft["digest"], "selection": selection, "gate_id": gate_id, "plan_ids": []}
            trial["_report_inputs"][draft["id"]] = saved
        trial["_input_selections"]["P0-08"] = saved["selection"]
        self.service.controls.fence(trial)
        trial["_input_revision"] += 1
        self.service.prepare_analysis(trial, "P0-08")
        if trial.get("plan") and trial["plan"]["status"] == "proposed" and trial["plan"]["steps"][0]["tool_id"] == "P0-08":
            trial["plan"]["summary"] = ("P0-08 未评估与缺失证据检查：五个科学域均未提供正式测量、匹配的数据视图或验证记录。"
                "本次仅用包内规则登记缺项，不将已有 QC 或旧版细胞状态结果冒充这些证据，不判定产品合格。请单独确认。")
            saved["plan_ids"].append(trial["plan"]["id"])
        self.service.save(trial)
        state.update(trial)

    def stages(self, state, draft):
        result = deepcopy(draft["stages"])
        result.append({"tool_id": "P0-07", "state": "blocked", "reason_codes": ["comparison_inputs_not_bound"]})
        previous = draft["status"] == "confirmed"
        for tool_id, schema, ready_reason, blocked_reason in (
            ("P0-08", "evidence-sufficiency-run-result/v0.2", "missingness_only", "scientific_draft_confirmation_required"),
            ("P0-09", "case-evidence-graph-manifest/v0.1", "candidate_missingness_policy", "canonical_missingness_result_required"),
            ("P0-10", "claim-verification-result/v0.1", "internal_draft_only", "compiled_report_required"),
        ):
            status, reasons = ("ready", [ready_reason]) if previous else ("blocked", [blocked_reason])
            try:
                available = previous and self._result(state, draft, tool_id, "bridge://schemas/" + schema) is not None
            except (HTTPException, ValueError, OSError, KeyError):
                available, status, reasons = False, "blocked", ["result_evidence_invalid"]
            if available:
                status = "available"
            previous = bool(available)
            result.append({"tool_id": tool_id, "state": status, "reason_codes": reasons})
        result.extend([
            {"tool_id": "P0-11", "state": "blocked", "reason_codes": ["verified_report_and_export_approval_required"]},
        ])
        return result
