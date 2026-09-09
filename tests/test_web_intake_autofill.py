"""Metadata-first intake is a draft, never implicit analysis approval."""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from test_web_service import client, new_session, settle, confirm_change


def upload_metadata(client, tmp_path, *, days=(28, 28), samples=("PRIVATE_SAMPLE_A", "PRIVATE_SAMPLE_A"),
                    day_column="culture_day", uns=None, extra_obs=None):
    import anndata as ad
    import numpy as np
    import pandas as pd
    from scipy import sparse
    data = ad.AnnData(sparse.csr_matrix(np.ones((len(days), 2), dtype=np.int32)),
        obs=pd.DataFrame({"sample_id": list(samples), "capture_id": list(samples), day_column: list(days)},
                         index=[f"PRIVATE_CELL_{i}" for i in range(len(days))]),
        var=pd.DataFrame({"gene_symbol": ["PRIVATE_GENE_A", "PRIVATE_GENE_B"],
                          "feature_type": ["Gene Expression", "Gene Expression"]},
                         index=["GENE_1", "GENE_2"]))
    for key, values in (extra_obs or {}).items():
        data.obs[key] = list(values)
    data.uns.update(uns or {})
    path = tmp_path / "metadata.h5ad"
    data.write_h5ad(path)
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/uploads", files={"file": ("experiment.h5ad", path.read_bytes())})
    assert response.status_code == 200, response.json()
    return sid, response.json()["uploads"][0]["id"]


def intake(client, sid, aid):
    return client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid}).json()


