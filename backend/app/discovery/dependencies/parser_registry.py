from collections.abc import Callable

from app.discovery.dependencies.parsers import ManifestParsers


class ParserRegistry:

    def __init__(self):
        self._parsers: dict[
            str,
            Callable
        ] = {}

        self._register_default_parsers()

    def _register_default_parsers(self):
        self.register(
            "json",
            ManifestParsers.json,
        )

        self.register(
            "pyproject",
            ManifestParsers.pyproject,
        )

        self.register(
            "requirements",
            ManifestParsers.requirements,
        )

        self.register(
            "maven",
            ManifestParsers.maven,
        )

        self.register(
            "gradle",
            ManifestParsers.gradle,
        )

        self.register(
            "cargo",
            ManifestParsers.cargo,
        )

        self.register(
            "gomod",
            ManifestParsers.gomod,
        )

    def register(
        self,
        name: str,
        parser: Callable,
    ):
        self._parsers[name] = parser

    def get(
        self,
        name: str,
    ) -> Callable | None:
        return self._parsers.get(name)