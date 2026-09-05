# P0-02 deterministic grouping artifacts

Package: `0.5.3`

## Correction

Repeated raw-count requests could produce the same exploratory grouping labels
and scientific statistics but fail immutable output reuse. Wall-clock duration
and process peak memory were serialized into the scientific grouping metadata,
so their changes altered its content hash.

The correction removes those two volatile measurements and their collection.
Stable method parameters, clustering diagnostics, grouping identity and thread
configuration remain. Clustering, normalization, state evidence and scientific
status are unchanged.

## Verification

- The synthetic repeated-grouping regression failed on the previous code with
  unchanged labels and grouping hash, and passed after the correction despite
  changing mocked runtime measurements.
- `python -m pytest tests/test_cell_state.py -q`: 46 passed before integration.
- On the combined installed wheel, the six relevant P0-02 input-preservation,
  count-conversion and deterministic-replay tests passed.
- The installed integration suite passed 39 tests. All three integration profiles
  validated; 157 model, source and installed Schema copies matched.
- An independently repeated exact request succeeded twice with the same run ID.
  Every artifact content hash matched, and the input remained unchanged.
- Repository policy and `git diff --check` passed.

The combined wheel tested the runtime tree at commit `0afc9df0`; this record
and its README link were added afterward without changing executable code.
The replay evidence remains in private validation storage. No resource
identifiers, locations, biological results or input hashes are published here.

This is an engineering reproducibility correction. P0-02 remains
`candidate/shadow`; it adds no scientific freeze, calibrated identity or
release authority.