def test_metadata_day_fills_draft_without_claiming_independence(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    assert value["facts"].get("culture_day") == 28
    assert value["facts"]["sample_id_column"] == "sample_id"
    assert value["facts"]["capture_id_column"] == "capture_id"
    assert value["facts"]["gene_symbol_column"] == "gene_symbol"
    assert value["facts"]["matrix_location"] == "X"
    assert value["facts"]["independent_cultures"] is None
    assert value["facts"]["count_semantics"] == "unknown"
    assert client.get(f"/api/sessions/{sid}").json()["plan"] is None
    assert client.app.state.service.load(sid)["_asset_declarations"] == {}


def test_mixed_sample_days_remain_sample_scoped(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path, days=(21, 28), samples=("A", "B"))
    value = intake(client, sid, aid)
    assert value["facts"].get("culture_day") is None
    samples = value.get("autofill", {}).get("samples", [])
    assert [(x["sample_id"], x["culture_days"]) for x in samples] == [("A", [21]), ("B", [28])]
    assert "culture_day" not in [q["field"] for q in value["autofill"]["questions"]]


def test_questions_omit_known_day_and_internal_classifications(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    questions = value.get("autofill", {}).get("questions", [])
    assert questions and questions[0]["field"] == "target_cell_type"
    assert not ({"culture_day", "product_family", "sampling_context", "count_semantics"} &
                {q["field"] for q in questions})
    for q in questions:
        if q["options"]:
            assert q["options"][-1]["value"] == "__other__"
            assert not any(x["value"] == "unknown" for x in q["options"])


def test_default_target_keeps_lineage_separate_from_developmental_stage(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    question = value["autofill"]["questions"][0]
    response = client.post(f"/api/sessions/{sid}/intake/answer", json={
        "upload_id": aid, "revision": value["autofill"]["revision"],
        "field": question["field"], "value": question["options"][0]["value"], "other": False})
    assert response.status_code == 200
    value = intake(client, sid, aid)
    assert value["facts"]["target_cell_type"] == "midbrain dopaminergic lineage cells"
    assert value["facts"]["target_stage"] is None
    assert value["autofill"]["questions"][0]["field"] == "target_stage"
    assert value["autofill"]["questions"][0]["options"][-1]["value"] == "__other__"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["plan"] is None and not state["input_review_required"]


def test_only_analysis_consumed_fields_are_requested(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path, day_column="harvest_d")
    value = intake(client, sid, aid)
    # Recording an optional answer must not create a requirement to fill its peers.
    response = client.post(f"/api/sessions/{sid}/intake/answer", json={
        "upload_id": aid, "revision": value["autofill"]["revision"],
        "field": "starting_cell_type", "value": "iPSC", "other": False})
    assert response.status_code == 200
    value = intake(client, sid, aid)
    assert value["facts"]["starting_cell_type"] == "iPSC"
    assert value["facts"]["cell_line"] is None
    assert value["facts"]["culture_day"] is None
    assert value["facts"]["sequencing_method"] is None
    assert {q["field"] for q in value["autofill"]["questions"]} == {
        "target_cell_type", "target_stage", "assay", "culture_batch_role"}
    for field, answer in [("target_cell_type", "midbrain dopaminergic progenitors"),
                          ("target_stage", "progenitor"), ("assay", "scRNA-seq"),
                          ("independent_cultures", 1)]:
        value = intake(client, sid, aid)
        response = client.post(f"/api/sessions/{sid}/intake/answer", json={
            "upload_id": aid, "revision": value["autofill"]["revision"],
            "field": field, "value": answer, "other": False})
        assert response.status_code == 200
    value = intake(client, sid, aid)
    assert value["autofill"]["questions"] == []
    assert value["facts"]["cell_line"] is None
    # Omission from the question queue does not remove voluntary metadata editing.
    response = client.post(f"/api/sessions/{sid}/intake/answer", json={
        "upload_id": aid, "revision": value["autofill"]["revision"],
        "field": "cell_line", "value": "research-line-A", "other": False})
    assert response.status_code == 200
    assert intake(client, sid, aid)["facts"]["cell_line"] == "research-line-A"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["plan"] is None and not state["input_review_required"]


def test_observed_annotations_do_not_become_target_or_count_proof(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path, uns={"cell_type": "dopaminergic neuron"})
    value = intake(client, sid, aid)
    assert value["facts"].get("target_cell_type") is None
    assert value["facts"]["count_semantics"] == "unknown"
    assert value.get("autofill", {}).get("sources")


def test_model_context_keeps_identities_and_raw_values_local(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web.intake_autofill import model_context
    service = client.app.state.service
    context = model_context(service, service.load(sid), aid)
    wire = json.dumps(context)
    assert "PRIVATE_" not in wire
    assert str(tmp_path) not in wire
    assert "culture_day" in wire and "28" in wire
    assert context["purpose"] == "intake_extraction"


def test_answer_persists_and_rejects_stale_revision_without_confirming(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    payload = {"upload_id": aid, "revision": value.get("autofill", {}).get("revision", 0),
               "field": "starting_cell_type", "value": "iPSC", "other": False}
    response = client.post(f"/api/sessions/{sid}/intake/answer", json=payload)
    assert response.status_code == 200, response.json()
    assert intake(client, sid, aid)["facts"]["starting_cell_type"] == "iPSC"
    stale = client.post(f"/api/sessions/{sid}/intake/answer", json={**payload, "value": "ESC"})
    assert stale.status_code == 409
    assert intake(client, sid, aid)["facts"]["starting_cell_type"] == "iPSC"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["plan"] is None and not state["input_review_required"]


def test_other_answer_is_saved_without_becoming_a_false_enum(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    response = client.post(f"/api/sessions/{sid}/intake/answer", json={
        "upload_id": aid, "revision": value.get("autofill", {}).get("revision", 0),
        "field": "assay", "value": "spatial transcriptomics", "other": True})
    assert response.status_code == 200
    value = intake(client, sid, aid)
    assert value["facts"]["assay"] == "unknown"
    assert value["autofill"]["other_answers"]["assay"] == "spatial transcriptomics"
    assert "assay" not in [q["field"] for q in value["autofill"]["questions"]]


def test_purpose_extraction_maps_unusual_metadata_but_retains_manual_answer(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path, day_column="harvest_d")
    from bridge.web import intake_autofill as module
    captured = []
    def extracted(settings, context):
        captured.append(context)
        source = next(s for s in context["sources"] if s["label"] == "obs.harvest_d")
        return module.Extraction(fields=[module.ExtractedField(
            field="culture_day", value=28, source_ids=[source["id"]], quote="28")])
    monkeypatch.setattr(module, "extract_intake", extracted)
    response = client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    assert response.status_code == 200, response.json()
    settle(client, sid)
    value = intake(client, sid, aid)
    assert value["facts"]["culture_day"] == 28
    assert value["autofill"]["state"] == "complete"
    assert len(captured) == 1
    response = client.post(f"/api/sessions/{sid}/intake/answer", json={
        "upload_id": aid, "revision": value["autofill"]["revision"],
        "field": "culture_day", "value": 29, "other": False})
    assert response.status_code == 200
    client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    settle(client, sid)
    assert intake(client, sid, aid)["facts"]["culture_day"] == 29


def test_protocol_upload_extracts_cited_fields_without_running_tools(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    text = "Starting cells: human iPSC. Target: midbrain dopaminergic progenitors. Day 0-7: neural induction."
    def extracted(settings, context):
        source = next(s for s in context["sources"] if s["kind"] == "protocol")
        return module.Extraction(fields=[
            module.ExtractedField(field="starting_cell_type", value="iPSC", source_ids=[source["id"]], quote="human iPSC"),
            module.ExtractedField(field="target_cell_type", value="midbrain dopaminergic progenitors",
                                  source_ids=[source["id"]], quote="midbrain dopaminergic progenitors")],
            protocol_stages=[module.ProtocolStage(label="Neural induction", start_day=0, end_day=7,
                operations="neural induction", source_ids=[source["id"]], quote="Day 0-7: neural induction")])
    monkeypatch.setattr(module, "extract_intake", extracted)
    response = client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}",
                          files={"file": ("protocol.txt", text.encode(), "text/plain")})
    assert response.status_code == 200, response.json()
    state = settle(client, sid)
    value = intake(client, sid, aid)
    assert value["facts"]["starting_cell_type"] == "iPSC"
    assert value["autofill"]["protocol_stages"][0]["end_day"] == 7
    assert "protocol_name" not in [q["field"] for q in value["autofill"]["questions"]]
    assert "starting_cell_type" not in [q["field"] for q in value["autofill"]["questions"]]
    assert value["autofill"]["protocols"][0]["name"] == "protocol.txt"
    assert value["autofill"]["field_sources"]["starting_cell_type"]["source_ids"]
    assert state["plan"] is None and not state["input_review_required"]
    assert client.app.state.service.load(sid)["_tool_runs"] == []


def test_invalid_model_citation_cannot_fill_a_field(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    monkeypatch.setattr(module, "extract_intake", lambda *a: module.Extraction(fields=[
        module.ExtractedField(field="starting_cell_type", value="iPSC",
                              source_ids=["invented"], quote="iPSC")]))
    client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    settle(client, sid)
    value = intake(client, sid, aid)
    assert value["facts"]["starting_cell_type"] is None
    assert value["autofill"]["state"] == "unavailable"


def test_docx_reader_uses_paragraph_sources_and_rejects_unsafe_zip():
    from bridge.web.intake_sources import protocol_text
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Starting cells: iPSC</w:t></w:r></w:p></w:body></w:document>')
    pages = protocol_text("protocol.docx", stream.getvalue())
    assert pages[0]["location"] == "paragraph 1"
    assert pages[0]["text"] == "Starting cells: iPSC"
    with pytest.raises(ValueError):
        protocol_text("protocol.docx", b"not a zip")


def test_background_extraction_cannot_overwrite_newer_answer(client, tmp_path, monkeypatch):
    from threading import Event
    sid, aid = upload_metadata(client, tmp_path, day_column="harvest_d")
    from bridge.web import intake_autofill as module
    entered, release = Event(), Event()
    def extracted(settings, context):
        entered.set()
        assert release.wait(8)
        source = next(s for s in context["sources"] if s["label"] == "obs.harvest_d")
        return module.Extraction(fields=[module.ExtractedField(field="culture_day", value=28,
            source_ids=[source["id"]], quote="28")])
    monkeypatch.setattr(module, "extract_intake", extracted)
    client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    assert entered.wait(5)
    try:
        value = intake(client, sid, aid)
        response = client.post(f"/api/sessions/{sid}/intake/answer", json={
            "upload_id": aid, "revision": value["autofill"]["revision"],
            "field": "culture_day", "value": 30, "other": False})
        assert response.status_code == 200
    finally:
        release.set()
    settle(client, sid)
    assert intake(client, sid, aid)["facts"]["culture_day"] == 30


def test_protocol_attachment_reopens_confirmed_draft_even_without_field_changes(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": value["facts"]}).json()
    confirm_change(client, sid, staged)
    assert intake(client, sid, aid)["state"] == "confirmed"
    from bridge.web import intake_autofill as module
    monkeypatch.setattr(module, "extract_intake", lambda *args: module.Extraction())
    client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}",
                files={"file": ("protocol.txt", b"Day 0-7: neural induction.")})
    settle(client, sid)
    assert intake(client, sid, aid)["state"] == "draft"


def test_confirmed_manual_assay_does_not_overrule_a_newer_asset_declaration(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    client.post(f"/api/sessions/{sid}/intake/answer", json={"upload_id": aid,
        "revision": value["autofill"]["revision"], "field": "assay", "value": "scRNA-seq"})
    facts = intake(client, sid, aid)["facts"]
    facts["count_semantics"] = "raw_counts"
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": facts}).json()
    confirm_change(client, sid, staged)
    service = client.app.state.service
    with service.lock:
        state = service.load(sid)
        state["_asset_declarations"][aid]["assay"] = "snRNA-seq"
        service.save(state)
    assert intake(client, sid, aid)["facts"]["assay"] == "snRNA-seq"


def test_stopped_extraction_does_not_apply_a_late_result(client, tmp_path, monkeypatch):
    from threading import Event
    sid, aid = upload_metadata(client, tmp_path, day_column="harvest_d")
    from bridge.web import intake_autofill as module
    entered, release = Event(), Event()
    def extracted(settings, context):
        entered.set()
        assert release.wait(8)
        source = next(s for s in context["sources"] if s["label"] == "obs.harvest_d")
        return module.Extraction(fields=[module.ExtractedField(field="culture_day", value=28,
            source_ids=[source["id"]], quote="28")])
    monkeypatch.setattr(module, "extract_intake", extracted)
    client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    assert entered.wait(5)
    client.post(f"/api/sessions/{sid}/stop", json={})
    release.set()
    settle(client, sid)
    value = intake(client, sid, aid)
    assert value["facts"]["culture_day"] is None
    assert value["autofill"]["state"] == "unavailable"


def test_partial_or_mixed_metadata_cannot_be_mapped_to_a_global_day(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path, day_column="harvest_d", days=(21, 28), samples=("A", "B"))
    from bridge.web import intake_autofill as module
    def extracted(settings, context):
        source = next(s for s in context["sources"] if s["label"] == "obs.harvest_d")
        return module.Extraction(fields=[module.ExtractedField(field="culture_day", value=28,
            source_ids=[source["id"]], quote="28")])
    monkeypatch.setattr(module, "extract_intake", extracted)
    client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    settle(client, sid)
    value = intake(client, sid, aid)
    assert value["facts"]["culture_day"] is None
    assert value["autofill"]["state"] == "unavailable"


def test_protocol_readers_reject_active_xml_and_support_pdf_pages():
    from bridge.web.intake_sources import protocol_text
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><x>&y;</x>')
    with pytest.raises(ValueError):
        protocol_text("protocol.docx", stream.getvalue())
    # Small genuine PDF with one text stream; no parser mocking.
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    text = b"BT /F1 12 Tf 30 240 Td (Day 0-7: neural induction.) Tj ET"
    objects.append(b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream")
    pdf, offsets = b"%PDF-1.4\n", [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF"
    pages = protocol_text("protocol.pdf", pdf)
    assert pages[0]["location"] == "page 1"
    assert "Day 0-7: neural induction." in pages[0]["text"]


def test_staging_autofilled_facts_displays_exact_changes_against_committed_values(client, tmp_path):
    sid, aid = upload_metadata(client, tmp_path)
    value = intake(client, sid, aid)
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": value["facts"]}).json()
    changes = staged["pending_input_change"]["changes"]
    assert {"field": "culture_day", "before": None, "after": 28} in changes
    assert {"field": "sample_id_column", "before": None, "after": "sample_id"} in changes


def test_feature_type_cannot_prove_assay_even_with_an_exact_quote(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    def extracted(settings, context):
        source = next(s for s in context["sources"] if s["label"] == "var.feature_type")
        return module.Extraction(fields=[module.ExtractedField(field="assay", value="scRNA-seq",
            source_ids=[source["id"]], quote="Gene Expression")])
    monkeypatch.setattr(module, "extract_intake", extracted)
    client.post(f"/api/sessions/{sid}/intake/parse", json={"upload_id": aid})
    settle(client, sid)
    assert intake(client, sid, aid)["facts"]["assay"] == "unknown"


@pytest.mark.parametrize(("field", "first", "second", "question_required"), [
    ("cell_line", "H9", "iPSC line A", False),
    ("target_cell_type", "midbrain dopaminergic progenitors", "midbrain dopaminergic neurons", True),
])
def test_protocol_conflicts_only_prompt_when_consumed_by_analysis(client, tmp_path, monkeypatch,
                                                                  field, first, second, question_required):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    def extracted(settings, context):
        source = next(s for s in context["sources"] if s["kind"] == "protocol")
        return module.Extraction(fields=[
            module.ExtractedField(field=field, value=first, source_ids=[source["id"]], quote=first),
            module.ExtractedField(field=field, value=second, source_ids=[source["id"]], quote=second)])
    monkeypatch.setattr(module, "extract_intake", extracted)
    client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}",
                files={"file": ("protocol.txt", f"Experiments describe {first} and {second}.".encode())})
    settle(client, sid)
    value = intake(client, sid, aid)
    assert value["facts"][field] is None
    assert [item["field"] for item in value["autofill"]["conflicts"]] == ([field] if question_required else [])
    assert client.app.state.service.load(sid)["_intake_autofill"][aid]["conflicts"][0]["field"] == field
    assert value["autofill"]["state"] == "complete"


def test_protocol_confirmation_lists_sources_and_rechecks_attachment_integrity(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    monkeypatch.setattr(module, "extract_intake", lambda *a: module.Extraction())
    client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}",
                files={"file": ("protocol.txt", b"Day 0-7: neural induction.")})
    settle(client, sid)
    value = intake(client, sid, aid)
    staged = client.post(f"/api/sessions/{sid}/intake", json={"upload_id": aid, "facts": value["facts"]}).json()
    assert any(c["field"] == "protocol_documents" and "protocol.txt" in c["after"]
               for c in staged["pending_input_change"]["changes"])
    service = client.app.state.service
    state = service.load(sid)
    pid = state["_intake_autofill"][aid]["protocols"][0]["id"]
    from bridge.web.app import write_file
    write_file(service.directory(sid) / "intake-protocols" / (pid + ".bin"), b"Replaced text")
    pending = staged["pending_input_change"]
    response = client.post(f"/api/sessions/{sid}/input-change/confirm",
                           json={"change_id": pending["id"], "change_digest": pending["digest"]})
    assert response.status_code == 409
    assert aid not in service.load(sid).get("_intakes", {})


def test_protocol_upload_has_its_own_bounded_multipart_envelope(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    monkeypatch.setattr(module, "extract_intake", lambda *a: module.Extraction())
    text = ("Neural induction medium and culture steps. " * 1300).encode()
    assert len(text) > 32768
    response = client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}",
                           files={"file": ("protocol.txt", text)})
    assert response.status_code == 200, response.json()
    settle(client, sid)
    assert intake(client, sid, aid)["autofill"]["protocols"][0]["size"] == len(text)
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": "x" * 40000}).status_code == 413


def test_protocol_timing_does_not_promote_collection_days_to_culture_intervals(client, tmp_path, monkeypatch):
    sid, aid = upload_metadata(client, tmp_path)
    from bridge.web import intake_autofill as module
    def extracted(settings, context):
        source = next(s for s in context["sources"] if s["kind"] == "protocol")
        return module.Extraction(protocol_stages=[
            module.ProtocolStage(label="Floating culture", start_day=13, end_day=21, operations="floating culture",
                                 source_ids=[source["id"]]),
            module.ProtocolStage(label="Model-combined stage", start_day=22, end_day=28, operations="culture",
                                 source_ids=[source["id"]]),
            module.ProtocolStage(label="Maturation", start_day=37, end_day=None, operations="maturation",
                                 source_ids=[source["id"]])])
    monkeypatch.setattr(module, "extract_intake", extracted)
    client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}", files={"file": ("protocol.txt",
        b"From days 13-21, floating culture. From days 22-36, culture. Samples collected on day 28. After day 36, maturation.")})
    settle(client, sid)
    stages = intake(client, sid, aid)["autofill"]["protocol_stages"]
    assert (stages[0]["start_day"], stages[0]["end_day"]) == (13, 21)
    assert stages[1]["start_day"] is None and stages[1]["end_day"] is None
    assert stages[1]["timing_state"] == "needs_confirmation"
    assert stages[2]["start_day"] is None and stages[2]["timing_state"] == "needs_confirmation"
