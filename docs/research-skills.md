# Research workflow Skills

BRIDGE separates workflow instructions from scientific execution. A Skill helps
the model choose the next step; registered Tool Packages own input eligibility,
measurements, denominators and evidence. Skills do not add execution authority.

## Available workflows

| Workflow | Questions | Maintained instructions |
|---|---|---|
| Case understanding | Experimental question, supplied facts, preparation/capture relationships and consequential clarification | [SKILL](../src/bridge/skills/case-understanding/SKILL.md) · [examples](../src/bridge/skills/case-understanding/EXAMPLES.md) |
| Expression exploration | Input QC, expression profiles, clusters, markers and cell-type differential expression | [SKILL](../src/bridge/skills/expression-exploration/SKILL.md) · [examples](../src/bridge/skills/expression-exploration/EXAMPLES.md) |
| Reference and target definition | Reference applicability, product roles, regional denominators and developmental windows | [SKILL](../src/bridge/skills/reference-and-target-definition/SKILL.md) · [examples](../src/bridge/skills/reference-and-target-definition/EXAMPLES.md) |
| Product assessment | Identity, regional fit, development, composition and proliferation/stress | [SKILL](../src/bridge/skills/product-assessment/SKILL.md) · [examples](../src/bridge/skills/product-assessment/EXAMPLES.md) |
| Evidence reasoning | Conflicting evidence, competing hypotheses and discriminating checks | [SKILL](../src/bridge/skills/evidence-reasoning/SKILL.md) · [examples](../src/bridge/skills/evidence-reasoning/EXAMPLES.md) |
| Research reporting | Current evidence, interpretation, report handoff and verifier conditions | [SKILL](../src/bridge/skills/research-reporting/SKILL.md) · [examples](../src/bridge/skills/research-reporting/EXAMPLES.md) |
| Product comparison | Comparability, independent preparations, confounding and descriptive stability | [SKILL](../src/bridge/skills/product-comparison/SKILL.md) · [examples](../src/bridge/skills/product-comparison/EXAMPLES.md) |
| Graft follow-up | Independent post-transplant observations and declared preparation/graft links | [SKILL](../src/bridge/skills/graft-followup/SKILL.md) · [examples](../src/bridge/skills/graft-followup/EXAMPLES.md) |

The catalog is generated from packaged `SKILL.md` frontmatter. Each workflow has
one maintained name and description, an immutable body within a running process,
and a SHA-256 content fingerprint. `EXAMPLES.md` documents acceptance cases and is
not injected into every model request. Existing comparison, graft and other scientific
contracts remain unchanged; instructions do not add missing scientific capabilities.

## Product scope

