# BRIDGE Knowledge

BRIDGE runtime retrieval uses the immutable packaged snapshot at `src/bridge/resources/knowledge_snapshot.json.gz`. Its curated inputs and source-verification record live in [`knowledge/catalog/`](catalog/).

The generated [catalog-backed method shortlist](active-methods.md) shows the methods selected from the global knowledge snapshot by current P0 packages. P0-10's package-owned methods and selection state live in its versioned [benchmark record](../docs/validation/p0_10_claim_verifier_benchmark_v0.1.md) rather than being duplicated in the global shortlist. The repository does not track exploded Method Cards, Source Cards, bindings, aliases, retrieval chunks or source URL lists.

Source accessibility and scientific validity remain separate. A verified URL does not promote a method to formal eligibility.
