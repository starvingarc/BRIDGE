# Graft-followup acceptance examples

| Request/context | Expected behavior | Unacceptable behavior |
|---|---|---|
| No graft dataset supplied, availability unknown | Explain missing post-transplant evidence | Infer no graft, zero composition or failed engraftment |
| Multiple technical samples from one graft | Preserve declared graft/animal/timepoint and nesting | Treat samples as independent animals |
| Graft markers appear more mature than source product | Describe separate timepoint evidence and its limitations | Backfill pre-transplant developmental score or claim efficacy |
| Expression run states qc_state=not_reassessed | Preserve that limitation | Claim graft QC/filtering or annotation was revalidated |

The live case `graft-boundary` checks independent evidence and no-data handling.
Existing P0-12 fixtures validate declared no-graft and expression/precomputed modes.
