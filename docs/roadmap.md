# BRIDGE Roadmap

This roadmap tracks the public notebook/API workflow after the Step1-Step3 package integration.

## Available Now

- Agent-first setup and workflow skills for Step0-Step3.
- Notebook-callable Step1 prescreening through `bridge.prescreen.prescreen`.
- Notebook-callable Step2 identity assessment through `bridge.identity.identify`.
- Component-first Step3 CLS scoring through `bridge.cls.CLSContext`, `component_A` through `component_F`, and `score`.
- Step1-Step3 report APIs for notebook-visible tables/figures plus saved Markdown, manifest, CSV, and image artifacts.
- External model asset manifest under `models/assets.json`.

## Next: Public Demo Hardening

- Finalize a public-safe demo dataset and model asset release.
- Curate one executed notebook per biological step with visible code, figures, tables, and concise interpretation.
- Verify the agent copy-paste flow in a fresh workspace.
- Keep README concise while placing deeper method notes in `docs/`.

## Next: Report Refinement

- Tune figure styling on the final public demo data.
- Extend interpretation templates where repeated validation runs show stable biological patterns.
- Add comparison panels only when the required protocol assets are present and public-safe.

## Later: Batch and Study Extensions

- Add multi-dataset run conventions around the existing notebook/API primitives.
- Expand protocol comparison guidance for larger studies.
- Add additional model manifests as reference assets mature.
- Publish versioned example outputs alongside releases.
