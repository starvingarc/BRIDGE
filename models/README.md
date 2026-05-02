# Models

This directory is the public entry point for BRIDGE model assets and model metadata.

Model files may be committed when they are intentionally part of the public BRIDGE software distribution or required reproducible artifacts. If model files are large, store them with Git LFS rather than normal Git blobs.

## Expected Role in the Agent Demo

Step0 should inspect this directory to validate that the required reference models and metadata are available before Step1-Step3 are run.

Recommended model documentation for each model directory:
- model name and BRIDGE step
- expected input object type, usually `.h5ad`
- required count layer or expression layer
- reference label key and target labels
- files required to load the model
- downstream step that consumes the model

## Current Boundary

This directory may contain metadata before the final public model assets are added. Step skills should treat missing large model files as a setup issue and report the expected location clearly rather than inventing paths.

Keep model metadata and model files clearly separated from dataset-specific runtime configuration.
