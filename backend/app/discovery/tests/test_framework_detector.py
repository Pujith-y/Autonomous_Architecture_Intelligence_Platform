import json
from pathlib import Path

from app.discovery.dependencies.models import Dependency
from app.discovery.frameworks.matcher import FrameworkMatcher
from app.discovery.frameworks.registry import FrameworkRegistry
from app.discovery.framework_detector import FrameworkDetector
from app.discovery.models import DiscoveredFile
from app.discovery.file_classifier import FileCategory


def write_framework_definitions(
    path: Path,
    definitions: list[dict],
):
    path.write_text(
        json.dumps(definitions),
        encoding="utf-8",
    )


def test_detects_react(tmp_path):
    definitions_path = (
        tmp_path / "frameworks.json"
    )

    write_framework_definitions(
        definitions_path,
        [
            {
                "name": "React",
                "ecosystem": "javascript",
                "dependencies": ["react"],
                "dependency_prefixes": [],
            }
        ],
    )

    registry = FrameworkRegistry(
        definitions_path
    )

    dependencies = [
        Dependency(
            name="react",
            ecosystem="javascript",
            source_file="package.json",
        )
    ]

    result = FrameworkMatcher().match(
        dependencies=dependencies,
        definitions=registry.definitions,
    )

    assert result == ["React"]


def test_detects_fastapi(tmp_path):
    definitions_path = (
        tmp_path / "frameworks.json"
    )

    write_framework_definitions(
        definitions_path,
        [
            {
                "name": "FastAPI",
                "ecosystem": "python",
                "dependencies": ["fastapi"],
                "dependency_prefixes": [],
            }
        ],
    )

    registry = FrameworkRegistry(
        definitions_path
    )

    dependencies = [
        Dependency(
            name="fastapi",
            ecosystem="python",
            source_file="pyproject.toml",
        )
    ]

    result = FrameworkMatcher().match(
        dependencies=dependencies,
        definitions=registry.definitions,
    )

    assert result == ["FastAPI"]


def test_detects_framework_by_dependency_prefix(
    tmp_path,
):
    definitions_path = (
        tmp_path / "frameworks.json"
    )

    write_framework_definitions(
        definitions_path,
        [
            {
                "name": "Angular",
                "ecosystem": "javascript",
                "dependencies": [],
                "dependency_prefixes": [
                    "@angular/"
                ],
            }
        ],
    )

    registry = FrameworkRegistry(
        definitions_path
    )

    dependencies = [
        Dependency(
            name="@angular/core",
            ecosystem="javascript",
            source_file="package.json",
        )
    ]

    result = FrameworkMatcher().match(
        dependencies=dependencies,
        definitions=registry.definitions,
    )

    assert result == ["Angular"]


def test_does_not_match_wrong_ecosystem(
    tmp_path,
):
    definitions_path = (
        tmp_path / "frameworks.json"
    )

    write_framework_definitions(
        definitions_path,
        [
            {
                "name": "React",
                "ecosystem": "javascript",
                "dependencies": ["react"],
                "dependency_prefixes": [],
            }
        ],
    )

    registry = FrameworkRegistry(
        definitions_path
    )

    dependencies = [
        Dependency(
            name="react",
            ecosystem="python",
            source_file="requirements.txt",
        )
    ]

    result = FrameworkMatcher().match(
        dependencies=dependencies,
        definitions=registry.definitions,
    )

    assert result == []


def test_unknown_dependency_does_not_match(
    tmp_path,
):
    definitions_path = (
        tmp_path / "frameworks.json"
    )

    write_framework_definitions(
        definitions_path,
        [
            {
                "name": "React",
                "ecosystem": "javascript",
                "dependencies": ["react"],
                "dependency_prefixes": [],
            }
        ],
    )

    registry = FrameworkRegistry(
        definitions_path
    )

    dependencies = [
        Dependency(
            name="some-random-package",
            ecosystem="javascript",
            source_file="package.json",
        )
    ]

    result = FrameworkMatcher().match(
        dependencies=dependencies,
        definitions=registry.definitions,
    )

    assert result == []

def test_framework_detector_end_to_end(
    tmp_path,
):
    dependency_definitions = (
        tmp_path / "dependencies.json"
    )

    dependency_definitions.write_text(
        json.dumps(
            [
                {
                    "filename": "package.json",
                    "ecosystem": "javascript",
                    "parser": "json",
                }
            ]
        ),
        encoding="utf-8",
    )

    framework_definitions = (
        tmp_path / "frameworks.json"
    )

    framework_definitions.write_text(
        json.dumps(
            [
                {
                    "name": "React",
                    "ecosystem": "javascript",
                    "dependencies": ["react"],
                    "dependency_prefixes": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    package_json = tmp_path / "package.json"

    package_json.write_text(
        json.dumps(
            {
                "dependencies": {
                    "react": "^19.0.0"
                }
            }
        ),
        encoding="utf-8",
    )

    detector = FrameworkDetector(
        manifest_definitions=dependency_definitions,
        framework_definitions=framework_definitions,
    )

    discovered_file = DiscoveredFile(
        path=package_json,
        relative_path=Path("package.json"),
        name="package.json",
        extension=".json",
        size=package_json.stat().st_size,
        is_hidden=False,
        is_symlink=False,
        is_binary=False,
        is_large=False,
        language="JSON",
        category=FileCategory.CONFIGURATION,
    )

    result = detector.detect(
        [
            discovered_file
        ]
    )

    assert result == ["React"]

def test_all_framework_definitions_are_detectable():
    definitions_path = (
        Path(__file__).parent.parent
        / "frameworks"
        / "definitions.json"
    )

    registry = FrameworkRegistry(
        definitions_path
    )

    matcher = FrameworkMatcher()

    for definition in registry.definitions:

        if definition.dependencies:
            dependency_name = next(
                iter(definition.dependencies)
            )

        elif definition.dependency_prefixes:
            dependency_name = (
                next(
                    iter(
                        definition.dependency_prefixes
                    )
                )
                + "example"
            )

        else:
            raise AssertionError(
                f"Framework '{definition.name}' "
                "has no dependencies or prefixes"
            )

        dependency = Dependency(
            name=dependency_name,
            ecosystem=definition.ecosystem,
            source_file="test-manifest",
        )

        result = matcher.match(
            dependencies=[dependency],
            definitions=[definition],
        )

        assert definition.name in result