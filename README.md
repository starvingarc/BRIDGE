# BRIDGE

**Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation**

BRIDGE is a research software package and agent-guided notebook workflow for evaluating in vitro cell products against in vivo developmental references. The public workflow is notebook-first: Step1 prescreens candidate RG-like cells, Step2 identifies target mDA progenitor candidates, and Step3 scores developmental concordance with CLS components.

## Agent Install And Use (Recommended)

For a first-time install, send this to Claude Code, Codex, or a similar coding agent:

```text
Help me install https://github.com/starvingarc/BRIDGE
```

Then run the workflow through the repository-local skills:

| Skill | Invocation | Purpose |
| --- | --- | --- |
| `bridge-step0` | `/bridge-step0` or `@bridge-step0` | Initialize environment, model assets, config, and run directory. |
| `bridge-step1` | `/bridge-step1` or `@bridge-step1` | Prescreen one in vitro `.h5ad` dataset and produce RG candidate artifacts plus a Step1 report. |
| `bridge-step2` | `/bridge-step2` or `@bridge-step2` | Run mDA progenitor identity assessment and write a Step2 report. |
| `bridge-step3` | `/bridge-step3` or `@bridge-step3` | Run CLS components, single-dataset reports, and optional multi-protocol comparison. |

Command names are lowercase for compatibility. The project brand remains **BRIDGE**. Full copy-paste demo prompts are in [docs/agent_demo.md](docs/agent_demo.md). Model assets are fetched separately from public object-storage URLs declared in [models/assets.json](models/assets.json).

## Manual Install And Use

Install from GitHub or from a local checkout:

```bash
pip install git+https://github.com/starvingarc/BRIDGE.git
# or, from a cloned source tree:
pip install -e ".[workflow]"
```

Notebook-callable entry points:

```python
import scanpy as sc

from bridge.prescreen import prescreen
from bridge.identity import identify
from bridge.cls import CLSContext, component_A, component_B, component_C, component_D, component_E, component_F, score

from bridge.prescreen.report import write_report as write_prescreen_report
from bridge.identity.report import write_report as write_identity_report
from bridge.cls.report import write_report as write_cls_report, compare_reports
```

The high-level manual notebook flow is:

```python
step1 = prescreen(adata, ref_model_dir="./models/whole_brain_ref_model", output_dir="./runs/demo_dataset/step1", prefix="demo_dataset")
write_prescreen_report(result=step1, output_dir="./runs/demo_dataset/step1/report", prefix="demo_dataset")

adata_ref = sc.read_h5ad("./models/target_reference.h5ad")
step2 = identify(
    bdata_rg, adata_ref, ref_model_dir="./models/target_ref_model",
    target_class="RG_Mesencephalon_FP", output_dir="./runs/demo_dataset/step2", prefix="demo_dataset",
    reference_h5ad_path="./models/target_reference.h5ad",
)
write_identity_report(result=step2, output_dir="./runs/demo_dataset/step2/report", prefix="demo_dataset", target_class="RG_Mesencephalon_FP")

ctx = CLSContext(
    bdata=step2.bdata,
    adata_ref=step2.adata_ref,
    target_class="RG_Mesencephalon_FP",
    output_dir="./runs/demo_dataset/step3",
    dataset_id="demo_dataset",
    probs_ref_cal=step2.probabilities.probs_ref_cal,
)

# Each CLS component is callable on its own when debugging or customizing the analysis.
# a = component_A(ctx)
# b = component_B(ctx)
# c = component_C(ctx)
# d = component_D(ctx)
# e = component_E(ctx)
# f = component_F(ctx)

# For the default reportable A-F run, call score(ctx).
cls_result = score(ctx)
write_cls_report(result=cls_result, ctx=ctx, output_dir="./runs/demo_dataset/step3/report", prefix="demo_dataset")
```

## Documentation

- [Agent demo script](docs/agent_demo.md): full video/demo flow.
- [Skills](docs/skills.md): repository-local Step0-Step3 skill interface.
- [Formal workflows](docs/formal_workflows.md): package surface and artifact contracts.
- [Thesis-to-code mapping](docs/thesis_to_code.md): how the thesis workflow maps to the repository.
- [Roadmap](docs/roadmap.md): model assets, notebooks, report polish, and future extensions.

## Repository Map

```text
src/bridge/        Python package
configs/           public config templates
models/            model metadata and model-asset entry point
notebooks/         placeholder area for formal notebook examples
docs/              detailed workflow and roadmap documentation
.claude/skills/    repository-local Step0-Step3 skills
```