The eight workflows organize research tasks; they are not eight assessment domains.
Product assessment contains five domains: target identity, regional fidelity,
developmental compatibility, whole-product/off-target composition, and proliferation
and stress response. QC and cell-state evidence are their shared foundation. Product
comparison and graft follow-up have separate questions and contracts; graft evidence
remains independent of pre-transplant assessment. See the maintained
[five-domain methods](tool-packages.md#五域方法逐项说明).

## Invocation and boundaries

Ordinary conversation begins with a small routing prompt and the catalog. The
model can call `load_skill(name)` for one of the registered names. The provider
reads package-owned text and sends it with the existing action contracts in the
next request. Native calls receive a matching tool result; JSON mode receives
the workflow in its next system prompt. Only the selected body is supplied. This is a bounded
internal read, not a public Action or a scientific tool.

Before a Skill is loaded, only a read, an ordinary reply or input-review request
is admitted. Analysis preparation and other structured actions require the loaded
stage. A greeting, explicit stop, input correction or unmatched non-research
request can finish in one model request. A matching workflow uses at most two;
another read, invalid name or path is rejected. Model mistakes in choosing the
workflow remain possible and require behavioral evaluation, not only file tests.

An approved assessment already has a server-owned scope and loads exactly one
workflow for its current phase, without another model request. A report-ready
handoff selects research-reporting; otherwise graph preparation or available
options select product-assessment; with neither, it selects evidence-reasoning.
Authorized comparison or graft options do not add more workflows to that request;
their separate scientific contracts and authorization still apply. Ordinary
conversation can still select product-comparison or graft-followup by topic.
Scientific-input drafts load only reference-and-target-definition under their separate
purpose-limited contract. Scope loading is recorded distinctly from a model-selected read.
Each ordinary turn chooses its immediate task afresh; there is no recursive workflow loop.

Both JSON envelopes and the configured native function-call protocol use the same
loader and final Action validation. Native requests with multiple calls or prose
outside the call are rejected. Skill reads cannot run arbitrary files, add tools,
approve a plan, redefine input facts or bypass Registry eligibility. Existing
source-bound result admission, unavailable/unknown states and scientific limits
remain enforced outside workflow text.

## Provenance and packaging

After a valid final model Action, the private session stores `_skill_invocations`:
Skill name and content hash, model/scope selection, final action, purpose, provider
request count, timestamp and the current private message/input/assessment binding.
The public session projection excludes these records. Prompt text, credentials and
raw model output are not stored in this trace. A transport/parse failure before a
valid Action uses existing failure diagnostics and has no successful Skill receipt.

The loader uses `importlib.resources`; wheel package data includes Skill and example
files, source attribution, pinned hashes and license texts. Validate the installed wheel as well as the source checkout. Updating a
workflow changes its hash and requires a process restart, as for provider code.
Existing historical receipts preserve their original hashes.

## Testing

`tests/test_research_skills.py` exercises the real provider adapter with an HTTP
test transport, including deferred loading, malformed reads, loop limits,
assessment scope, private provenance and plan approval. Existing Web regressions
cover input eligibility, source binding, missingness, report and graft boundaries.

For live acceptance, configure `BRIDGE_WEB_MODEL_BASE_URL`, `BRIDGE_WEB_MODEL` and
`BRIDGE_WEB_MODEL_API_KEY` in the caller's private environment, then run:

```bash
PYTHONPATH=src python scripts/check_research_skills_model.py --live \
  --protocol json --output /tmp/bridge-skill-check/results.json --with-tool-flow
```

The opt-in command sends fixed synthetic questions through the actual model adapter.
Its tool flow creates isolated synthetic data and explicitly approves a QC plan,
then checks the registered result. It never connects to existing sessions. The
output path must be outside the checkout; a summary and parsed-action review file
are written privately. Keep those files out of Git. Use `--protocol deepseek_tools`
only with a compatible configured provider; `--case` selects a bounded subset and
`--repetitions` runs fresh requests while retaining every failure. Ordinary responses
have a 3,000-token output cap and scoped decisions normally 6,000. Recognized
DeepSeek assessment models use a bounded 32,768-token output allowance including
reasoning; this is separate from the request context budget. Length truncation
remains an explicit error, with no silent retry or permission expansion.

The minimal phase fixtures in `tests/test_research_skills.py` keep the system
message below 16,000 characters, including the JSON action schema when applicable.
This regression budget is neither a token limit nor a universal cap on evidence-rich
requests. JSON assessment prompts omit item definitions for arrays already restricted
to `maxItems: 0`; the restriction remains, and usable item definitions return when
current evidence permits them. Native tool schemas and stored Action contracts are
unchanged. Current wire hypotheses require explicit `feature_queries` (possibly `[]`);
historical saved hypotheses retain their missing-field compatibility.

The same test module runs the four scoped model-evaluation cases through the real
provider and evaluator with an offline HTTP transport. Correct phase selection
passes and deliberately incorrect selection fails. These checks do not contact a
model and do not replace opt-in live acceptance.

Case checks cover routing and Action structure, not the truth of free-form scientific
interpretation. Review the private parsed actions separately. Synthetic execution,
transport tests and successful model calls do not establish scientific qualification.

Known acceptance limits: synthetic routing and Action checks do not validate free-text
experimental-design advice. In particular, preparation independence must come from
the declared design, not the count of captures, wells or cells. A single capture can
pool several preparations; separate wells or aliquots can remain dependent. Native
protocol support must be checked for the configured provider; malformed calls and
transport timeouts remain explicit failures. Detailed engineering runs belong in PR
validation records, separate from scientific qualification.

## Public reuse and code integration

The workflows adapt public ToolUniverse and K-Dense scientific-agent-skills guidance.
[Packaged attribution](../src/bridge/skills/SOURCES.md) explains the changes and retained
licenses; [the source manifest](../src/bridge/skills/sources.json) pins each upstream
file and maps all eight workflows to reused BRIDGE modules and excluded behavior.
Neither upstream repository is a runtime dependency.

Reusable public material supplies question framing, experimental units, reference
applicability, competing explanations and report organization. Existing BRIDGE
intake/scientific-input controls, Registry eligibility, typed hypotheses/citations,
comparison/graft contracts and report verification supply executable behavior.
Examined public validation scripts use incompatible standalone schemas, so the
integration reuses BRIDGE validators instead of introducing duplicate authority.

Live acceptance measures routing and Action structure separately from interpretation.
Successful selection does not prove that every free-text sentence respects scientific
or presentation boundaries. Parsed-answer review and real-data/scientific acceptance
remain necessary for broader claims; native-format compatibility is provider-specific.
