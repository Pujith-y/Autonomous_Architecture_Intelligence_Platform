from app.discovery.models import (
    DiscoveredFile,
    DiscoveredDirectory,
)

from app.discovery.repository_analyzer import (
    RepositoryAnalyzer,
)

from app.discovery.framework_detector import (
    FrameworkDetector,
)

from app.discovery.repository_model import (
    RepositoryModel,
)


class RepositoryBuilder:

    def __init__(
        self,
        analyzer: RepositoryAnalyzer,
        framework_detector: FrameworkDetector,
    ):
        self.analyzer = analyzer
        self.framework_detector = framework_detector

    def build(
        self,
        name: str,
        path,
        files: list[DiscoveredFile],
        directories: list[DiscoveredDirectory],
    ) -> RepositoryModel:

        metadata = self.analyzer.analyze(
            files,
            directories,
        )

        frameworks = self.framework_detector.detect(
            files
        )

        return RepositoryModel(
            name=name,
            path=path,
            files=files,
            directories=directories,
            metadata=metadata,
            languages=metadata.languages,
            frameworks=frameworks,
        )