from pathlib import Path

from app.parser.joern.client import JoernClient


def main():

    joern = JoernClient()

    script_path = Path(
        "app/parser/joern/scripts/analyze.sc"
    )

    repository_path = Path(
        "app/parser/joern/tests/fixtures/python"
    )

    result = joern.run_script(
        script_path=script_path,
        repository=repository_path
    )

    print(result)


if __name__ == "__main__":
    main()