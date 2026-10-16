"""Saved fine states retain unknown mass and require explicit reviewed roles."""
import pytest
from bridge.tool_packages.p0_03_target_regional.saved_roles import account_roles

def row(key, state, count, level="L2"):
    return dict(record_id=key,state_id=state,count=count,level=level,record_kind="state")

def test_partial_roles_keep_full_denominator_and_null_purity():
    rows=[row("a","state:a",6),row("b","state:b",3),row("unknown",None,1)]
    result=account_roles(rows,10,{"state:a":"evaluate","state:b":"parent_only"},
        {"state:a":dict(product_role="target",source_refs=["source:a"]),
         "state:b":dict(product_role="target",source_refs=["source:b"])},True)
    assert result["role_counts"]==dict(target=6,acceptable_adjacent=0,known_off_target=0,role_unresolved=4)
    assert result["target_fraction"] is None
    assert result["role_records"][1]["reason_code"]=="source_definition_parent_only"
    assert result["role_records"][2]["reason_code"]=="state_identity_unresolved"

def test_reviewed_explicit_mapping_computes_only_closed_partition():
    rows=[row("a","state:a",6),row("b","state:b",4,"L1")]
    result=account_roles(rows,10,{"state:a":"evaluate","state:b":"evaluate"},
        {"state:a":dict(product_role="target",source_refs=["source:a"]),
         "state:b":dict(product_role="acceptable_adjacent",source_refs=["source:b"])},True)
    assert result["target_fraction"]==.6
    assert result["role_judgement_state"]=="complete"
    draft=account_roles(rows,10,{}, {},False)
    assert draft["role_counts"]["role_unresolved"]==10
    assert draft["target_fraction"] is None

def test_absent_child_mapping_does_not_inherit_parent_role():
    result=account_roles([row("a","state:child",10)],10,{"state:child":"evaluate"},
        {"state:parent":dict(product_role="target",source_refs=["source:parent"])},True)
    assert result["role_records"][0]["reason_code"]=="state_role_missing"
    assert result["target_fraction"] is None

@pytest.mark.parametrize("count,n",[(9,10),(11,10)])
def test_partition_must_close(count,n):
    with pytest.raises(ValueError,match="whole_product_counts_not_conserved"):
        account_roles([row("a","state:a",count)],n,{}, {},False)

def test_saved_role_pair_checks_exact_definition_binding_and_checksum(tmp_path):
    import hashlib, json
    from types import SimpleNamespace
    from bridge.tool_packages._saved_cell_state_context import _role_context as role_context
    from bridge.tool_packages._configurable_contracts import StateRoleMap,ProductDefinitionCard
    from bridge.toolkit.contracts import StructuredInputRef
    definition_ref=dict(object_id="product-definition:synthetic",object_version="1")
    map_ref=dict(object_id="state-role-map:synthetic",object_version="1")
    provenance=[dict(object_id="source:review",object_version="1")]
    role_map=StateRoleMap(object_version="0.1.0",state_role_map_id=map_ref["object_id"],map_version="1",
        product_definition_ref=definition_ref,review_state="reviewed",provenance_refs=provenance,
        assignments=[dict(state_id="state:a",product_role="target",role_evidence_class="reviewed",
            evidence_direction="support",source_refs=["source:review"])])
    definition=ProductDefinitionCard(object_version="0.1.0",product_definition_id=definition_ref["object_id"],
        definition_version="1",state_role_map_ref=map_ref,review_state="draft",
        supported_assays=["scRNA-seq"],provenance_refs=provenance)
    refs=[]
    for role,model in [("state_role_map",role_map),("product_definition_card",definition)]:
        path=tmp_path/(role+".json");path.write_text(model.model_dump_json())
        refs.append(StructuredInputRef(input_id=role,role=role,path=path,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            media_type="application/json",schema_ref="bridge://schemas/"+role.replace("_","-")+"/v0.1",object_version="0.1.0"))
    request=SimpleNamespace(object_inputs=refs)
    original=SimpleNamespace(request=SimpleNamespace(assets=[SimpleNamespace(assay="scRNA-seq")]))
    source_row=SimpleNamespace(model_dump=lambda **kw:row("a","state:a",10))
    hierarchy=SimpleNamespace(whole_product_denominator=10,whole_product_records=[source_row])
    fields=role_context(request,original,hierarchy,[dict(state_id="state:a",definition_decision="evaluate")],[])
    assert fields["target_fraction"]==1
    assert fields["state_role_map_ref"]=="state-role-map:synthetic@1"
    value=json.loads(refs[1].path.read_text());value["state_role_map_ref"]["object_version"]="2"
    refs[1].path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match="saved_cell_state_checksum_mismatch"):
        role_context(request,original,hierarchy,[],[])
    refs[1]=refs[1].model_copy(update={"sha256":hashlib.sha256(refs[1].path.read_bytes()).hexdigest()})
    with pytest.raises(ValueError,match="saved_role_definition_binding_mismatch"):
        role_context(request,original,hierarchy,[],[])
