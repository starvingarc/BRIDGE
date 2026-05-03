# Models

This directory is the public entry point for BRIDGE model assets and model metadata.

Large model files are distributed through public object-storage URLs instead of normal Git blobs. The repository tracks only the manifest and documentation needed to fetch them.

## Asset Manifest

`models/assets.json` lists the public object-storage download URL, BRIDGE step, and repository-relative destination for each required asset. These URLs must not contain private server names, IP addresses, user names, or internal filesystem paths.

Expected downloaded layout:

```text
models/whole_brain_ref_model/model.pt
models/target_ref_model/model.pt
models/target_reference.h5ad
models/ref_sceniclike.h5ad
models/regulons.json
```

`target_reference.h5ad` is the target-specific AnnData paired with `target_ref_model` for Step2 identity assessment. Do not substitute `ref_sceniclike.h5ad` for Step2; that file is a reduced SCENIC-like reference used only by Step3 component F.

## Download

From the repository root:

```bash
python scripts/download_model_assets.py --dry-run
python scripts/download_model_assets.py
```

The dry run prints the planned public object-storage URLs and destinations without downloading files. The full command creates the expected `models/` layout. Use `--force` to replace existing downloaded assets.

## Step0 Validation

Step0 should inspect `models/assets.json`, download missing public assets when requested, and validate that the expected files exist before Step1-Step3 are run.

Downloaded model files should remain local runtime assets. Do not commit them back into the repository.
