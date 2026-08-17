from pathlib import Path

import pytest

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)
from app.discovery.file_classifier import FileClassifier
from app.discovery.framework_detector import FrameworkDetector
from app.discovery.ignore import IgnoreRules
from app.discovery.repository_analyzer import RepositoryAnalyzer
from app.discovery.repository_builder import RepositoryBuilder
from app.discovery.repository_scanner import RepositoryScanner

from app.ingestion.repository_ingestor import RepositoryIngestor
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)


@pytest.mark.integration
def test_real_portfolio_repository():
    source = RepositorySource(
        source_type=RepositorySourceType.GIT,
        location="https://github.com/Pujith-y/portfolio",
        branch=None,  # Use the default branch
        shallow=True,
    )

    repository = RepositoryIngestor().ingest(
        source
    )

    base_path = Path(__file__).parent.parent

    classification_definitions = (
        ClassificationDefinitions(
            base_path
            / "classification"
            / "definitions.json"
        )
    )

    classifier = FileClassifier(
        classification_definitions
    )

    scanner = RepositoryScanner(
        ignore_rules=IgnoreRules(
            root=repository.path
        ),
        file_classifier=classifier,
    )

    files, directories = scanner.scan(
        repository
    )

    framework_detector = FrameworkDetector(
        manifest_definitions=(
            base_path
            / "dependencies"
            / "definitions.json"
        ),
        framework_definitions=(
            base_path
            / "frameworks"
            / "definitions.json"
        ),
    )

    builder = RepositoryBuilder(
        analyzer=RepositoryAnalyzer(),
        framework_detector=framework_detector,
    )

    result = builder.build(
        name=repository.name,
        path=repository.path,
        files=files,
        directories=directories,
    )

    # Basic repository discovery
    assert result.name
    assert result.path.exists()

    # Discovery results
    assert result.files
    assert result.metadata is not None

    # Metadata consistency
    assert result.metadata.total_files == len(
        result.files
    )

    assert result.metadata.total_directories == len(
        result.directories
    )

    # Language detection
    assert result.languages

    # Framework detection
    assert result.frameworks

    print("\nREAL REPOSITORY RESULT")
    print("Name:", result.name)
    print("Path:", result.path)
    print("Files:", result.metadata.total_files)
    print(
        "Directories:",
        result.metadata.total_directories,
    )
    print(
        "Languages:",
        result.languages,
    )
    print(
        "Frameworks:",
        result.frameworks,
    )