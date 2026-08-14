from pathlib import Path

from app.discovery.file_classifier import (
    FileCategory,
    FileClassifier,
)

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)


definitions = ClassificationDefinitions(
    Path(__file__).parent
    / "classification"
    / "definitions.json"
)

classifier = FileClassifier(
    definitions
)


tests = [
    ("src/main.py", "Python", False),
    ("tests/test_main.py", "Python", False),
    ("README.md", "Markdown", False),
    ("package.json", "JSON", False),
    ("dist/app.js", "JavaScript", False),
    ("__pycache__/main.pyc", None, False),
    ("logo.png", None, True),
]


for path, language, binary in tests:

    result = classifier.classify(
        Path(path),
        language,
        binary,
    )

    print(
        f"{path:30} -> {result.value}"
    )