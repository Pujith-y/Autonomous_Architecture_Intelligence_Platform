from pathlib import Path

from app.discovery.file_classifier import FileCategory
from app.discovery.models import (
    DiscoveredFile,
    DiscoveredDirectory,
)
from app.discovery.repository_analyzer import (
    RepositoryAnalyzer,
)


def make_file(
    name: str,
    category: FileCategory,
    language: str | None = None,
    binary: bool = False,
    large: bool = False,
    hidden: bool = False,
    symlink: bool = False,
) -> DiscoveredFile:

    path = Path(name)

    return DiscoveredFile(
        path=path,
        relative_path=path,
        name=path.name,
        extension=path.suffix,
        size=100,
        is_hidden=hidden,
        is_symlink=symlink,
        is_binary=binary,
        is_large=large,
        language=language,
        category=category,
    )


def test_repository_analyzer_counts_categories():

    files = [
        make_file(
            "main.py",
            FileCategory.SOURCE,
            language="Python",
        ),
        make_file(
            "test_main.py",
            FileCategory.TEST,
            language="Python",
        ),
        make_file(
            "README.md",
            FileCategory.DOCUMENTATION,
            language="Markdown",
        ),
        make_file(
            "package.json",
            FileCategory.CONFIGURATION,
            language="JSON",
        ),
        make_file(
            "dist/app.js",
            FileCategory.BUILD,
            language="JavaScript",
        ),
        make_file(
            "__pycache__/main.pyc",
            FileCategory.GENERATED,
            binary=True,
        ),
        make_file(
            "logo.png",
            FileCategory.ASSET,
            binary=True,
        ),
        make_file(
            "unknown.xyz",
            FileCategory.UNKNOWN,
        ),
    ]

    directories = [
        DiscoveredDirectory(
            path=Path("src"),
            relative_path=Path("src"),
            name="src",
            is_hidden=False,
        ),
        DiscoveredDirectory(
            path=Path("tests"),
            relative_path=Path("tests"),
            name="tests",
            is_hidden=False,
        ),
    ]

    analyzer = RepositoryAnalyzer()

    metadata = analyzer.analyze(
        files=files,
        directories=directories,
    )

    assert metadata.total_files == 8
    assert metadata.total_directories == 2

    assert metadata.source_files == 1
    assert metadata.test_files == 1
    assert metadata.documentation_files == 1
    assert metadata.configuration_files == 1
    assert metadata.build_files == 1
    assert metadata.generated_files == 1
    assert metadata.asset_files == 1
    assert metadata.unknown_files == 1

    assert metadata.binary_files == 2

    assert metadata.languages == {
        "Python": 2,
        "Markdown": 1,
        "JSON": 1,
        "JavaScript": 1,
    }