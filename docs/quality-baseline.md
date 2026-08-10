# Quality Baseline

## Engineering Gates

- Schema validation and round-trip serialization.
- Exactly 12 discoverable Tool Packages with stable IDs.
- Deterministic eligibility, reason codes and content hashes.
- Original-input checksum remains unchanged.
- CLI and Python SDK return equivalent structured results.
- Knowledge aliases and source references resolve without dangling IDs.
- Public files contain no private paths, usernames or credentials.

## Scientific Gates

Installation is not scientific validation. Method promotion requires validation appropriate to its claim, including source/lab/modality holdout, OOD and abstention behavior, downsampling, reference/preprocessing sensitivity, evidence-family deduplication and biological review.

P0-01 additionally checks matrix semantics, sample/capture hierarchy, declared gene-identifier coverage, scRNA/snRNA separation, per-capture metrics, missing-input degradation and candidate MeasurementSpec behavior. An absent QC gene set must become `unavailable`, not a zero fraction.

## Visualization Gates

Every registered chart binds its source artifact, denominator, units, uncertainty and missing state. Static SVG/PNG rendering and chart payload must agree. Exploratory plots cannot enter a verified report.

## Completion Evidence

Completion claims require a fresh full test run, CLI smoke, knowledge validation, privacy scan, `git diff --check`, and documented server integration results. Unavailable external services or datasets remain explicitly unverified.
