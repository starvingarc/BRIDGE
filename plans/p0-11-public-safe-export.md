# P0-11 Allowlist-first Public JSON Projection

## Goal

Make P0-11 callable without turning it into a general publishing, file-cleaning
or anonymization framework. All selected claims, public aliases, allowed claim
types/evidence states and prohibited literals remain checksummed policy input.

## Interface

The first executable slice accepts one ReportDraft, one eligible
ClaimVerificationResult and one PublicExportSpec. It creates one new
PublicSafeReport JSON candidate and never mutates or copies the source report.

The output omits source report/claim/ProductCase/Evidence/binding identifiers,
retains only selected claim semantics and numeric bindings, and requires later
human confirmation. P0-10 warnings become `review_required` rather than being
silently dropped.

## Explicit non-goals

- no automatic publication or confirmation authority;
- no CSV, Markdown, archive, figure, SVG/HTML or media handling;
- no universal credential, PII or semantic leak detector;
- no translation or free rewriting of verified claim text;
- no biological verification, score, rank or release decision.

## Deliverables

- module-local models, executor and adapter;
- public/packaged PublicExportSpec and PublicSafeReport Schemas;
- synthetic request, detailed Tool Card and validation record;
- focused source and installed-wheel tests;
- one P0-11-only stacked Draft PR based on the P0-07 branch.

## Verification and stop

All execution occurs in GitHub Actions. The PR remains Draft after engineering
gates. Real disclosure policies and public aliases require independent human
approval and can change without code changes.
