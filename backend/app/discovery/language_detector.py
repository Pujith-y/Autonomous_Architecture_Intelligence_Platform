from pathlib import Path

from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound


class LanguageDetector:

    def detect(self, path: Path) -> str | None:
        try:
            lexer = get_lexer_for_filename(path.name)

        except ClassNotFound:
            return None

        return lexer.name