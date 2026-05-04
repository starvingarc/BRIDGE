from __future__ import annotations

from pathlib import Path

def test_step_skills_require_notebook_visible_report_sections():
    root = Path(__file__).resolve().parents[1]
    for skill in ["bridge-step1", "bridge-step2", "bridge-step3"]:
        text = (root / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "notebook-visible" in text
        assert "display each table" in text
        assert "display each figure" in text
        assert "interpretation" in text


def test_step1_skill_requires_direct_input_when_readable():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".claude" / "skills" / "bridge-step1" / "SKILL.md").read_text(encoding="utf-8")
    assert "use the user-provided path directly" in text
    assert "do not create or reuse a compatibility copy" in text


def test_step_skills_require_narrative_notebook_structure():
    root = Path(__file__).resolve().parents[1]
    required_phrases = [
        "Opening Markdown",
        "one table or one figure",
        "purpose/context",
        "display_matplotlib_figure",
        "biological interpretation",
        "Final Markdown summary",
        "Final artifact cell",
        "do not re-display every report artifact",
    ]
    for skill in ["bridge-step1", "bridge-step2", "bridge-step3"]:
        text = (root / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        for phrase in required_phrases:
            assert phrase in text, (skill, phrase)


def test_step3_skill_requires_different_protocol_comparison_guidance():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".claude" / "skills" / "bridge-step3" / "SKILL.md").read_text(encoding="utf-8")
    for phrase in [
        "SphereDiff (CSC 2025)",
        "MacroDiff (unpublished)",
        "MSK-DA01 (CSC 2021)",
        "Different-protocol comparison",
        "不同方案的对比报告",
        "component heatmap",
        "Component B",
        "plot_protocol_component_B_pseudobulk",
        "plot_protocol_component_F1_regulon_heatmap",
        "plot_protocol_component_F2_regulon_activity",
        "F1 regulon target overlap",
        "F2 regulon activity alignment",
    ]:
        assert phrase in text


def test_step1_skill_requires_explicit_umap_sections():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".claude" / "skills" / "bridge-step1" / "SKILL.md").read_text(encoding="utf-8")
    for phrase in [
        "plot_predicted_cell_type_umap",
        "plot_prediction_confidence_umap",
        "plot_cell_type_umap",
        "predicted identity UMAP",
        "prediction confidence UMAP",
        "one code cell per UMAP",
    ]:
        assert phrase in text
