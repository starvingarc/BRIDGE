"""M1 HTTP registration; persistence and transitions belong to the object store."""
from fastapi import HTTPException, Request

from .presentation import public_error
from .model_settings import ModelSelectionError

from .research_object_models import (
    Decision, LeadPatch, Mutation, MappingStart, ProtocolCreate, ProtocolPatch,
    RunCreate, RunPatch, SampleCreate, SamplePatch, SourceReview, VersionCreate,
)


# Only these fixed, non-sensitive codes may cross the existing public-error
# boundary. Arbitrary internal exceptions still receive the generic envelope.
OBJECT_ERROR_MESSAGES = {
    "research_material_unavailable": public_error("research_material_unavailable", results_state="unknown").user_message,
    "research_not_found": "找不到该研究，或你没有访问权限。",
    "protocol_not_found": "找不到该方案。",
    "protocol_version_not_found": "找不到该方案版本。",
    "run_not_found": "找不到该轮分化。",
    "conversation_not_found": "尚未创建该研究或轮次的对话。",
    "conversation_binding_ambiguous": "该范围存在重复的会话绑定，请联系维护者核对。",
    "sample_not_found": "找不到该样本。",
    "assessment_not_found": "尚无该评估结果。",
    "action_not_found": "找不到该待确认项。",
    "lead_not_found": "找不到该线索。",
    "material_not_found": "找不到该研究资料。",
    "object_version_conflict": "内容已更新，请刷新后重新核对。",
    "protocol_version_immutable": "已确认或来源已核对的方案不能修改，请创建新版本。",
    "protocol_source_required": "请提供文献引用或来源文档，再记录来源核对。",
    "protocol_source_not_reviewed": "请先核对来源，再登记回顾性轮次。",
    "protocol_provenance_stale": "字段值已修改，请更新或清除该字段的旧出处。",
    "protocol_incomplete": "请补齐方案总天数、试剂剂量、时间窗口和操作日期。",
    "protocol_unconfirmed_fields": "请先核对所有标为待确认的方案字段。",
    "protocol_version_not_confirmed": "请先确认方案版本，再开始一轮分化。",
    "protocol_material_required": "请选择该研究中的方案文档。",
    "protocol_source_invalid": "方案原文不可读取、完整性已改变或超出提取范围，请核对资料。",
    "protocol_import_invalid": "方案生成未通过编译或来源检查，请核对原文并重试。",
    "protocol_provider_unavailable": "模型服务暂不可用，请检查所选模型后重试。",
    "protocol_compiler_unavailable": "方案编译检查暂不可用，请联系维护者。",
    "protocol_formalization_not_found": "该版本没有文档形式化来源。",
    "protocol_formalization_limit": "方案来源记录过大，请按独立方案拆分文档后重试。",
    "protocol_formalization_unavailable": "方案来源记录无法通过完整性检查，请联系维护者。",
    "invalid_protocol_content": "请检查方案天数、阶段和试剂窗口。",
    "reagent_catalog_unavailable": "小分子库暂不可用，请保留试剂文字记录。",
    "reagent_catalog_id_unknown": "该试剂未匹配到小分子库，请核对来源。",
    "sample_material_requires_h5ad": "请选择该研究中的 H5AD 数据文件。",
    "sample_has_material": "该样本已关联数据，不能重复关联或替换。",
    "assessment_request_active": "该样本已有待确认或已批准的评估请求。",
    "action_not_pending": "该请求已处理，请刷新查看。",
    "lead_not_open": "该线索已处理，请刷新查看。",
    "object_store_unavailable": "研究对象暂不可读取，请联系维护者检查。",
    "sample_matrix_location_unavailable": "该文件中没有所选矩阵，请核对可用的原始计数位置。",
    "sample_declaration_conflict": "捕获批次的两种声明方式冲突，请核对后选择一种。",
    "mapping_input_immutable": "已声明的映射输入不能改写，请登记新样本。",
    "mapping_material_required": "请先关联样本数据。",
    "mapping_already_started": "该样本已有运行中或完成的映射。",
    "marker_expression_unavailable": "该评估尚无基因表达着色数据。",
    "mapping_result_unavailable": "映射结果无法通过完整性检查，请联系维护者。",
    "research_object_limit": "该研究的对象存储已达到上限。",
}


