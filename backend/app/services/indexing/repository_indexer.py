from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.repository_model import Repository
from app.models.indexing_run_model import IndexingRun
from app.models.repository_status import RepositoryStatus
from app.models.indexing_status import IndexingStatus

from app.ingestion.repository_ingestor import RepositoryIngestor
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)

from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.repository_builder import RepositoryBuilder
from app.discovery.framework_detector import FrameworkDetector
from app.discovery.repository_analyzer import RepositoryAnalyzer
from app.discovery.ignore import IgnoreRules

from app.parser.aaip_code_model.orchestrator import (
    build_repository_graph,
)

from app.knowledge_graph.neo4j.repository import (
    Neo4jRepository,
)


class RepositoryIndexer:

    def __init__(self):
        self.ingestor = RepositoryIngestor()

        self.builder = RepositoryBuilder(
            analyzer=RepositoryAnalyzer(),
            framework_detector=FrameworkDetector(),
        )

        self.neo4j_repository = Neo4jRepository()

    def index(
        self,
        repository: Repository,
        db: Session,
    ) -> IndexingRun:

        run = IndexingRun(
            repository_id=repository.id,
            status=IndexingStatus.INDEXING,
            started_at=datetime.utcnow(),
        )

        repository.status = RepositoryStatus.INDEXING

        db.add(run)
        db.commit()
        db.refresh(run)

        try:
            self._run_pipeline(
                repository,
            )

            run.status = IndexingStatus.COMPLETED
            run.completed_at = datetime.utcnow()

            repository.status = RepositoryStatus.READY
            repository.last_indexed_at = datetime.utcnow()

            db.commit()

            return run

        except Exception as e:

            run.status = IndexingStatus.FAILED
            run.completed_at = datetime.utcnow()
            run.error_message = str(e)

            repository.status = RepositoryStatus.FAILED

            db.commit()

            raise

    def _run_pipeline(
        self,
        repository: Repository,
    ) -> None:

        source = RepositorySource(
            source_type=RepositorySourceType.LOCAL,
            location=repository.path,
        )

        discovered_repository = self.ingestor.ingest(
            source
        )

        scanner = RepositoryScanner(
            ignore_rules=IgnoreRules(discovered_repository.path),
        )

        files, directories = scanner.scan(
            discovered_repository
        )

        discovered_repo = self.builder.build(
            name=discovered_repository.name,
            path=discovered_repository.path,
            files=files,
            directories=directories,
        )

        model = build_repository_graph(
            discovered_repo
        )

        self.neo4j_repository.save(
            model,
            user_id=repository.us er_id,
            repository_id=repository.id,
        )