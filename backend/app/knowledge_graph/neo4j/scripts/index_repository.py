from app.ingestion.repository_ingestor import RepositoryIngestor
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)

from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.repository_builder import RepositoryBuilder
from app.discovery.framework_detector import FrameworkDetector
from app.discovery.repository_analyzer import RepositoryAnalyzer

from app.parser.aaip_code_model.orchestrator import build_repository_graph
from app.knowledge_graph.neo4j.repository import Neo4jRepository
from app.discovery.ignore import IgnoreRules

ingestor = RepositoryIngestor()

source = RepositorySource(
    source_type=RepositorySourceType.LOCAL,
    location="/app/app/parser/aaip_code_model/tests/fixtures/normalization"
)

repository = ingestor.ingest(source)

ignore_rules = IgnoreRules(root=repository.path)

scanner = RepositoryScanner(ignore_rules=ignore_rules)
analyzer = RepositoryAnalyzer()
framework_detector = FrameworkDetector()
builder = RepositoryBuilder(analyzer, framework_detector)


files, directories = scanner.scan(repository)

discovered_repo = builder.build(
    name=repository.name,
    path=repository.path,
    files=files,
    directories=directories,
)

model = build_repository_graph(discovered_repo)

neo4j_repository = Neo4jRepository()
neo4j_repository.save(model)

print(f"Repository '{discovered_repo.name}' has been successfully indexed into Neo4j.")