# Server Reproducibility Validation

**Date:** 2026-08-12

**Status:** `engineering_validation_passed_shadow_only`

**Validated implementation:** `0029ff46841d5b92630ee4e5750ba2fe73961c03`

This public-safe record covers engineering reproducibility only. It validates the
BRIDGE package, projections, environment contracts and data-free adapter loading.
P0-02 remains a shadow candidate; this record does not freeze a state, method,
threshold or product role.

## Provenance

| Artifact | SHA-256 |
|---|---|
| External 194-file evidence manifest | `372020192edac13d77aafd613828e9a7565d327b1db6e1d4dc972aa785b11365` |
| Verified transfer bundle | `69035ef92b05a769c481ded87c1fd1b21a0588535e3c35682a3ae0b6fe4715e9` |
| Git source archive | `ca5aef96f194c9649495c67bc044b906e2c45d3551c1df8546688f38157ce5a4` |
| Built wheel, `bridge-0.2.0.dev0-py3-none-any.whl` | `197ff61b9734ae787c73fdb2c25a182a397bdbd9a1a07c6ea4d72f1a59c60fb0` |
| Installed P0-02 freeze implementation source | `853fb9a1ac2f57aa60de62d715c81b25ce7fe51d60e7c934aaaf027e7925c4c2` |

The source archive and wheel were produced from the validated implementation
SHA. The same wheel was installed without dependency changes into the core and
cell-state Python environments. Smoke checks imported BRIDGE from each installed
wheel rather than from the source checkout.

## Core environment and repository gates

The core environment was rebuilt with strict channel priority from the tracked
contract. Its exact constraints were Python 3.12, pip 25.1, setuptools 84.0.0,
wheel 0.47.0, NumPy 2.2, pandas 2.3, SciPy 1.16, scikit-learn 1.7,
Pydantic 2.12, PyYAML 6.0, AnnData 0.12, Scanpy 1.11, h5py 3.14,
Matplotlib 3.10, PyArrow 21, pytest 8.4, jsonschema 4.25,
cryptography 46.0 and Scrublet 0.2.3. The resolved runtime included Python
3.12.13, pip 25.1.1, NumPy 2.2.6, pandas 2.3.3, SciPy 1.16.3,
scikit-learn 1.7.2, Pydantic 2.12.5, Scanpy 1.11.5, PyArrow 21.0.0 and
pytest 8.4.2.

The following engineering gates passed:

- four focused regressions: sparse-HDF5 clock/config determinism, generated
  knowledge counts, curated P0-01 source verification and competitor isolation;
- the full installed-wheel suite: 192 passed, with one expected synthetic AnnData
  duplicate-variable-name warning;
- discovery of exactly 12 Tool Packages, with only P0-01 and P0-02 implemented;
  P0-03 remained a scaffold;
- knowledge validation: 354 methods, 387 canonical public sources, 396 bindings,
  zero dangling references and zero formal-eligible methods;
- repository policy, schema/card parity, example-version checks and the
  `domain_score=null` boundary; focused projection checks passed 5/5 and domain
  score checks passed 3/3;
- two consecutive three-generator passes with no tracked-byte drift;
- wheel smoke checks in both Python environments;
- 192 tracked files, a clean worktree at the validated SHA, and no tracked Git
  LFS pointer.

## Data-free adapter health

The Python adapter health check loaded adapter implementation 0.2.3 and verified
its CellTypist and scANVI metadata boundaries without opening scientific data.
The checked versions were CellTypist 1.7.1, scvi-tools 1.4.0.post1,
decoupler 2.1.4, torch 2.9.1, NumPy 2.2.6, pandas 2.3.3, SciPy 1.16.3,
Scanpy 1.11.5 and h5py 3.15.1.

The R environment reported R 4.6.1 and loaded SingleR 2.14.1, scmap 1.34.0,
scConform 1.0.0, UCell 2.16.0, Harmony 2.0.4 and Symphony 0.1.3. Harmony and
Symphony were installed from independently verified archives:

| Package | Verified archive root | Archive SHA-256 | Installed-file manifest SHA-256 |
|---|---|---|---|
| Harmony 2.0.4 | `df19af23ae0639bd6ea2da63898f973f08c85862` | `6c0dc183288c547f82152f682b6d9563807af564f07d3af70b8079b9ba7277cf` | `a0efd8b744416a1b29ad288ff96965512f1cd10228b2823cec553a781b151038` |
| Symphony 0.1.3 | `7c5905988734d9cfe6e1e97a658664717c4ba7b7` | `82b01602a63405e8615e124d2a0ebae9ad8c889e210207473fe6ba9e6959229b` | `23ab9c3c06066bfe2fbe78d61b1c3cae05f28466fb3d2fb23c5d6bfb2774f428` |

The installed package descriptions did not contain `Remote*` commit fields.
Provenance therefore rests on the verified archive root, archive hash and
installation log, plus the installed-file manifest. Only
`BRIDGE_HARMONY_COMMIT` changed, from
`b7b5a77ea3d16724726491390f8722c173c51b39` to
`df19af23ae0639bd6ea2da63898f973f08c85862`; the other eight recorded R
environment variables remained unchanged. The packaged R adapter loaded and all
25 expressions parsed. This was a data-free parse/load check, not a method run.

## Scientific boundary

No scientific dataset or locked or sealed asset was opened; no locked runner or
scientific benchmark was executed. No state or method is frozen, and no claim is
made about efficacy, safety, potency, product ranking or release readiness.
P0-02 remains shadow-only pending biological review, an approved FreezeGate and
the locked evaluation. P0-03 was not started and remains blocked until P0-02 has
a valid release manifest.
