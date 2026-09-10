# BRIDGE

*Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation*

BRIDGE helps researchers inspect single-cell transcriptomic evidence from
cell-therapy products: what cell states are present, how they relate to an
intended product, and which questions the evidence still cannot answer.
The first use case is hPSC-derived midbrain dopaminergic products for
Parkinson's disease research.

## Questions to explore

- Which cell states are supported, uncertain or in conflict across sources?
- How do target identity, regional identity and development differ?
- What is the whole-product composition, including non-target and unknown cells?
- Which proliferation or stress observations are measured, and which need
  better inputs or scientific review?

Results retain their original values, denominators, limitations and source
versions. The interface separates tool findings from proposed explanations and
lets the researcher approve a finite analysis scope, stop it and inspect the
local evidence chain.

## Start with the private Web interface

Use Python 3.12 and Node.js 22.12 or newer:

~~~bash
git clone https://github.com/starvingarc/BRIDGE.git
cd BRIDGE
python -m pip install -e ".[qc,web,evidence,process]"
npm --prefix frontend ci
npm --prefix frontend run build
~~~

Follow the [private-instance configuration](docs/web-preview.md#start-a-private-instance)
before starting `python -m bridge.web`. There is no public hosted service
provided by this repository. In the interface, upload a sample, review and
confirm its experimental facts, approve applicable quality checks, then prepare
a bounded cell-state and product assessment. Missing scientific prerequisites
remain visible; approval does not supply them.

For direct tool use, see the [question-led tool guide](docs/tool-packages.md)
and [runnable examples](examples/README.md).

## Research limits

BRIDGE is a research tool, not a clinical decision or product-release system.
Current results do not establish safety, clinical efficacy, validated potency,
GMP release or an absolute product ranking. Missing or unavailable evidence is
never a zero measurement. Cell counts do not establish independent biological
replicates, and post-transplant evidence does not replace pre-transplant
assessment.

The connected interface and synthetic checks are engineering evidence, not
scientific qualification. Source-state, product-role, developmental-window,
program and biological-unit reviews remain necessary. Actual tested scope and
unverified gates are recorded in the [validation history](docs/validation/README.md).

[Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)
