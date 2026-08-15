from pathlib import Path

from app.discovery.language_detector import LanguageDetector


def test_detects_python():

    detector = LanguageDetector()

    assert detector.detect(
        Path("main.py")
    ) == "Python"


def test_detects_javascript():

    detector = LanguageDetector()

    assert detector.detect(
        Path("app.js")
    ) == "JavaScript"


def test_detects_jsx():

    detector = LanguageDetector()

    assert detector.detect(
        Path("App.jsx")
    ) == "JSX"


def test_detects_filename_based_language():

    detector = LanguageDetector()

    assert detector.detect(
        Path("Dockerfile")
    ) == "Docker"


def test_unknown_filename_returns_none():

    detector = LanguageDetector()

    assert detector.detect(
        Path("something.zzzzunknown")
    ) is None