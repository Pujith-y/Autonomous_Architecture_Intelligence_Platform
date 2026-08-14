from pathlib import Path

import pathspec


class IgnoreRules:

    def __init__(
        self,
        root: Path,
        custom_patterns: list[str] | None = None,
    ):
        self.root = root

        self.patterns = pathspec.PathSpec.from_lines(
            "gitignore",
            self._load_gitignore() + (custom_patterns or []),
        )

    def _load_gitignore(self) -> list[str]:
        gitignore = self.root / ".gitignore"

        patterns = [
            ".git",
            ".git/**",
        ]

        if gitignore.exists():
            patterns.extend(
                gitignore.read_text(
                    encoding="utf-8"
                ).splitlines()
            )

        return patterns

    def should_ignore(self, path: Path) -> bool:

        relative_path = path.relative_to(self.root)

        return self.patterns.match_file(
            relative_path.as_posix()
        )