# Research workspace

Source implementation; validation and preview acceptance are tracked in the [implementation plan](../plans/research-workspace.md).

## Organization

A **研究** is a durable, account-owned research workspace with a name, optional description, shared original materials and any number of conversations. A **会话** belongs directly to a research workspace. Researchers choose its purpose; no experiment, batch or assessment folder is imposed between research and conversation. The [domain vocabulary](../CONTEXT.md) defines these terms.

Original H5AD, protocol and supporting document files are shared within a research. Conversations retain independent messages, selected analysis inputs, declarations, fact confirmation, approvals, tool runs and results. Selecting a shared file for analysis creates a session-local binding to immutable bytes; it does not import another conversation's interpretation or approval. Newly added material becomes visible to other conversations without silently replacing their current inputs. Supporting metadata files can be stored and downloaded; they do not establish a sample join or scientific input contract by themselves.

Research ownership uses the existing account boundary. A research identifier never grants another account access, including to file downloads. Files remain private and quota-limited. Removing a conversation must not remove the shared originals. Legacy conversations remain reachable in a clearly labeled historical area; they can be placed into a research explicitly without changing their scientific records.

## Appearance and interaction

Login opens a research home with search, create action and research cards. A pale neutral laboratory palette, layered glass navigation, restrained charcoal actions and abstract cell covers provide visual continuity. Covers are decorative and do not encode assay data or qualification. Reading surfaces remain opaque, scientific chart colors retain their meaning, and the existing account-only settings entry remains at the lower left.

Inside a research, the sidebar lists conversations and offers a free new conversation. Shared materials open in a drawer from the header or composer. A research with no conversations offers a clear first-conversation action; a research with no materials does not block discussion. Session names can be edited. Existing archive, restore, delete and settings flows remain usable.

The conversation initially leads. Input/background review, approvals and pending questions remain reachable through the existing scientific components. When results become available, the workspace can foreground results while retaining a conversation area. A deliberate user view choice is preserved during polling; routine state updates never pull the reader away from an open figure or report.

Narrow layouts provide a working navigation drawer, one selected conversation or results panel, readable controls and access to materials. Keyboard focus, reduced motion, reduced transparency and increased contrast remain supported. Waiting, failure and empty states show actual request state; no invented study, metrics or scientific result ships in the application.

## Implemented paths and limits

`App` owns the research directory; `SessionWorkspace` retains the existing conversation controller, request fences, polling and scientific components. `ResearchStore` owns only research metadata and immutable originals. There is no additional experiment object or second scientific-state store.

The materials drawer accepts H5AD, PDF, DOCX, TXT, Markdown, CSV and TSV. Documents and supporting tables have a 25 MiB ceiling, also bounded by the deployment upload limit; H5AD uses the existing finite deployment settings. Each account has at most 256 research workspaces, each research at most 128 materials, and each conversation at most eight selected H5ADs. Originals and session copies count towards account and global storage quotas.

Choosing H5AD makes an independent private copy and uses the same registration method as legacy uploads. Choosing a protocol requires a current H5AD; opening the drawer from its experiment background preserves that file as the initial target. Repeated selection is idempotent. Protocol interpretation and researcher confirmation remain separate. Legacy H5ADs can explicitly be saved to the research library after assignment. Existing session-local protocol attachments remain available in their original intake; the interface does not bulk-copy them when moving a conversation.

H5AD copying and legacy sharing use the existing per-session upload guard while streaming outside the service lock, so unrelated conversations remain accessible. Failed file transfers do not register new inputs. Downloads verify original checksums before returning bytes.

The old mandatory side-by-side shell, draggable divider and standalone empty-workspace component are removed. The existing conversation, intake, assessment, results/report, archive and account settings components are reused. No scientific calculation, extra runtime dependency or demonstration data is added.

## Scientific boundaries

The organization layer does not change the [ten-step scientific workflow](BRIDGE_PRD.md#61-agent-总体工作流). ProductCase, batch identity, matrix semantics, sources, approval, evidence/version binding and historical report access retain their existing owners and checks. Missing values remain missing; shared storage implies neither biological comparability nor permission to reuse a prior conclusion.
