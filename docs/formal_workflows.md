# Formal Workflows

## Conceptual BRIDGE Pipeline

BRIDGE follows a three-step conceptual pipeline:
- **Step 1**: reference construction and whole-brain pre-screening
- **Step 2**: identity assessment and candidate selection
- **Step 3**: CLS-based concordance scoring, reporting, and visualization

This file explains which parts are already formalized in the public repository and which parts remain planned.

## What Is Formalized in BRIDGE v1

The current public repository formalizes:
- **Step 2**: Identity Assessment
- **Step 3**: CLS A-F, result packaging, and reporting scaffolding

More concretely:
- `src/bridge/identity` provides the Step 2 package layer
- `src/bridge/cls` provides the Step 3 scoring layer
- `src/bridge/io` and `src/bridge/workflows` support packaging and workflow organization

## Step 1 Status

Step 1 is part of the intended BRIDGE architecture, but it is **not yet formalized in this repository as released workflow code**.

In thesis terms, Step 1 corresponds to:
- reference atlas construction
- integration of embryonic brain data into a biologically grounded reference space
- whole-brain pre-screening before target-specific evaluation

In repository terms, Step 1 is currently represented by roadmap and scope documentation rather than by a released package module.

## Step 2 Status

Step 2 is the formal **Identity Assessment** layer. Its role is to identify high-confidence target candidates under a more specific reference.

The current formal Step 2 package includes:
- query model loading
- prediction and probability handling
- calibration
- uncertainty estimation
- entropy-based and threshold-based candidate selection

## Step 3 Status

Step 3 is the formal **concordance scoring and reporting** layer. Its role is to evaluate how well the selected in vitro candidates reconstruct the intended in vivo developmental program.

The current formal Step 3 package includes:
- CLS component A-F
- shared result packaging
- serialization scaffolding
- reporting and visualization scaffolding

## Why the Distinction Matters

The repository intentionally distinguishes:
- the **full conceptual BRIDGE pipeline**
- the **subset of that pipeline already formalized in public package code**

This avoids implying that Step 1 is already productionized while still keeping the repository aligned with the thesis logic that motivated the codebase.
