from pathlib import Path
import tempfile

from app.discovery.repository_builder import (
    RepositoryBuilder,
)

from app.discovery.repository_analyzer import (
    RepositoryAnalyzer,
)

from app.ingestion.repository_ingestor import RepositoryIngestor
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)

from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.ignore import IgnoreRules


from app.discovery.framework_detector import (
    FrameworkDetector,
)

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)
from app.discovery.file_classifier import FileClassifier

test_root = Path(
    tempfile.mkdtemp(
        prefix="aaip_classification_"
    )
)

(test_root / "src").mkdir()
(test_root / "tests").mkdir()
(test_root / "dist").mkdir()
(test_root / "__pycache__").mkdir()
(test_root / "docs").mkdir()

(test_root / "src" / "main.py").write_text(
    "print('hello')",
    encoding="utf-8",
)

(test_root / "tests" / "test_main.py").write_text(
    "def test_main(): pass",
    encoding="utf-8",
)

(test_root / "dist" / "app.js").write_text(
    "console.log('build')",
    encoding="utf-8",
)

(test_root / "__pycache__" / "main.pyc").write_bytes(
    b"\x00\x01\x02"
)

(test_root / "docs" / "README.md").write_text(
    "# Documentation",
    encoding="utf-8",
)


definitions = ClassificationDefinitions(
    Path(__file__).parent
    / "classification"
    / "definitions.json"
)

classifier = FileClassifier(
    definitions
)

source = RepositorySource(
    source_type=RepositorySourceType.LOCAL,
    location=test_root,
)

ingestor = RepositoryIngestor()

repository = ingestor.ingest(source)

ignore_rules = IgnoreRules(root=repository.path)

scanner = RepositoryScanner(ignore_rules=ignore_rules,file_classifier=classifier)

files, directories = scanner.scan(repository)




base_path = Path(__file__).parent


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

print(result)