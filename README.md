# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is a research software package and agent-guided notebook workflow for evaluating in vitro cell products against in vivo developmental references. The public workflow is intentionally notebook-first: Step1 prescreens candidate RG-like cells, Step2 identifies target mDA progenitor candidates, and Step3 scores developmental concordance with CLS components.

## Agent Quick Start

For a first-time install, send this to Claude Code, Codex, or a similar coding agent:

```text
Help me install https://github.com/starvingarc/BRIDGE
```

Then run the workflow through the repository-local skills:

| Skill | Invocation | Purpose |
| --- | --- | --- |
| `bridge-step0` | `/bridge-step0` or `@bridge-step0` | Initialize environment, model assets, config, and run directory. |
| `bridge-step1` | `/bridge-step1` or `@bridge-step1` | Prescreen one in vitro `.h5ad` dataset and produce RG candidate artifacts. |
| `bridge-step2` | `/bridge-step2` or `@bridge-step2` | Run mDA progenitor identity assessment from Step1 RG candidates. |
| `bridge-step3` | `/bridge-step3` or `@bridge-step3` | Run CLS components and generate summary/manifest artifacts from Step2 outputs. |

Command names are lowercase for compatibility. The project brand remains **BRIDGE**. Full copy-paste demo prompts are in [docs/agent_demo.md](docs/agent_demo.md).

## Python API

Install from GitHub or from a local checkout:

```bash
pip install git+https://github.com/starvingarc/BRIDGE.git
# or, from a cloned source tree:
pip install -e .
```

Notebook-callable entry points:

```python
from bridge.prescreen import prescreen
from bridge.identity import identify
from bridge.cls import CLSContext, component_A, component_B, score
```

The high-level notebook flow is:

```python
step1 = prescreen(adata, ref_model_dir="./models/whole_brain_ref_model", output_dir="./runs/demo_dataset/step1", prefix="demo_dataset")
step2 = identify(bdata_rg, adata_ref, ref_model_dir="./models/target_ref_model", target_class="RG_Mesencephalon_FP", output_dir="./runs/demo_dataset/step2", prefix="demo_dataset")

ctx = CLSContext(
    bdata=step2.bdata,
    adata_ref=step2.adata_ref,
    target_class="RG_Mesencephalon_FP",
    output_dir="./runs/demo_dataset/step3",
    dataset_id="demo_dataset",
    probs_ref_cal=step2.probabilities.probs_ref_cal,
)

component_A(ctx)
component_B(ctx)
cls_result = score(ctx)
```

## Documentation

- [Agent demo script](docs/agent_demo.md): full video/demo flow.
- [Skills](docs/skills.md): repository-local Step0-Step3 skill interface.
- [Formal workflows](docs/formal_workflows.md): package surface and artifact contracts.
- [Thesis-to-code mapping](docs/thesis_to_code.md): how the thesis workflow maps to the repository.
- [Roadmap](docs/roadmap.md): model assets, plotting functions, reports, and future extensions.

Polished per-step plotting functions, rich biological interpretation text, and publication-ready executed notebooks are roadmap items. Current outputs are artifact-focused and should not be described as final biological reports.

## Repository Map

```text
src/bridge/        Python package
configs/           public config templates
models/            model metadata and model-asset entry point
notebooks/         placeholder area for formal notebook examples
docs/              detailed workflow and roadmap documentation
.claude/skills/    repository-local Step0-Step3 skills
```
