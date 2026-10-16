"""A new authorization can carry an exact unresolved draft, never its approval."""
import copy
import pytest
from web_support import client
from test_web_scientific_inputs import science_case
from test_web_assessment import propose_scope
from bridge.web.scientific_inputs import digest


def setup_pending(client, tmp_path):
    service, sid, aid = science_case(client, tmp_path)
    summary = propose_scope(client, sid, aid, 'P0-01', None)
    state = service.load(sid)
    old = state['_assessment']
    old.update(status='blocked', stop_reason='provider_text_unverified', model_turns_used=3,
        authorization={'scope_id': summary['scope_id'], 'scope_sha256': summary['scope_digest']},
        pending_revision={'hypotheses': [], 'issues': [{'code': 'unknown_as_absent'}]})
    service.sessions.save(state)
    body = {key: old['scope'][key] for key in ('question','upload_id','allowed_modes','max_tool_runs','max_model_turns')}
    body['max_model_turns'] = 6
    body['continuation'] = {'scope_id': summary['scope_id'], 'scope_digest': summary['scope_digest'],
        'pending_revision_sha256': digest(old['pending_revision'])}
    return service, sid, copy.deepcopy(old), body


def test_exact_pending_draft_requires_fresh_approval_and_retains_history(client, tmp_path, monkeypatch):
    service, sid, old, body = setup_pending(client, tmp_path)
    scheduled = []
    monkeypatch.setattr(service.assessment, '_schedule', lambda state: scheduled.append(True))
    response = client.post(f'/api/sessions/{sid}/assessment/propose', json=body)
    assert response.status_code == 200, response.json()
    current = service.load(sid)
    new = current['_assessment']
    assert current['_assessment_history'][-1] == old
    assert new['pending_revision'] == old['pending_revision']
    assert new['scope']['continuation'] == body['continuation']
    assert new['authorization'] is None and new['model_turns_used'] == 0
    assert not scheduled and not new.get('interpretation_versions')
    summary = response.json()['assessment']
    assert summary['continuation'] == body['continuation']
    approved = client.post(f'/api/sessions/{sid}/assessment/approve', json={
        key: summary[key] for key in ('scope_id','scope_digest')})
    assert approved.status_code == 200, approved.json()
    assert scheduled == [True]


@pytest.mark.parametrize('change', ['identity','draft','question','input','accepted','no_issues'])
def test_changed_or_unavailable_source_does_not_replace_current_scope(client, tmp_path, change):
    service, sid, old, body = setup_pending(client, tmp_path)
    if change == 'identity': body['continuation']['scope_digest'] = '0' * 64
    if change == 'draft': body['continuation']['pending_revision_sha256'] = '0' * 64
    if change == 'question': body['question'] = 'A different research question'
    state = service.load(sid)
    if change == 'input': state['_input_revision'] += 1
    if change == 'accepted': state['_assessment']['interpretation_versions'] = [{'version': 1}]
    if change == 'no_issues': state['_assessment']['pending_revision']['issues'] = []
    service.sessions.save(state)
    before = copy.deepcopy(service.load(sid)['_assessment'])
    response = client.post(f'/api/sessions/{sid}/assessment/propose', json=body)
    assert response.status_code == 409, response.json()
    assert service.load(sid)['_assessment'] == before


def test_draft_mutation_after_proposal_cannot_be_approved(client, tmp_path):
    service, sid, old, body = setup_pending(client, tmp_path)
    response = client.post(f'/api/sessions/{sid}/assessment/propose', json=body)
    assert response.status_code == 200
    summary = response.json()['assessment']
    state = service.load(sid)
    state['_assessment']['pending_revision']['issues'] = []
    service.sessions.save(state)
    response = client.post(f'/api/sessions/{sid}/assessment/approve', json={
        key: summary[key] for key in ('scope_id','scope_digest')})
    assert response.status_code == 409
    assert service.load(sid)['_assessment']['authorization'] is None


