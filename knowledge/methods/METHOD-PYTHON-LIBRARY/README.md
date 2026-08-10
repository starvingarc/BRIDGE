# Python library

| Field | Value |
|---|---|
| Method ID | `METHOD-PYTHON-LIBRARY` |
| Modules | P0-11 |
| Scientific status | shortlisted |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | DETERMINISTIC-LEAK-SCAN, RASTER-CHECK, SCHEMA-VALIDATION, SVG-SECURITY, TABLE-SERIALIZATION |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

public-safe export

## Inputs

typed objects | JSON object + schema | approved aggregate table | approved table | text fields | registered PNG/JPEG payload | registered SVG

## Outputs

validated model / JSON schema | validation record | CSV payload | schema record / optional Parquet intermediate | pattern match records | re-encoded image | parsed safe tree or error

## Boundaries

schema 通过不代表无敏感字段 | 与 Pydantic 同属结构证据家族 | 不得读取或导出细胞级私有表 | P0 公开包不默认包含 Parquet | 不能识别所有语义泄漏 | 重编码后仍需独立 metadata 审计 | 只限制 XML parser 攻击，不清除 script

## Environment

Evidence 与报告治理环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [Security - Pillow (PIL Fork) 12.3.0 documentation](https://pillow.readthedocs.io/en/stable/handbook/security.html) (`SOURCE-023A4A9BD0A77ABC`)
- [Client Challenge](https://pypi.org/project/regex/) (`SOURCE-043599EF7F115DB4`)
- [GitHub - mrabarnett/mrab-regex · GitHub](https://github.com/mrabarnett/mrab-regex) (`SOURCE-0A5D1C2E3E74491A`)
- [jsonschema 4.26.0 documentation](https://python-jsonschema.readthedocs.io/) (`SOURCE-176CF3DCE17C926D`)
- [GitHub - tiran/defusedxml · GitHub](https://github.com/tiran/defusedxml) (`SOURCE-257604DC54501860`)
- [pandas documentation — pandas 3.0.5 documentation](https://pandas.pydata.org/docs/) (`SOURCE-27F6DDCA9CC20B93`)
- [Python — Apache Arrow v25.0.0](https://arrow.apache.org/docs/python/) (`SOURCE-3EC417090A252FD0`)
- [GitHub - pydantic/pydantic: Data validation using Python type hints · GitHub](https://github.com/pydantic/pydantic) (`SOURCE-6249314697CB9C14`)
- [GitHub - python-jsonschema/jsonschema: An implementation of the JSON Schema specification for Python · GitHub](https://github.com/python-jsonschema/jsonschema) (`SOURCE-68B7BDA54162DBB5`)
- [GitHub - apache/arrow: Apache Arrow is the universal columnar format and multi-language toolbox for fast data interchange and in-memory analytics · GitHub](https://github.com/apache/arrow) (`SOURCE-733392686F48BD27`)
- [GitHub - python-pillow/Pillow: Python Imaging Library (fork) · GitHub](https://github.com/python-pillow/Pillow) (`SOURCE-A3DEBDA1887245AC`)
- [Welcome to Pydantic | Pydantic Docs](https://docs.pydantic.dev/latest/) (`SOURCE-DA22316C4D882854`)
- [GitHub - pandas-dev/pandas: Flexible and powerful data analysis / manipulation library for Python, providing labeled data structures similar to R data.frame objects, statistical functions, and much more · GitHub](https://github.com/pandas-dev/pandas) (`SOURCE-E2312A11B048C332`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
