---
name: case-understanding
description: Use when a researcher needs to clarify an experimental question, supplied protocol or sample context, preparation/capture relationships, independent replication, or consequential missing facts before choosing analysis. 实验背景理解、分析设计与必要追问；不用于直接解释已计算的表达或产品结果。
---

# Case understanding

## Scope and inputs

Turn the researcher's question and supplied facts into a reviewable case. Read the
current intake, research context, source-bound protocol observations and unresolved
fields. Product intent, protocol version, preparation, capture and analysis version
are distinct. A protocol describes a planned process, not proof of its execution.

## Decisions

1. Identify the question, product/batch, sampling time and intended research use from
   the current context; do not restate confirmed background in every reply. For
   comparisons, identify the outcome, comparison and unit before discussing methods.
2. Separate supplied facts, tool observations, absent facts, unparseable statements
   and conflicting sources. Preserve each fact's provenance; an unknown relationship
   stays unknown. A filename, cell count or number of files does not establish it.
3. Identify the experimental unit and nesting: preparation, biological sample,
   technical capture and cells. Several captures from one culture do not create
   independent biological repeats. Different wells, aliquots, captures or samples
   alone do not establish independence; ask what was independently prepared and
   where the intervention was assigned. A pooled capture can include multiple
   preparations. A culture batch may include several cultures; do not equate a batch
   with one culture or label captures technical repeats without their source relation.
   Never assert a replicate count from filenames or sequencing count.
   In a design explanation, separate supplied facts from conditional examples;
   do not claim that an unknown design supports statistical inference.
   Ask about allocation, pairing or batch confounding
   only when it changes the proposed analysis or interpretation.
4. Reuse already confirmed facts. Ask the smallest consequential question using the
   existing input/clarification controls; offer an explicit unknown answer. If the
   researcher only requests an explanation, return a brief `reply` with that gap.
5. For a requested draft of unconfirmed input, `propose_intake` uses only user-stated
   facts and the supplied upload ID. For a correction to committed facts, use
   `review_inputs`; explain that affected results need a separately confirmed update.

## Handoff, stopping and output

For an explanation-only question with unknown replication, answer the specific question
briefly and state the unresolved preparation/allocation relationship only where it limits
the conclusion. Use conditional examples when requested; do not guess a replicate count
or repeat a generic checklist of sufficient conditions for biological independence.

Summarize the case only when establishing it or when the researcher asks for a recap.
For follow-ups, add the requested explanation without repeating known background or the
previous conclusion. Mention the next confirmation control only when needed to proceed.
Use biological names in prose, not internal IDs.
Fact confirmation and analysis approval remain separate. Once facts are reviewed,
requested QC/expression preparation uses the expression workflow; product target and
reference choices use the source-bound scientific-input flow. The next turn receives
current server state; do not invent a handoff Action or store case facts in this Skill.

If an essential relationship cannot be established, state which conclusion is limited
and whether descriptive exploration remains possible. Do not repeatedly ask a known
unknown or promise that extra cells repair missing independent replication.

Adapted workflow and license attribution: [sources](../SOURCES.md).
