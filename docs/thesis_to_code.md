# Thesis-to-Code Mapping

This repository is intentionally structured so that a reader can map the thesis workflow onto the codebase.

## High-Level Mapping

- **Thesis Step 1**: reference construction and whole-brain pre-screening
  - repository status: documented as planned work
  - repository location: roadmap and scope documents in `docs/`

- **Thesis Step 2**: identity assessment and candidate selection
  - repository status: formalized in BRIDGE v1
  - repository location: `src/bridge/identity`

- **Thesis Step 3**: concordance scoring, result packaging, and reporting
  - repository status: formalized in BRIDGE v1
  - repository location: `src/bridge/cls`, `src/bridge/io`, and `src/bridge/workflows`

## Why CLS Appears in Step 3

CLS, or **Composite Likeness Score**, is the mechanism BRIDGE uses to summarize developmental concordance after candidate selection has already happened.

That is why CLS belongs to Step 3 rather than Step 2:
- Step 2 decides which cells are credible target candidates
- Step 3 scores how well those candidates reconstruct the reference developmental program

## Why Step 1 Is Documented But Not Yet Released

The thesis describes Step 1 as part of the full workflow, but the public repository currently treats it as planned rather than fully released because:
- the code and interfaces are not yet stabilized as a public package module
- reference construction and upstream pre-screening still need clearer production-facing contracts
- public documentation should not overstate implementation maturity

## Reading the Repository Correctly

If you are reading BRIDGE from the perspective of the thesis:
- use `README.md` for the overall three-step picture
- use `docs/formal_workflows.md` for repository scope
- use `src/bridge/identity` for the released Step 2 implementation
- use `src/bridge/cls` for the released Step 3 implementation

If you are reading BRIDGE from the perspective of the code:
- treat Step 1 as architectural context and roadmap
- treat Step 2 and Step 3 as the actual released v1 package surface
