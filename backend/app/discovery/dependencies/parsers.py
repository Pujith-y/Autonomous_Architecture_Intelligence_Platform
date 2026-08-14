import json
import re
import tomllib
import xml.etree.ElementTree as ET

from pathlib import Path


class ManifestParsers:

    @staticmethod
    def json(path: Path) -> set[str]:

        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return set()

        dependencies = set()

        for section in (
            "dependencies",
            "devDependencies",
            "peerDependencies",
            "optionalDependencies",
        ):

            dependencies.update(
                data.get(section, {}).keys()
            )

        return {
            dependency.lower()
            for dependency in dependencies
        }

    @staticmethod
    def pyproject(path: Path) -> set[str]:

        try:
            data = tomllib.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            tomllib.TOMLDecodeError,
        ):
            return set()

        dependencies = set()

        project = data.get(
            "project",
            {}
        )

        for dependency in project.get(
            "dependencies",
            []
        ):

            dependencies.add(
                ManifestParsers._normalize_python(
                    dependency
                )
            )

        return dependencies

    @staticmethod
    def requirements(path: Path) -> set[str]:

        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            return set()

        dependencies = set()

        for line in lines:

            line = line.strip()

            if (
                not line
                or line.startswith("#")
            ):
                continue

            if line.startswith("-r"):
                continue

            dependencies.add(
                ManifestParsers._normalize_python(
                    line
                )
            )

        return dependencies

    @staticmethod
    def maven(path: Path) -> set[str]:

        try:
            root = ET.parse(path).getroot()
        except (
            OSError,
            ET.ParseError,
        ):
            return set()

        dependencies = set()

        for element in root.iter():

            if element.tag.endswith(
                "artifactId"
            ):

                if element.text:
                    dependencies.add(
                        element.text.strip().lower()
                    )

        return dependencies

    @staticmethod
    def gradle(path: Path) -> set[str]:

        try:
            content = path.read_text(
                encoding="utf-8"
            ).lower()
        except OSError:
            return set()

        dependencies = set()

        patterns = [
            r'implementation\s+["\']([^"\']+)',
            r'api\s+["\']([^"\']+)',
            r'compileOnly\s+["\']([^"\']+)',
            r'runtimeOnly\s+["\']([^"\']+)',
            r'testImplementation\s+["\']([^"\']+)',
        ]

        for pattern in patterns:

            matches = re.findall(
                pattern,
                content,
            )

            for match in matches:

                parts = match.split(":")

                if len(parts) >= 2:
                    dependencies.add(
                        parts[-2]
                    )

        return dependencies

    @staticmethod
    def cargo(path: Path) -> set[str]:

        try:
            data = tomllib.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            tomllib.TOMLDecodeError,
        ):
            return set()

        dependencies = data.get(
            "dependencies",
            {}
        )

        return {
            name.lower()
            for name in dependencies
        }

    @staticmethod
    def gomod(path: Path) -> set[str]:

        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            return set()

        dependencies = set()

        inside_block = False

        for line in lines:

            line = line.strip()

            if line == "require (":
                inside_block = True
                continue

            if inside_block and line == ")":
                inside_block = False
                continue

            if inside_block:

                parts = line.split()

                if parts:
                    dependencies.add(
                        parts[0].lower()
                    )

        return dependencies

    @staticmethod
    def _normalize_python(
        dependency: str
    ) -> str:

        dependency = dependency.strip()

        dependency = dependency.split(
            "[",
            1
        )[0]

        dependency = re.split(
            r"[<>=!~]",
            dependency,
            maxsplit=1,
        )[0]

        return dependency.strip().lower()