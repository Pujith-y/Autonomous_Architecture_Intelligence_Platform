from pathlib import Path

from app.knowledge_graph.semantic.source_extractor import SourceExtractor
from app.repository_model.entities import Entity
from app.repository_model.enums import EntityKind
from app.repository_model.locations import SourceLocation


def make_entity(
    root: Path,
    relative_path: str = "example.py",
    start_line: int = 2,
    end_line: int = 3,
) -> Entity:
    return Entity(
        id="test-function",
        kind=EntityKind.FUNCTION,
        name="example",
        location=SourceLocation(
            file=Path(relative_path),
            start_line=start_line,
            end_line=end_line,
        ),
        language="python",
    )


def test_extracts_exact_inclusive_line_range(tmp_path):
    (tmp_path / "example.py").write_text(
        "first\nsecond\nthird\nfourth\n",
        encoding="utf-8",
    )

    extractor = SourceExtractor(tmp_path)
    entity = make_entity(tmp_path)

    assert extractor.extract(entity) == "second\nthird\n"


def test_returns_none_without_location(tmp_path):
    entity = Entity(
        id="no-location",
        kind=EntityKind.FUNCTION,
        name="unknown",
    )

    assert SourceExtractor(tmp_path).extract(entity) is None


def test_returns_none_for_missing_file(tmp_path):
    extractor = SourceExtractor(tmp_path)
    entity = make_entity(tmp_path, relative_path="missing.py")

    assert extractor.extract(entity) is None


def test_returns_none_for_invalid_line_range(tmp_path):
    (tmp_path / "example.py").write_text("only one line\n", encoding="utf-8")

    extractor = SourceExtractor(tmp_path)
    entity = make_entity(tmp_path, start_line=2, end_line=3)

    assert extractor.extract(entity) is None


def test_rejects_path_outside_repository(tmp_path):
    extractor = SourceExtractor(tmp_path)
    entity = make_entity(tmp_path, relative_path="../outside.py")

    assert extractor.extract(entity) is None
