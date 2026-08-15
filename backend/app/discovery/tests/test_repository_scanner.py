from pathlib import Path

from app.discovery.repository_scanner import RepositoryScanner
from app.discovery.ignore import IgnoreRules

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)

from app.discovery.file_classifier import FileClassifier

from app.ingestion.models import Repository
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)


def test_scanner_handles_walk_errors(
    tmp_path,
    monkeypatch,
):

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(tmp_path),
    )

    repository = Repository(
        name="permission-test",
        path=tmp_path,
        source=source,
    )

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

    def fake_walk(
        root,
        followlinks=False,
        onerror=None,
    ):
        if onerror:
            onerror(
                PermissionError("permission denied")
            )

        return

        yield

    monkeypatch.setattr(
        "app.discovery.repository_scanner.os.walk",
        fake_walk,
    )

    files, directories = scanner.scan(repository)

    assert files == []
    assert directories == []

def test_scanner_does_not_follow_symlink_directories(
        tmp_path,
):
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    (source_dir / "main.py").write_text(
        "print('hello')"
    )

    link = tmp_path / "linked_src"

    try:
        link.symlink_to(
            source_dir,
            target_is_directory=True,
        )
    except OSError:
        import pytest

        pytest.skip(
            "Symlink creation is not supported"
        )

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(tmp_path),
    )

    repository = Repository(
        name="symlink-test",
        path=tmp_path,
        source=source,
    )

    definitions = ClassificationDefinitions(
        Path(__file__).parent.parent
        / "classification"
        / "definitions.json"
    )

    classifier = FileClassifier(definitions)

    scanner = RepositoryScanner(
        ignore_rules=IgnoreRules(root=tmp_path),
        file_classifier=classifier,
        follow_symlinks=False,
    )

    files, directories = scanner.scan(repository)

    relative_files = {
        file.relative_path
        for file in files
    }

    assert Path("src/main.py") in relative_files
    assert Path("linked_src/main.py") not in relative_files

def test_scanner_can_follow_symlink_directories(
    tmp_path,
):
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    (source_dir / "main.py").write_text(
        "print('hello')"
    )

    link = tmp_path / "linked_src"

    try:
        link.symlink_to(
            source_dir,
            target_is_directory=True,
        )
    except OSError:
        import pytest

        pytest.skip(
            "Symlink creation is not supported"
        )

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(tmp_path),
    )

    repository = Repository(
        name="symlink-follow-test",
        path=tmp_path,
        source=source,
    )

    definitions = ClassificationDefinitions(
        Path(__file__).parent.parent
        / "classification"
        / "definitions.json"
    )

    classifier = FileClassifier(definitions)

    scanner = RepositoryScanner(
        ignore_rules=IgnoreRules(root=tmp_path),
        file_classifier=classifier,
        follow_symlinks=True,
    )

    files, directories = scanner.scan(repository)

    relative_files = {
        file.relative_path
        for file in files
    }

    assert Path("src/main.py") in relative_files
    assert Path("linked_src/main.py") in relative_files

def test_scanner_handles_symlink_cycle(
    tmp_path,
):
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    (source_dir / "main.py").write_text(
        "print('hello')"
    )

    loop = source_dir / "loop"

    try:
        loop.symlink_to(
            tmp_path,
            target_is_directory=True,
        )
    except OSError:
        import pytest

        pytest.skip(
            "Symlink creation is not supported"
        )

    source = RepositorySource(
        source_type=RepositorySourceType.LOCAL,
        location=str(tmp_path),
    )

    repository = Repository(
        name="cycle-test",
        path=tmp_path,
        source=source,
    )

    definitions = ClassificationDefinitions(
        Path(__file__).parent.parent
        / "classification"
        / "definitions.json"
    )

    classifier = FileClassifier(definitions)

    scanner = RepositoryScanner(
        ignore_rules=IgnoreRules(root=tmp_path),
        file_classifier=classifier,
        follow_symlinks=True,
    )

    files, directories = scanner.scan(repository)

    relative_files = {
        file.relative_path
        for file in files
    }

    assert Path("src/main.py") in relative_files