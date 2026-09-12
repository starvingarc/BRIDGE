<h1 align="center">BRIDGE</h1>

<p align="center">
  <strong>A research agent for single-cell evidence in cell-therapy products.</strong>
</p>

<p align="center">
  <a href="https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml"><img src="https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml/badge.svg?branch=main" alt="Repository CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2E7B70" alt="MIT license"></a>
  <a href="docs/product-principles.md"><img src="https://img.shields.io/badge/use-research_only-7867A6" alt="Research use only"></a>
</p>

<p align="center">
  <a href="#get-started"><strong>Get started</strong></a> &nbsp;·&nbsp;
  <a href="examples/README.md#synthetic-scrna-upload-demo">Try the sample data</a> &nbsp;·&nbsp;
  <a href="docs/README.md">Documentation</a> &nbsp;·&nbsp;
  <a href="docs/validation/README.md">Validation</a>
</p>

---

BRIDGE helps researchers explore cell states in cell-therapy products using
single-cell data. The first use case is **hPSC-derived midbrain dopaminergic
products for Parkinson's disease research**.

<p align="center">
  <a href="docs/assets/bridge-biological-workflow.svg"><img src="docs/assets/bridge-biological-workflow.svg" width="100%" alt="Conceptual evidence map: developmental references and a cell product inform identity, regional fidelity, development, composition, and proliferation and stress response, with traceable evidence outputs."></a>
</p>

<p align="center">
  <em>Conceptual overview of the research workflow.</em>
</p>

## Get started

Run BRIDGE as a **private, self-hosted Web application for one operator**.
Requires **Python 3.12** and **Node.js 22.12+**.

### 1. Install and build

```bash
git clone https://github.com/starvingarc/BRIDGE.git
cd BRIDGE

python -m pip install ".[qc,web,evidence,process]"
npm --prefix frontend ci
npm --prefix frontend run build
```

### 2. Configure your private instance

Follow the [setup guide](docs/web-preview.md#start-a-private-instance) to
configure private storage, operator authentication, a model provider and the
built frontend. Store credentials in private runtime configuration outside the
repository.

Start the service, then open the address you configured:

```bash
python -m bridge.web
```

### 3. Try the sample data

Explore the input format with the
[synthetic scRNA sample](examples/README.md#synthetic-scrna-upload-demo),
a small dataset for trying the upload interface and testing integrations.

For direct Python or CLI use, see the [tool guide](docs/tool-packages.md) and
[request examples](examples/README.md). Set the example paths and checksums
for your own files before running.

## Explore & contribute

[Documentation](docs/README.md) ·
[Scientific principles](docs/product-principles.md) ·
[Privacy & provenance](docs/privacy-and-provenance.md) ·
[Contributing](CONTRIBUTING.md) ·
[Issues](https://github.com/starvingarc/BRIDGE/issues)

---

<p align="center">
  <sub>Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation</sub><br>
  <sub>Open source under the <a href="LICENSE">MIT License</a>.</sub>
</p>
