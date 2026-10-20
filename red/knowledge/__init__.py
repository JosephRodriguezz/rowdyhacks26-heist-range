"""Source-linked, scenario-independent study notes supplied to Red workers."""

from pathlib import Path


def load_lesson_notes() -> str:
    root = Path(__file__).parent
    names = (
        "investigation.md", "access_control.md", "sessions.md", "input_handling.md",
        "mass_assignment.md", "path_traversal.md", "workflow_bypass.md",
    )
    parts = [(root / name).read_text(encoding="utf-8") for name in names]
    return "\n\n".join(parts)