def install_research_object_http(app, store, model_configuration, atlas_mapping):
    prefix = "/api/researches/{rid}"

    @app.get(prefix + "/workbench")
    def workbench(rid: str, request: Request):
        return store.workbench(request.state.principal.id, rid)

    @app.post(prefix + "/protocols")
    def create_protocol(rid: str, body: ProtocolCreate, request: Request):
        owner = request.state.principal.id
        settings = None
        if body.material_id:
            try:
                with model_configuration.lock:
                    selection = model_configuration.recent_selection(owner)
                    settings = model_configuration.snapshot_for(owner, selection)
            except ModelSelectionError as error:
                raise HTTPException(409, error.code) from None
        return store.create_protocol(owner, rid, body, settings=settings)

    @app.get(prefix + "/protocols/{pid}")
    def protocol(rid: str, pid: str, request: Request):
        return store.protocol(request.state.principal.id, rid, pid)

    @app.get(prefix + "/protocols/{pid}/versions/{vid}/formalization")
    def formalization(rid: str, pid: str, vid: str, request: Request):
        return store.formalization(request.state.principal.id, rid, pid, vid)

    @app.post(prefix + "/protocols/{pid}/versions")
    def create_version(rid: str, pid: str, body: VersionCreate, request: Request):
        return store.create_version(request.state.principal.id, rid, pid, body)

    @app.patch(prefix + "/protocols/{pid}/versions/{vid}")
    def edit_version(rid: str, pid: str, vid: str, body: ProtocolPatch, request: Request):
        return store.edit_version(request.state.principal.id, rid, pid, vid, body)

    @app.post(prefix + "/protocols/{pid}/versions/{vid}/confirm")
    def confirm_version(rid: str, pid: str, vid: str, body: Mutation, request: Request):
        return store.edit_version(request.state.principal.id, rid, pid, vid, body, confirm=True)

    @app.post(prefix + "/protocols/{pid}/versions/{vid}/source-review")
    def review_source(rid: str, pid: str, vid: str, body: SourceReview, request: Request):
        return store.review_source(request.state.principal.id, rid, pid, vid, body)

    @app.post(prefix + "/runs")
    def create_run(rid: str, body: RunCreate, request: Request):
        return store.create_run(request.state.principal.id, rid, body)

    @app.patch(prefix + "/runs/{oid}")
    def edit_run(rid: str, oid: str, body: RunPatch, request: Request):
        return store.edit_run(request.state.principal.id, rid, oid, body)

    @app.post(prefix + "/runs/{oid}/samples")
    def create_sample(rid: str, oid: str, body: SampleCreate, request: Request):
        owner = request.state.principal.id
        sample = store.create_sample(owner, rid, oid, body)
        return atlas_mapping.schedule(owner, rid, sample["id"])

    @app.patch(prefix + "/samples/{oid}")
    def attach_sample(rid: str, oid: str, body: SamplePatch, request: Request):
        owner = request.state.principal.id
        sample = store.attach_sample(owner, rid, oid, body)
        return atlas_mapping.schedule(owner, rid, sample["id"])

    @app.post(prefix + "/samples/{oid}/mapping")
    def retry_mapping(rid: str, oid: str, body: MappingStart, request: Request):
        owner = request.state.principal.id
        store.declare_mapping(owner, rid, oid, body)
        return atlas_mapping.schedule(owner, rid, oid, explicit=True)

    @app.post(prefix + "/samples/{oid}/workflow")
    def continue_workflow(rid: str, oid: str, body: MappingStart, request: Request):
        owner = request.state.principal.id
        changed = store.supplement_sample_input(owner, rid, oid, body)
        return atlas_mapping.schedule(owner, rid, oid, allow_completed=changed)

    @app.post(prefix + "/samples/{oid}/assessments")
    def propose_assessment(rid: str, oid: str, body: Mutation, request: Request):
        return store.propose_assessment(request.state.principal.id, rid, oid, body)

    @app.get(prefix + "/assessments/{oid}")
    def assessment(rid: str, oid: str, request: Request):
        return store.assessment(request.state.principal.id, rid, oid)

    @app.get(prefix + "/assessments/{oid}/marker-expression")
    def marker_expression(rid: str, oid: str, request: Request):
        return store.marker_expression(request.state.principal.id, rid, oid)

    @app.post(prefix + "/actions/{oid}/approve")
    def approve(rid: str, oid: str, body: Decision, request: Request):
        return store.decide(request.state.principal.id, rid, oid, body, approve=True)

    @app.post(prefix + "/actions/{oid}/decline")
    def decline(rid: str, oid: str, body: Decision, request: Request):
        return store.decide(request.state.principal.id, rid, oid, body, approve=False)

    @app.patch(prefix + "/leads/{oid}")
    def edit_lead(rid: str, oid: str, body: LeadPatch, request: Request):
        return store.edit_lead(request.state.principal.id, rid, oid, body)