def test_insufficient_repair_budget_offers_exact_continuation_without_spending(client, tmp_path):
    service, sid, old, body = setup_pending(client, tmp_path)
    state = service.load(sid)
    state['_assessment']['scope']['max_model_turns'] = 4
    state['_assessment']['scope_digest'] = digest(state['_assessment']['scope'])
    service.sessions.save(state)
    before = copy.deepcopy(state['_assessment'])
    assert service.assessment.resume_eligibility(state) == (False, 'interpretation_revision_budget_insufficient')
    public = client.get(f'/api/sessions/{sid}').json()['assessment']
    proposal = public['continuation_proposal']
    assert proposal['question'] == before['scope']['question']
    assert proposal['continuation']['pending_revision_sha256'] == digest(before['pending_revision'])
    assert proposal['max_model_turns'] >= 2
    assert 'hypotheses' not in proposal and 'issues' not in proposal
    assert service.load(sid)['_assessment'] == before
    response = client.post(f'/api/sessions/{sid}/assessment/propose', json=proposal)
    assert response.status_code == 200, response.json()
    new = service.load(sid)['_assessment']
    assert new['pending_revision'] == before['pending_revision']
    assert new['authorization'] is None and new['model_turns_used'] == 0


@pytest.mark.parametrize('change', ['enough_budget', 'input_change', 'no_issues', 'running'])
def test_continuation_offer_is_absent_without_current_stopped_repair_need(client, tmp_path, change):
    service, sid, old, body = setup_pending(client, tmp_path)
    state = service.load(sid)
    a = state['_assessment']
    a['scope']['max_model_turns'] = 4
    a['scope_digest'] = digest(a['scope'])
    if change == 'enough_budget': a['model_turns_used'] = 1
    if change == 'input_change': state['_input_revision'] += 1
    if change == 'no_issues': a['pending_revision']['issues'] = []
    if change == 'running': a['status'] = 'running'
    assert service.assessment.continuation_proposal(state) is None


def test_continuation_pins_original_roots_instead_of_discovering_later_outputs(client, tmp_path, monkeypatch):
    service, sid, old, body = setup_pending(client, tmp_path)
    monkeypatch.setattr(service.inputs, 'assessment_resource_ids',
        lambda state, upload_id, modes: [*old['scope']['binding']['resources'], 'new-unrelated-output'])
    response = client.post(f'/api/sessions/{sid}/assessment/propose', json=body)
    assert response.status_code == 200, response.json()
    assert service.load(sid)['_assessment']['scope']['binding'] == old['scope']['binding']


def test_continuation_reuses_verified_admitted_receipts_as_pinned_evidence(client, tmp_path, monkeypatch):
    from test_web_assessment import approve_scope, settle_assessment
    from bridge.web.provider import Action
    from bridge.web.assessment import AssessmentScope
    from bridge.web.evidence import assessment_evidence
    service, sid, aid = science_case(client, tmp_path)
    scope = propose_scope(client, sid, aid, 'P0-01', None)
    calls = []
    def decide(settings, messages, context):
        calls.append(True)
        decision = ({'action': 'check', 'option_id': context['options'][0]['id']}
            if len(calls) == 1 else {'action': 'stop', 'reason': 'no_discriminating_check'})
        return Action.model_validate({'action': 'assessment', 'decision': decision})
    monkeypatch.setattr('bridge.web.provider.converse', decide)
    approve_scope(client, sid, scope)
    settle_assessment(client, sid)
    state = service.load(sid)
    old = state['_assessment']
    assert old['admissions'] and state['_tool_runs']
    old.update(status='blocked', pending_revision={'hypotheses': [], 'issues': [{'code': 'unknown_as_absent'}]})
    old['model_turns_used'] = old['scope']['max_model_turns'] - 1
    service.sessions.save(state)
    before_evidence, _ = assessment_evidence(service.inputs, state, old)
    roots = service.inputs.assessment_pool(state, AssessmentScope.model_validate(old['scope']))
    proposal = service.assessment.continuation_proposal(state)
    response = client.post(f'/api/sessions/{sid}/assessment/propose', json=proposal)
    assert response.status_code == 200, response.json()
    current = service.load(sid)
    new = current['_assessment']
    after_evidence, _ = assessment_evidence(service.inputs, current, new)
    assert new['scope']['binding']['resources'] == roots
    assert [row['alias'] for row in after_evidence] == [row['alias'] for row in before_evidence]
    assert current['_tool_runs'] == state['_tool_runs']
    assert new['admissions'] == [] and new['tool_runs_used'] == 0
    assert service.assessment.check(current) is None
