# Reference-and-target-definition acceptance examples

| Request/context | Expected behavior | Unacceptable behavior |
|---|---|---|
| Researcher requests target/window candidates | Explain applicable sources or invoke existing source-bound draft | Ask for internal IDs or confirm a window automatically |
| Developmental source lacks the desired state | Keep its window unresolved and identify the missing coverage | Infer maturity from culture day alone |
| Two atlas mappings disagree | Preserve source/version/applicability and the conflict | Majority vote among dependent references |
| Formal draft has no supported roles | Valid candidate with empty unsupported choices | Invent state/source IDs or retrieve a live atlas into the formal run |

The live case `reference-target` covers discovery; scoped provider and scientific-input
integration tests cover candidate construction, source binding and confirmation.
