from pathlib import Path

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)
from app.discovery.file_classifier import FileClassifier
from app.discovery.ignore import IgnoreRules
from app.discovery.repository_analyzer import RepositoryAnalyzer
from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.framework_detector import FrameworkDetector
from app.discovery.repository_builder import RepositoryBuilder

from app.ingestion.models import Repository
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)
from app.ingestion.repository_ingestor import RepositoryIngestor


def test_discovery_pipeline(tmp_path):

    # Create a small repository
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "dist").mkdir()

    (tmp_path / "src" / "main.py").write_text(
        "print('hello')"
    )

    (tmp_path / "tests" / "test_main.py").write_text(
        "def test_main(): pass"
    )

    (tmp_path / "docs" / "README.md").write_text(
        "# Test repository"
    )

    (tmp_path / "dist" / "app.js").write_text(
        "console.log('built')"
    )

    (tmp_path / "package.json").write_text(
        '''
        {
            "name": "test-project",
            "dependencies": {
                "react": "^19.0.0"
            }
        }
        '''
    )

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(tmp_path),
    )

    ingestor = RepositoryIngestor()

    repository = ingestor.ingest(source=source)

    definitions = ClassificationDefinitions(
        Path(__file__).parent.parent
        / "classification"
        / "definitions.json"
    )

    classifier = FileClassifier(definitions)

    scanner = RepositoryScanner(
        ignore_rules=IgnoreRules(root=tmp_path),
        file_classifier=classifier,
    )

    files, directories = scanner.scan(repository)

    base_path = Path(__file__).parent.parent

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

    assert result.name == repository.name
    assert result.path == repository.path

    assert result.metadata is not None

    assert result.metadata.total_files == 5

    assert result.metadata.source_files == 1
    assert result.metadata.test_files == 1
    assert result.metadata.documentation_files == 1
    assert result.metadata.build_files == 1
    assert result.metadata.configuration_files == 1

    assert result.languages == result.metadata.languages

    assert "Python" in result.languages
    assert "JavaScript" in result.languages
    assert "Markdown" in result.languages

    assert "React" in result.frameworks