# Step 1 Roadmap

Step 1 covers reference construction and upstream whole-brain pre-screening in the full BRIDGE architecture.

Current status:
- notebook-callable prescreening API in `src/bridge/prescreen`
- output contract for prescreened h5ad, RG candidate h5ad, probability CSV, and summary JSON
- report API in `bridge.prescreen.report` for prediction summaries, optional UMAP views, Markdown, manifest, and interpretation text

The goal for formalization is to define:
- stable inputs
- stable outputs
- explicit configuration contracts
- clear mapping from reference-construction logic to downstream Step 2 and Step 3 modules
- a public-safe executed notebook example
