# Culture-dish illustrations / 培养皿视觉素材

These eight **original SVG illustrations** are decorative artwork for the
[Soft Lab Console](../../plans/bridge-product-design.md) incubator and protocol-flow
cards. They are *not* microscopy, registered evidence, anatomical maps, or
scientific estimates. No cell fractions, stage boundaries, specimen ages, graft
positions, or product performance can be inferred from their shapes or colors.

| Workbench state | Artwork |
|---|---|
| Expanding / 扩增期 | [expansion](../../frontend/public/illustrations/culture-dishes/expansion.svg) |
| Stage I / 神经诱导 | [stage-i-neural-induction](../../frontend/public/illustrations/culture-dishes/stage-i-neural-induction.svg) |
| Stage II / 底板诱导 | [stage-ii-floor-plate-induction](../../frontend/public/illustrations/culture-dishes/stage-ii-floor-plate-induction.svg) |
| Stage III / 底板祖细胞 | [stage-iii-floor-plate-progenitor](../../frontend/public/illustrations/culture-dishes/stage-iii-floor-plate-progenitor.svg) |
| Stage IV / 神经元成熟 | [stage-iv-neuronal-maturation](../../frontend/public/illustrations/culture-dishes/stage-iv-neuronal-maturation.svg) |
| Frozen / 冻存 | [cryopreserved](../../frontend/public/illustrations/culture-dishes/cryopreserved.svg) |
| Grafted / 移植后 | [post-graft](../../frontend/public/illustrations/culture-dishes/post-graft.svg) |
| Draft / 未开始 | [not-started](../../frontend/public/illustrations/culture-dishes/not-started.svg) |

The files have transparent outside margins, a common `420 × 420` viewBox, no
network dependencies, no fonts or scripts, and a CSS `prefers-color-scheme`
adaptation for the glass background. They scale for incubator cards and
56–104px protocol-stage thumbnails. For a Vite-served static file, use
`/illustrations/culture-dishes/<filename>.svg`.

**Integration:** `frontend/src/workbench/StageDish.tsx` maps workbench states to
these files (`CultureDish`, `artFor`, `artForStage`) and replaces the earlier
procedural Canvas painter. Motion is a CSS layer on the whole illustration
(breathing, sway, drift, brightness, glow, and a glass sheen for growing
cultures), offset per dish and switched off under `prefers-reduced-motion`.
No measured value changes the artwork: proportions belong to the chain views,
not to illustrative colors or fill counts.

**Reference and rights review (2026-10-12):** General morphology was checked
against [neural rosette imagery in a published hPSC neural differentiation
study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10899886/) and
[neural-rosette protocol context](https://pubmed.ncbi.nlm.nih.gov/37148244/).
The existing external HDBR anatomy models have a
[CC BY-NC-SA 4.0 / non-commercial restriction](https://hdbratlas.org/copyright.html)
and are **not** embedded in these illustrations. Other searched microscopy
photographs were treated as visual references only, not as redistributable
assets. No third-party photographs, atlas geometry or textures have been copied.
These SVG vector paths were created specifically for this repository, under
its MIT-licensed project code/artwork.

**Review:** The images are conceptual and should be reviewed on both light and
dark surfaces and at card/thumbnail sizes during their later UI integration.
The current PR changes only static resources and this provenance note.
