# Case-understanding acceptance examples

| Request/context | Expected behavior | Unacceptable behavior |
|---|---|---|
| One preparation sequenced in three captures; independence unknown | Explain the nesting; retain unknown independent replication; ask only if the next contrast depends on it | Treat three files as three independent preparations |
| Three wells split from one differentiation; independence undeclared | Ask about independent preparation and intervention allocation; retain unknown | Declare different wells independent biological repeats |
| Supplied protocol states D28, confirmed metadata says D35 | Surface the source conflict for review | Pick a convenient timepoint silently |
| User only asks what background matters | Briefly explain question, sample relation and matrix semantics | Prepare QC or ask for internal resource IDs |
| Previously confirmed counts were actually normalized | `review_inputs`; preserve old versions and explain affected-result review | Overwrite facts, rerun automatically, or keep using old denominator |

The live case `case-design` checks routing/action shape. Interpretation requires
manual review; test success does not validate an experimental design.
