# Quick atlas mapping v0 implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement and verify this scoped chain.

**Goal:** An attached, declared laboratory H5AD produces a persisted, versioned quick mapping and source-bound positions on the existing developmental tree.

**Architecture:** P0-02 owns a registered Scanpy ingest mode. A research-scoped worker runs descriptive P0-01 checks and this mode in an isolated process; the object store owns atomic assessment transitions and authenticated result reads. A private, checksummed reference bundle binds sc/sn counts, annotations, tree geometry and method parameters.

**Tech Stack:** Python 3.12, AnnData/Scanpy, scikit-learn, existing ToolRegistry and FastAPI storage.

**Spec:** [Approved product design §7](bridge-product-design.md#7-图谱与参考) and [research objects](research-objects.md#34-atlasassessment样本映射到图谱).

## Global constraints

- Pre-graft uses REF-CHEN-VMB-SC-v1; post-graft uses REF-CHEN-VMB-SN-v1. No cross-modality fallback.
- Reference fitting uses reference expression only. Intersect measured genes; never zero-fill absent genes. Record effective feature and projection identities.
- Center both reference and query using the reference mean before ingest; query composition must not move a cell's projection.
- Data, source cell IDs, runtime paths and receipts stay in private storage. Originals remain unchanged.
- Standard mapping starts automatically only with declared matrix semantics, sample context and configured matching resources; missing prerequisites remain data_attached with a reason.
- No new LLM calls, frontend changes, calibrated OOD/age claims, chain thresholds, clinical claims or scientific qualification.
- Old results remain accessible. Restart marks interrupted work explicitly; retry creates a new version, never a fabricated success.
- Integration, publication and deployment remain separate.

## Review focus

- Missing or reordered genes: overlap is explicit and reference PCA fitting is reproducible; insufficient overlap fails.
- Pooled laboratory files: acceptance uses separately sourced subsets, never calls a pool one sample.
- Non-neural reference labels: no invented neural tree position; closed-set label transfer is not OOD detection.
- Tampered input/resource/result or cross-account reads: fail closed without revealing private paths or data.
- Duplicate attachment/retry, saturated worker and restart: persisted states remain truthful, originals and historical attempts remain available.

## Tasks

### 1. Registered reference mapping and private resources
Files: package quick_atlas.py, quick_atlas_reference.py, quick_atlas_runtime.py; P0-02 registry/spec/card; tests/test_quick_atlas_mapping.py; scripts/prepare_quick_atlas_reference.py.
Interfaces: freeze_reference(...) writes a versioned private manifest; map_counts(query, reference, tree, recipe) returns a bounded display summary and a full private cell table; run_quick_atlas_mapping(request, spec) returns ToolRun.
- [x] Write and observe failing tests for transfer, modality isolation, feature intersection, reference-centered projection, missing tree positions and integrity rejection.
- [x] Implement reference-only PCA/ingest, explicit candidate/uncalibrated status, source-bound numeric transfer and tree positions.
- [x] Bind checksummed outputs and real P0-01 receipt through ToolRegistry; run the targeted tests and commit.

### 2. Research attachment, worker and recovery
Files: web atlas_mapping.py / atlas_worker.py; research object models/store/HTTP; Settings/Service/lifespan; tests/test_research_atlas_mapping.py.
Interfaces: immutable mapping_input declaration; schedule(owner, research_id, sample_id) reserves an assessment and starts the registered pipeline; authenticated reads validate receipt/result bindings.
- [x] Write and observe failing tests for automatic start, missing declarations/resources, duplicate jobs, isolation, tampering and restart/retry.
- [x] Add bounded worker lifecycle, quota reservation, persisted job/result identities, fixed-reference retry and result projection.
- [x] Update the existing contract and frontend handoff; run affected object/conversation and mapping tests and commit.

### 3. Real sample acceptance and delivery
- [x] Freeze the controlled scRNA reference and tree bindings; retain snRNA as unavailable after nonintegral-count rejection, without rounding or fallback.
- [x] Split the existing pooled laboratory input by its declared source group into private derived inputs; preserve source hashes and membership.
- [x] Exercise real upload/attachment through HTTP, run registered tools, reopen outputs after completion/restart, and verify tree coordinates against the bound reference.
- [x] Record engineering results and uncompleted scientific controls separately; run proportional contract checks and a fresh whole-change review.
- [x] Commit a clean backend candidate and give Claude the exact API/results handoff. Do not merge or deploy implicitly.


## Tree marker display follow-up

The accepted existing tree remains the display baseline. The backend follow-up
adds the approved default marker panel to sample points and same-modality reference
points through a separately verified read-only artifact endpoint. It keeps the
mapping method and all uncomputed chain values unchanged. The interface contract
is maintained in [Research Objects](research-objects.md#132-树上-marker-表达补充合同)
and runtime behavior in [Quick Atlas Mapping](../docs/quick-atlas-mapping.md#marker-expression-for-tree-coloring).
Frontend implementation remains with its existing owner; implementation,
engineering acceptance and scientific qualification remain separate.
