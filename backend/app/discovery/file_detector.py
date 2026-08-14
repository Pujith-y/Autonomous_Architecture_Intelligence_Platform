from pathlib import Path


def is_binary_file(path: Path) -> bool:

    try:
        with path.open("rb") as f:
            chunk = f.read(8192)

    except OSError:
        return False

    if not chunk:
        return False

    return b"\x00" in chunk