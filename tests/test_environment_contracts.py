from __future__ import annotations

from pathlib import Path

import yaml

from bridge.tool_packages.p0_02_cell_state.freeze import RUNTIME_ENVIRONMENT_SPEC
from bridge.toolkit.registry import ToolRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: str) -> dict:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _pip_dependencies(spec: dict) -> list[str]:
    for dependency in spec["dependencies"]:
        if isinstance(dependency, dict) and "pip" in dependency:
            return dependency["pip"]
    return []


def _conda_dependencies(spec: dict) -> set[str]:
    return {dependency for dependency in spec["dependencies"] if isinstance(dependency, str)}


def test_every_tool_environment_reference_resolves_to_conda_yaml() -> None:
    index = yaml.safe_load((REPO_ROOT / "environments" / "index.yaml").read_text(encoding="utf-8"))
    specs = index["environment_specs"]

    for tool in ToolRegistry.load_default().list():
        assert tool.environment_spec_id in specs
        conda_spec = yaml.safe_load(
            (REPO_ROOT / specs[tool.environment_spec_id]["yaml_ref"]).read_text(encoding="utf-8")
        )
        assert conda_spec["name"].startswith("bridge-")
        assert "python=3.12" in conda_spec["dependencies"]
        assert "prefix" not in conda_spec


def test_cell_state_release_runtime_matches_the_tool_runtime_environment() -> None:
    spec = ToolRegistry.load_default().describe("P0-02")
    assert RUNTIME_ENVIRONMENT_SPEC == spec.environment_spec_id


def test_cell_state_runtime_environment_includes_signature_verification() -> None:
    spec = _load_yaml("environments/bridge-p0-core.yml")
    assert "cryptography=46.0" in _conda_dependencies(spec)


def test_core_environment_pins_wheel_build_tooling() -> None:
    spec = _load_yaml("environments/bridge-p0-core.yml")
    assert {"setuptools=84.0.0", "wheel=0.47.0"} <= _conda_dependencies(spec)


def test_active_environment_contracts_do_not_name_machine_local_environments() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "environments").glob("*"))
        if path.is_file()
    )

    assert "name: pytorch" not in text
    assert "/data1/" not in text
    assert "/data2/" not in text
    assert "/Users/" not in text


def test_active_tool_docs_use_environment_specs_not_server_environment_names() -> None:
    docs = REPO_ROOT / "docs" / "bridge_spec_v0.1"
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(docs.glob("*.md")))

    assert "`pytorch`" not in text
    assert "`r4.3`" not in text
    assert "bridge-amax" not in text


def test_cell_state_python_environment_contract_is_pinned() -> None:
    index = _load_yaml("environments/index.yaml")["environment_specs"]
    entry = index["ENV-CELLSTATE-PY-v0.1"]
    spec = _load_yaml(entry["yaml_ref"])

    assert entry["conda_name"] == spec["name"] == "bridge-cellstate-py"
    assert entry["state"] == "health_check_passed"
    assert spec["channels"] == ["conda-forge", "bioconda", "nodefaults"]
    assert {
        "python=3.12",
        "numpy=2.2.6",
        "pandas=2.3.3",
        "scipy=1.16.3",
        "pydantic=2.12.5",
        "pyyaml=6.0.3",
        "h5py=3.15.1",
        "anndata=0.12.6",
        "scanpy=1.11.5",
        "pyarrow=21.0.0",
        "scikit-learn=1.7.2",
    } <= _conda_dependencies(spec)
    assert {
        "celltypist==1.7.1",
        "scvi-tools==1.4.0.post1",
        "decoupler==2.1.4",
        "torch==2.9.1",
        "cryptography==46.0.3",
        "cffi==2.0.0",
        "pycparser==2.23",
    } <= set(_pip_dependencies(spec))


def test_cell_state_bioconductor_environment_contract_is_health_checked_and_pinned() -> None:
    index = _load_yaml("environments/index.yaml")["environment_specs"]
    entry = index["ENV-CELLSTATE-BIOC-R46-v0.1"]
    spec = _load_yaml(entry["yaml_ref"])

    assert entry["conda_name"] == spec["name"] == "bridge-cellstate-bioc-r46"
    assert entry["state"] == "health_check_passed"
    assert spec["channels"] == ["conda-forge", "bioconda", "nodefaults"]
    assert {
        "r-base=4.6",
        "git",
        "make",
        "c-compiler",
        "cxx-compiler",
        "cmake=4.4.2",
        "libxml2=2.15.1",
        "libxml2-devel=2.15.1",
        "liblzma-devel=5.8.1",
        "xz=5.8.1",
        "zlib=1.3.2",
    } <= _conda_dependencies(spec)
    assert spec["variables"] == {
        "BRIDGE_BIOC_VERSION": "3.23",
        "BRIDGE_BIOCMANAGER_VERSION": "1.30.27",
        "BRIDGE_REMOTES_VERSION": "2.5.0",
        "BRIDGE_DIGEST_VERSION": "0.6.39",
        "BRIDGE_SINGLER_VERSION": "2.14.1",
        "BRIDGE_SCMAP_VERSION": "1.34.0",
        "BRIDGE_SCCONFORM_VERSION": "1.0.0",
        "BRIDGE_UCELL_VERSION": "2.16.0",
        "BRIDGE_IGRAPH_VERSION": "2.3.3",
        "BRIDGE_HARMONY_COMMIT": "df19af23ae0639bd6ea2da63898f973f08c85862",
        "BRIDGE_SYMPHONY_COMMIT": "7c5905988734d9cfe6e1e97a658664717c4ba7b7",
    }


def test_cell_state_r_post_create_is_pinned_without_a_separate_symphony_environment() -> None:
    readme = (REPO_ROOT / "environments" / "README.md").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "environments" / "install-cellstate-bioc-r46.R").read_text(encoding="utf-8")
    index = _load_yaml("environments/index.yaml")["environment_specs"]

    assert 'install-cellstate-bioc-r46.R' in readme
    assert 'immunogenomics/harmony' in installer
    assert 'ref = Sys.getenv("BRIDGE_HARMONY_COMMIT")' in installer
    assert 'immunogenomics/symphony' in installer
    assert 'ref = Sys.getenv("BRIDGE_SYMPHONY_COMMIT")' in installer
    assert 'as.character(BiocManager::version()) != Sys.getenv("BRIDGE_BIOC_VERSION")' in installer
    assert 'Ncpus = 1L' in installer
    assert 'BRIDGE_HARMONY_ARCHIVE' in installer
    assert 'BRIDGE_SYMPHONY_ARCHIVE' in installer
    assert 'BRIDGE_SCCONFORM_ARCHIVE' in installer
    assert '"rhdf5"' in installer
    assert 'packageVersion(package)' in installer
    assert not any("SYMPHONY" in spec_id for spec_id in index)
