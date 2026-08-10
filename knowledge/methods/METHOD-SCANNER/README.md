# scanner

| Field | Value |
|---|---|
| Method ID | `METHOD-SCANNER` |
| Modules | P0-11 |
| Scientific status | conditional |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | PII-SCAN |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

public-safe export

## Inputs

sanitized candidate text

## Outputs

PII findings

## Boundaries

需开发中文与内部 ID recognizer；第二道防线

## Environment

Evidence 与报告治理环境；工具专用隔离环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - data-privacy-stack/presidio: An open-source framework for detecting, redacting, masking, and anonymizing sensitive data (PII) across text, images, and structured data. Supports NLP, pattern matching, and customizable pipelines. · GitHub](https://github.com/microsoft/presidio) (`SOURCE-E9AC183AB92F53F5`)
- [This page has moved](https://microsoft.github.io/presidio/) (`SOURCE-EB9D20E87F69C703`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
