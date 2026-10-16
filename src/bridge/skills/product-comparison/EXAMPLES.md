# Product-comparison acceptance examples

| Request/context | Expected behavior | Unacceptable behavior |
|---|---|---|
| One preparation has three captures, another has one | Explain preparation-level units and confounding | Treat four captures as independent batches |
| One multiplexed capture contains four declared preparations; allocation unknown | Preserve four preparation identities while checking independence and pooling/condition confounding | Infer one biological replicate from one capture, or assume all four are independent |
| Comparison uses different denominators or method versions | Explain comparability gap or approved alignment need | Directly subtract values as if comparable |
| Descriptive difference favors a new protocol | Report difference with confounding and replication limits | Claim the protocol caused improvement or rank products |
| Request is gene DE within one cell type | Route to expression-exploration and its registered contrast | Use structured product comparison on raw expression files |

The live case `comparison-contract` covers routing and design boundaries. Existing
P0-07 fixtures own numeric comparability/independence validation.
