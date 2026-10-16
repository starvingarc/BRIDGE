# BRIDGE frontend

React/Vite browser client for the private BRIDGE Web interface.
The Python service remains in `src/bridge/web/`; the browser consumes its
same-origin API. Account/password login is the only entry; expired sessions return
to that account screen. Obsolete server authentication modes fail closed.

## Build and test

Use a Node.js version satisfying `engines.node` in [package.json](package.json).
The package declaration is advisory in npm's default configuration. From the repository root:

~~~bash
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
~~~

The build writes `frontend/dist/`. The checkout launcher uses it automatically;
installed wheels require its absolute path in `BRIDGE_WEB_STATIC_DIR`.

## Local development

Start the backend with the [private configuration](../docs/web-preview.md#start-a-private-instance)
and the existing Vite proxy port, then run Vite:

~~~bash
bridge-web --config /absolute/path/web.env --env development --port 8765 --origin http://127.0.0.1:5173
# In another terminal:
npm --prefix frontend run dev
~~~

Vite listens on `127.0.0.1:5173` and proxies `/api` to
`127.0.0.1:8765`. The explicit development origin above matches the browser origin.

Authentication, approval, assessment, versioning and artifact behavior are
defined in the [Web guide](../docs/web-preview.md). Repository contribution and
maintenance requirements live in [AGENTS](../AGENTS.md).

## Research navigation

Login opens `App`'s research directory and card search. A research contains
independent conversations and shared originals, with no imposed experiment or
batch folder. `SessionWorkspace` preserves the previous conversation controller,
polling and request generation checks; it composes the existing scientific UI.
The materials drawer handles one upload/selection flow for both the composer and
protocol intake. Adding a file stores an original; selecting it binds only the
current conversation. Legacy conversations remain under **历史会话**.

The initial view is conversation, with explicit **实验背景** and **结果** controls.
A user selection survives polling. Ready results can otherwise foreground the
reader, with conversation alongside it on desktop and a single selected panel on
narrow screens. The old draggable divider and its resize state are removed.
The workbench's **报告** entry opens the existing conversation report reader. This rail entry is transitional: reports move to the experiment and comparison pages and the materials view (see the [workbench roadmap](../plans/user-journey.md)).
The `#/r/<research>/reports/<session>` address restores the selected conversation
and report tab on reload. The session list remains available for other histories;
a conversation without a report shows its existing empty state.
See [research workspace](../docs/research-workspace.md) for persistence and limits.

Workbench conversations stay in the existing side drawer. The incubator uses the
research's fixed conversation; a focused run uses that run's fixed conversation.
History is restored from the server, and all typed questions use the same message
and cancellation routes as full sessions. Tree questions prefill a scoped question
for sending; live workbenches never produce local example answers. The full-session
link retains the established analysis input, approval and result interfaces.
Changing account/research/run discards pending UI responses from the previous scope.

## Assessment reading flow

The overview groups server-owned observations into five expandable domains. Each
card opens and focuses the applicable results, with figures before detailed
values and provenance. Available results need no badge; missing or unavailable
states remain visible.
Short status labels and shapes retain unavailable and missing states. Disclosures
reveal explanations and sources; evidence references open their bound graph
nodes. Confirmed intake facts remain editable
and can be expanded without repeating the full form. Versioned proposed
explanations remain in the conversation as expandable records; their unverified
status stays visible while the overview holds the concise current reading.

The report tab groups registered research artifacts by input revision, graph
version and snapshot hash. Its sandboxed preview reads the verified HTML artifact
itself, with no client-side regeneration. Downloads use the same group. Pending
input corrections suppress current previews; historical reports retain the
server's acknowledgement gate. A completed report is shown as results ready,
while scientific qualification remains separate. An accepted explanation can also
have ready results; its server-authorized continuation remains visible until the
researcher continues to report generation.

## Workspace appearance

The workspace uses cold grey-white surfaces, restrained charcoal actions and
abstract cell covers matching the approved research design. Covers are purely
decorative. Base scientific controls remain in `src/styles.css`; the directory,
materials drawer and composition styles live in `src/research-workspace.css`.
Scientific chart/category colors and warning states retain their meaning.

Frosted material belongs to navigation and overlays. Tables, figures and report
content remain opaque; verified report HTML is not restyled or regenerated.
CSS backdrop blur has an opaque fallback. Reduced motion, reduced transparency
and increased contrast preferences keep controls usable without material effects.
Short transitions provide press feedback and drawer/dialog movement; result
content has no entrance animation or motion that delays access.
The implementation uses existing CSS, with no glass or animation dependency.

## Model settings

The sidebar footer contains only the clickable account ID. It opens one settings
dialog with **账号**, **模型**, and administrator-only **测试管理** navigation.
Account settings include password changes and sign-out. Desktop uses a left
settings navigation rail; narrow screens use tabs above the scrollable content.
Only the active section mounts and loads data. Closing or changing sections
discards credential drafts; pending writes and connection tests keep the dialog
and current section in place; directory reads can be dismissed.

The **模型** directory presents the shared provider and each user's saved providers
in one place. Provider cards list models; selecting one changes later tasks. A shared
badge identifies the operator-managed connection. Only administrators can edit it;
ordinary accounts can use its listed models without seeing its key.

The editor offers DeepSeek/OpenAI presets and custom OpenAI Chat Completions APIs,
named provider IDs, manually entered model IDs and an optional fetched catalog.
Catalog reads do not save; connection tests send only fixed text and do not save.
Creating a provider leaves the current selection intact. Removing the selected
provider returns later tasks to the shared default. At most 32 private providers
and 100 models per provider are saved.

Keys are never returned to the form or written to browser storage. Blank inputs
retain a key only for the same account, provider ID and unchanged endpoint.
Changing an endpoint clears the draft key. Existing single personal configurations
are read as a provider without rewriting storage until the next edit.

The provider editor/catalog interaction and API-key validation are adapted from
DeepSeek Harness 0.2.0-rc.2's `@deepseek-ai/dsh-client-ui-settings-models` module.
Its MIT copyright and license are retained in
[deepseek-harness.txt](public/licenses/deepseek-harness.txt). BRIDGE retains its own
HTTP API, account authorization and restricted outbound transport.

## H5AD upload limits

The upload control reads the authenticated `/api/config` endpoint and refreshes it
before sending each file. The displayed limit is deployment-specific; it is not
a fixed frontend default. A missing or invalid limit disables upload until the
researcher retries successfully. Over-limit files are rejected before transfer.

The interface distinguishes file-transfer limits from the limits on expanded H5AD
data and individual datasets. Compressing a file does not reduce these internal
resource requirements. Proxy rejections without a JSON response have a separate
message. Uploading/checking is an indeterminate state, not a completion percentage.

## Standalone developmental anatomy preview

The anatomy component is a separate local preview; it does not alter the main
research workflow or register any scientific result. Fetch the pinned public
assets, then start the preview and open `/anatomy.html`:

~~~bash
node frontend/scripts/fetch-anatomy-models.mjs
bridge-web --config /absolute/path/web.env --env development --port 8765 --origin http://127.0.0.1:5173
# In another terminal:
npm --prefix frontend run dev:anatomy
~~~

Use `npm --prefix frontend run build:anatomy` for the standalone build in
`frontend/anatomy-dist/`. The normal application build excludes this entry and
its assets. Downloaded geometry stays in ignored `frontend/private_assets/`.
The acquisition script verifies exact SHA-256 values and refuses changed sources
or unexpected existing files. It preserves the original GLB bytes.

The viewer uses HDBR Atlas OPT reconstructions for
[CS14 / A386](https://hdbratlas.org/carnegie-stages/CS14.html) and
[CS15 / N340](https://hdbratlas.org/carnegie-stages/CS15.html). Both have seven
meshes: external mask, neural tube, eye, otic vesicle, dorsal root ganglia,
heart and liver. The neural tube is not independently segmented into brain
regions. Approximate source ages are postovulatory days; GW/PCW proximity is
context only, not specimen matching or spatial registration. Display framing is
normalized independently for each specimen, so rendered sizes are not an
absolute growth comparison. The preset views are unnamed viewing directions;
no anatomical orientation calibration is asserted.

Rotation, zoom, region picking/isolation, stage selection, and separate shell
and tissue opacity controls operate only on these source meshes. Coordinates
and topology are retained; colors, opacity and display framing are changed.
Transparent surfaces use standard polygon blending, so intersecting surfaces
can show ordering artifacts; this is not a volumetric rendering.

Attribution: **HDBR Atlas (https://hdbratlas.org)**. Source material and adapted
visualizations are **CC BY-NC-SA 4.0**, for non-commercial use, subject to the
[HDBR terms](https://hdbratlas.org/copyright.html) and
[license](https://creativecommons.org/licenses/by-nc-sa/4.0/). This does not
imply HDBR endorsement. Commercial use requires contacting HDBR separately.
Relevant publications: Kerwin et al. (2010), *The HUDSEN Atlas*,
[doi:10.1111/j.1469-7580.2010.01290.x](https://doi.org/10.1111/j.1469-7580.2010.01290.x);
Gerrelli et al. (2015), *Enabling research with human embryonic and fetal tissue
resources*, [doi:10.1242/dev.122820](https://doi.org/10.1242/dev.122820).

### Candidate slice comparison

The CS15 preview can display an explicitly unregistered candidate sagittal plane.
It uses the optic mesh bounding-box centre and its local Z axis (the bilateral
span), transformed through the source node matrix. This is a geometric display
hypothesis, not validated anatomical calibration. Plane offsets are normalized
display units; no micrometre depth, slice ordering, or cell coordinates are assigned.
CS14 does not inherit the CS15 hypothesis.

An optional comparison panel reads three fixed images from ignored
`frontend/private_assets/localization/` through a loopback-only development
middleware: `section2-tissue-overlay.png`, `atlas-cs15-sagittal-11.jpg`, and
`atlas-cs15-frontal-24.jpg`. The tissue image is private and must not be committed
or published. These evidence files are not imported or copied into builds.
The panel is a development aid; built previews require their own authorized
evidence delivery. HDBR reference sections are N727 sagittal image 11 and A352
frontal image 24, separate specimens from the N340 GLB. Similarity of silhouettes
is qualitative and does not establish section depth or registration.


### Product UMAP and spatial reference

The result page reads the authenticated `spatial-context` projection for each saved
expression UMAP. Candidate type and original-cluster modes share hover/focus
preview while unpinned, click/Enter pinning and Escape clearing. Pins take priority
over hover and focus; plot hover waits for a stable group before updating. Legends
sit beside their plots and stack in narrow cards. Counts use full product and
capture denominators. Unknown annotation, unreviewed/missing mapping, observed
zero and unavailable reference remain distinct. The existing standalone UMAP and
source-bound static figure/table remain available when linking is unavailable.

The linked view adapts to its result-panel width and can expand into a modal.
Complete reference points are drawn on a static background canvas and a separate,
type-indexed highlight canvas. MiniAnatomy loads a configured, authenticated GLB
lazily, accepts no product selections and remains optional. Source model stage is
separate from reference sample stage; the plane remains an unregistered hypothesis.
`anatomy/previewAssets.ts` owns the standalone preview's private asset imports;
main application builds contain neither GLBs nor private reference coordinates.

Configuration and prerequisite behavior are in the [Web guide](../docs/web-preview.md#产品与空间参考联动配置).
Engineering coverage and remaining acceptance boundaries are in
[display verification](../docs/validation/product-spatial-link.md).

### Researcher-facing language

The workspace is for wet-lab researchers, clinicians and general bioinformatics
users. Overview cards, reading tabs and approval controls name biological
questions and actions. Internal tool IDs, schemas, hashes, raw JSON and registry
editors are absent from researcher views, including collapsed details.
Sources still navigate using exact versioned bindings; scientific values,
denominators, named methods and unresolved limitations remain available.
The overview keeps interpretation paragraphs, source lists and confirmed product
facts behind disclosures. Citation links reveal their exact source before
navigating to it. The two most recent conversation entries remain visible, while
input cards stay accessible.
Completed plans are collapsed; pending decisions and errors remain visible.
Result tabs provide navigation without repeating a second row of result actions.
Audit records remain in registered backend artifacts and developer interfaces. Current report HTML is rendered unchanged in the sandboxed reader;
its audit template is inert and never displayed as reader content.

### Figure-first result details

ResearchFigures owns SVG/DOM charts derived only from scope-bound saved values.
Composition uses a fixed 0–100% scale, retains all unknown/unavailable categories,
and offers exact counts and denominators in a closed table. Marker plots preserve
positive/counter roles; parent-only reference assignments stay visibly qualified.
Program means and cell P10–P90 spans use separate method/unit scales including
zero; these spans are not confidence intervals. ReferenceSimilarity uses −1 to 1
and draws no point for missing coefficients. Source groups are never combined.

One selected domain mounts at a time. Container-sized labels and tracks support
narrow panels without shrinking text; values remain visible without hover and
native disclosures provide tables and interpretation limits. Software and algorithm
names stay in method disclosures; default labels describe relative background
expression and gene-set association. No new chart dependency, persistent selection
state or scientific measurement is added.

The cell-state detail opens a four-panel view: vertical composition bars, UMAP,
reference anatomy and spatial coordinates. A read-only request resolves one saved
UMAP against the current scope digest and candidate receipt, requiring the complete
DataView and input SHA to agree. The candidate receipt SHA is checked again against
the assignment source on every context load and reload, preventing a later same-view
candidate from replacing the selected assessment evidence. This browser-only binding does not modify the
scientific evidence snapshot, saved report, assessment admissions or execution.
Missing, denied, changed or ambiguous sources leave the saved composition visible.
LinkedCellExplorer owns one hover/pinned selection; clicks outrank hover and focus.
Unknown and unavailable assignments retain separate counts, bars and colors.
Shared type colors remain stable; broader spatial matches keep their own identities.
The composition denominator always contains all product cells, independently of
UMAP display sampling. Spatial coordinates retain aspect and axis direction;
no physical scale or registration is inferred. Anatomy is a small reference panel.

Only an expanded cell-state card fetches the display binding. SVG renders the few
composition marks and axis labels, the existing Canvas renderer owns dense points,
and the existing lazy Three.js viewer owns anatomy. The narrow panel stacks plots
and permits horizontal bar-chart scrolling; the expanded dialog exposes the full
layout. Original counts remain keyboard-accessible. The 3D export renders the saved
model at 1200 x 1200 pixels, and the data export includes the exact context, section,
selection and palette for static figure generation. Existing receipt-bound plots
retain their authenticated source routes.

Figure design follows the evidence, missingness, typography and export review in
[K-Dense Scientific Visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-visualization/SKILL.md).
This is general research-figure guidance, not a journal acceptance certification.
Reference: Kassis T, Agarwal V, He Y, Patel D, Brueckner AM (2026),
[Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065).

### Composition display hierarchy and reference subtypes

The Web view uses unnumbered chart titles and a shared macaron palette. Composition,
UMAP and spatial distribution are the primary views; anatomy remains a small
supporting panel. Source disclosures expose concise names, versions and attribution;
internal review narratives remain in source artifacts. Numeric measurements,
missing states and concise method limitations stay available.

The optional reference-subtype mode reads saved, hash-verified auxiliary reference
correspondence. It refines only primary-assigned cells whose declared parent agrees
with the primary type. Other cells retain their broad label or original missing
state. This mode preserves the full denominator and does not replace primary
assignments, scientific evidence admission or report qualification. Reference-subtype
selections control composition and UMAP; spatial correspondence remains in broad-type
mode. Missing, changed or ambiguous auxiliary evidence leaves primary views available.


### Literature-assisted interpretation

The assessment scope form defaults public retrieval off. Enabling it requires
selecting public search concepts, which are shown again in scope approval along
with search/read limits. The source panel distinguishes no results, unavailable
retrieval, bibliographic-only records and saved abstracts. Explanation references
show the source title and unverified species/lineage/stage/experimental
applicability; measured evidence keeps its separate existing links.

## Workbench preview

`npm --prefix frontend run dev:workbench` serves the workbench with example protocols on port 5179. A private atlas tree placed at `frontend/private_assets/workbench/devtree.json` is served locally; otherwise a synthetic tree is shown. The design is maintained in [BRIDGE product design](../plans/bridge-product-design.md).
