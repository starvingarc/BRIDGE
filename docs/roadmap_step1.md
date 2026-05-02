# Step 1 Roadmap

Step 1 covers reference construction and upstream whole-brain pre-screening in the full BRIDGE architecture.

Current status:
- notebook-callable prescreening API in `src/bridge/prescreen`
- output contract design for prescreened h5ad, RG candidate h5ad, probability CSV, and summary JSON
- plotting and interpretation templates remain future work

The goal for formalization is to define:
- stable inputs
- stable outputs
- explicit configuration contracts
- clear mapping from reference-construction logic to downstream Step 2 and Step 3 modules
