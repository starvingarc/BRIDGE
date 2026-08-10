# defusedxml / DOMPurify / custom rules

| Field | Value |
|---|---|
| Method ID | `METHOD-DEFUSEDXML-DOMPURIFY-CUSTOM-RULES` |
| Modules | P0-11 |
| Scientific status | candidate |
| Source status | `not_registered` |
| License status | `unresolved` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | `unassigned` |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

file and figure checks

## Inputs

SVG | safe parse + element/attribute/link/text/tooltip allowlist | SVG active content | script/event/foreignObject/external reference scan

## Outputs

MediaCheckRecord | SvgCheckRecord

## Boundaries

script; event handler; foreignObject; external href | onload; javascript URL; external image

## Environment

Evidence 与报告治理环境；Web 渲染与发布验证环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- No public source registered; see `source_status`.

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
