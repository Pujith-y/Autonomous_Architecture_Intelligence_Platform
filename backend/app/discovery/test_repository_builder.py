from pathlib import Path

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

source = RepositorySource(
    source_type=RepositorySourceType.GIT,
    location="https://github.com/Pujith-y/portfolio",
    branch="main",
    shallow=True,
)

ingestor = RepositoryIngestor()

repository = ingestor.ingest(source)

ignore_rules = IgnoreRules(root=repository.path)

scanner = RepositoryScanner(ignore_rules=ignore_rules)

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