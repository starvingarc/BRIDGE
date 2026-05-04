# Models

This directory is the public entry point for BRIDGE model assets and model metadata.

Large model files are distributed through public object-storage URLs instead of normal Git blobs. The repository tracks only the manifest and documentation needed to fetch them.

## Asset Manifest

`models/assets.json` lists the public object-storage download URL, BRIDGE step, and repository-relative destination for each required asset. These URLs must be public-safe and independent of private servers, internal IP addresses, user names, or local filesystem paths.

Expected downloaded layout:

```text
models/whole_brain_ref_model/model.pt
models/target_ref_model/model.pt
models/target_reference.h5ad
models/ref_sceniclike.h5ad
models/regulons.json
```

Use `target_reference.h5ad` with `target_ref_model` for Step2 identity assessment. Use `ref_sceniclike.h5ad` and `regulons.json` for Step3 component F regulon diagnostics.

## Download

From the repository root:

```bash
python scripts/download_model_assets.py --dry-run
python scripts/download_model_assets.py
```

The dry run prints the planned public object-storage URLs and destinations. The full command creates the expected `models/` layout. Use `--force` to replace existing downloaded assets.

Downloaded model files remain local runtime assets and stay outside Git history.
