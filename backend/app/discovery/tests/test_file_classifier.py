from pathlib import Path

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)
from app.discovery.file_classifier import (
    FileCategory,
    FileClassifier,
)


DEFINITIONS_PATH = (
    Path(__file__).parent.parent
    / "classification"
    / "definitions.json"
)


def create_classifier() -> FileClassifier:
    definitions = ClassificationDefinitions(
        DEFINITIONS_PATH
    )

    return FileClassifier(definitions)


def test_source_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("src/main.py"),
        language="Python",
        is_binary=False,
    )

    assert result == FileCategory.SOURCE


def test_test_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("tests/test_main.py"),
        language="Python",
        is_binary=False,
    )

    assert result == FileCategory.TEST


def test_documentation_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("docs/README.md"),
        language="Markdown",
        is_binary=False,
    )

    assert result == FileCategory.DOCUMENTATION


def test_configuration_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("package.json"),
        language="JSON",
        is_binary=False,
    )

    assert result == FileCategory.CONFIGURATION


def test_build_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("dist/app.js"),
        language="JavaScript",
        is_binary=False,
    )

    assert result == FileCategory.BUILD


def test_generated_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("__pycache__/main.pyc"),
        language=None,
        is_binary=True,
    )

    assert result == FileCategory.GENERATED


def test_binary_asset():
    classifier = create_classifier()

    result = classifier.classify(
        Path("images/logo.png"),
        language=None,
        is_binary=True,
    )

    assert result == FileCategory.ASSET


def test_unknown_file():
    classifier = create_classifier()

    result = classifier.classify(
        Path("something.xyz"),
        language=None,
        is_binary=False,
    )

    assert result == FileCategory.UNKNOWN