import subprocess
from pathlib import Path


class JoernClient:

    def __init__(
        self,
        joern_command: str = "joern",
    ):
        self.joern_command = joern_command

    def run_script(
        self,
        script_path: Path,
        repository: Path,
    ) -> str:

        command = [
            self.joern_command,
            "--script",
            str(script_path),
            "--param",
            f"repository={repository}",
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:

            raise RuntimeError(
                "Joern execution failed:\n"
                + result.stderr
            )

        return result.stdout