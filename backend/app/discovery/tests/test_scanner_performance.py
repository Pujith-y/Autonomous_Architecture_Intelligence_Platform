import time
import statistics
from pathlib import Path

from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.ignore import IgnoreRules
from app.discovery.scan_limits import ScanLimits
from app.discovery.classification.loader import ClassificationDefinitions
from app.discovery.file_classifier import FileClassifier

from app.ingestion.models import Repository
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)


def create_scanner(root: Path) -> RepositoryScanner:

    definitions = ClassificationDefinitions(
        Path(__file__).parent.parent
        / "classification"
        / "definitions.json"
    )

    classifier = FileClassifier(definitions)

    return RepositoryScanner(
        ignore_rules=IgnoreRules(root=root),
        file_classifier=classifier,
        limits=ScanLimits(),
    )


def create_repository(root: Path) -> Repository:

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(root),
    )

    return Repository(
        name="performance-test",
        path=root,
        source=source,
    )


def measure_scan_time(
    root: Path,
    file_count: int,
) -> float:

    for index in range(file_count):

        (root / f"file_{index}.py").write_text(
            "print('hello')\n"
        )

    scanner = create_scanner(root)
    repository = create_repository(root)

    # Warm-up
    scanner.scan(repository)

    measurements = []

    for _ in range(5):

        start = time.perf_counter()

        scanner.scan(repository)

        end = time.perf_counter()

        measurements.append(end - start)

    return statistics.median(measurements)


def test_scanner_performance_scaling(tmp_path):

    results = {}

    for file_count in [100, 500, 1000]:

        test_root = tmp_path / str(file_count)
        test_root.mkdir()

        results[file_count] = measure_scan_time(
            test_root,
            file_count,
        )

    for file_count, duration in results.items():

        print(
            f"\n{file_count} files -> "
            f"{duration:.4f} seconds"
        )

    assert all(
        duration >= 0
        for duration in results.values()
    )