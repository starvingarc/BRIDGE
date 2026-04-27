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

## CLI and Workflow Mapping

The released execution layer mirrors the thesis structure:
- `bridge identity run` -> thesis Step 2
- `bridge cls run` -> thesis Step 3 scoring
- `bridge report summarize` -> thesis Step 3 reporting/output packaging
- `bridge report summarize-batch` -> multi-dataset Step 2 + Step 3 reporting wrapper

Step 1 is documented as the upstream reference-building stage. The current CLI focuses on the released Step 2 and Step 3 execution surface.

## Why CLS Appears in Step 3

CLS, or **Composite Likeness Score**, is the mechanism BRIDGE uses to summarize developmental concordance after candidate selection has already happened.

That is why CLS belongs to Step 3 rather than Step 2:
- Step 2 decides which cells are credible target candidates
- Step 3 scores how well those candidates reconstruct the reference developmental program

## How Step 1 Is Represented

The thesis describes Step 1 as part of the full workflow. The public repository represents it through architecture and roadmap documents while the package interface is being defined:
- stable input and output contracts
- reference-construction configuration
- downstream handoff into Step 2 and Step 3

## Reading the Repository Correctly

If you are reading BRIDGE from the perspective of the thesis:
- use `README.md` for the overall three-step picture
- use `docs/formal_workflows.md` for repository scope
- use `src/bridge/identity` for the released Step 2 implementation
- use `src/bridge/cls` for the released Step 3 implementation

If you are reading BRIDGE from the perspective of the code:
- treat Step 1 as architectural context and interface roadmap
- treat Step 2 and Step 3 as the actual released v1 package surface

Reporting note:
- the current report layer intentionally reaches back into Step 2 artifacts so that candidate-selection context is not lost when Step 3 results are summarized

Repository note:
- the public repository is meant to expose the stable software surface
- environment-specific validation practices can live in development or deployment workspaces
