from pathlib import Path

from app.parser.joern.client import JoernClient


def main():

    client = JoernClient()

    repository = Path(
        "joern_test_languages/javascript"
    )

    output = client.run_script(
        script_path=Path(
            "app/parser/joern/scripts/analyze.sc"
        ),
        repository=repository,
    )

    print(output)


if __name__ == "__main__":
    main()