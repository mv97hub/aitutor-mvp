"""The three seeded courses are gone. The tutor does not ship a syllabus file."""

from pathlib import Path


def test_seeded_course_modules_are_gone() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "curriculum"
    assert not (root / "rome.py").exists()
    assert not (root / "geometry.py").exists()
    assert not (root / "macro.py").exists()
    assert not (root / "shape.py").exists()


def test_one_course_revision_drops_only_the_three_seeded_codes() -> None:
    text = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "014_one_course_model.py"
    ).read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "SEEDED = (\"rome\", \"geometry\", \"macro\")" in text
    assert "_delete_seeded_courses()" in upgrade
    assert "DELETE FROM sessions WHERE id IN" in text
    assert "DELETE FROM messages WHERE session_id IN" in text
    assert "DELETE FROM courses WHERE code IN" in text
    bare = [line.strip() for line in text.splitlines() if line.strip() == "DELETE FROM sessions"]
    assert bare == []
