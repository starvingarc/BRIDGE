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
