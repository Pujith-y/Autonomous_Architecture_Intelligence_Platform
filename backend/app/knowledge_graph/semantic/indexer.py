from pathlib import Path

from app.knowledge_graph.semantic.document_builder import (
    SemanticDocument,
    SemanticDocumentBuilder,
)
from app.knowledge_graph.semantic.source_extractor import SourceExtractor
from app.repository_model.model import RepositoryModel


class SemanticIndexer:
    """Prepare repository entities for semantic indexing."""

    def __init__(
        self,
        source_extractor: SourceExtractor,
        document_builder: SemanticDocumentBuilder,
    ):
        self.source_extractor = source_extractor
        self.document_builder = document_builder

    @classmethod
    def for_repository(cls, repository_root: Path) -> "SemanticIndexer":
        return cls(
            source_extractor=SourceExtractor(repository_root),
            document_builder=SemanticDocumentBuilder(),
        )

    def build_documents(
        self,
        repository_model: RepositoryModel,
    ) -> list[SemanticDocument]:
        documents = []

        for entity in repository_model.entities:
            source_text = self.source_extractor.extract(entity)

            if source_text is None:
                continue

            document = self.document_builder.build(entity, source_text)

            if document is not None:
                documents.append(document)

        return documents
