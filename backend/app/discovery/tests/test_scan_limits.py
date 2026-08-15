from pathlib import Path

from app.discovery.scan_limits import ScanLimits
from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.ignore import IgnoreRules
from app.discovery.classification.loader import ClassificationDefinitions
from app.discovery.file_classifier import FileClassifier

from app.ingestion.models import Repository
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)


def create_repository(root: Path) -> Repository:

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(root),
    )

    return Repository(
        name="limit-test",
        path=root,
        source=source,
    )

def create_scanner(root: Path, limits: ScanLimits) -> RepositoryScanner:

    definitions = ClassificationDefinitions(
        Path(__file__).parent.parent
        / "classification"
        / "definitions.json"
    )

    classifier = FileClassifier(definitions)

    return RepositoryScanner(
        ignore_rules=IgnoreRules(root=root),
        file_classifier=classifier,
        limits=limits,
    )

def test_scan_limits_can_limit_files():
    limits = ScanLimits(
        max_files=10,
    )

    assert limits.max_files == 10
    assert limits.max_directories is None
    assert limits.max_total_size is None

def test_scanner_respects_max_files(tmp_path):

    (tmp_path / "one.py").write_text(
        "print('one')"
    )

    (tmp_path / "two.py").write_text(
        "print('two')"
    )

    (tmp_path / "three.py").write_text(
        "print('three')"
    )

    scanner = create_scanner(
        tmp_path,
        ScanLimits(max_files=2),
    )

    files, directories = scanner.scan(
        create_repository(tmp_path)
    )

    assert len(files) == 2

def test_scanner_respects_max_directories(tmp_path):

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()

    scanner = create_scanner(
        tmp_path,
        ScanLimits(max_directories=2),
    )

    files, directories = scanner.scan(
        create_repository(tmp_path)
    )

    assert len(directories) == 2

def test_scanner_respects_max_total_size(tmp_path):

    (tmp_path / "one.py").write_text(
        "a" * 100
    )

    (tmp_path / "two.py").write_text(
        "b" * 100
    )

    (tmp_path / "three.py").write_text(
        "c" * 100
    )

    scanner = create_scanner(
        tmp_path,
        ScanLimits(max_total_size=150),
    )

    files, directories = scanner.scan(
        create_repository(tmp_path)
    )

    assert len(files) <= 2

    assert sum(
        file.size
        for file in files
    ) <= 150

def test_scanner_marks_large_files_using_configured_limit(
    tmp_path,
):

    (tmp_path / "small.py").write_text(
        "a" * 50
    )

    (tmp_path / "large.py").write_text(
        "b" * 150
    )

    scanner = create_scanner(
        tmp_path,
        ScanLimits(max_file_size=100),
    )

    files, directories = scanner.scan(
        create_repository(tmp_path)
    )

    files_by_name = {
        file.name: file
        for file in files
    }

    assert files_by_name["small.py"].is_large is False
    assert files_by_name["large.py"].is_large is True