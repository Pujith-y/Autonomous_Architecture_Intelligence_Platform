from dataclasses import dataclass
from pathlib import Path

from app.discovery.file_classifier import FileCategory


@dataclass
class DiscoveredFile:
    path: Path
    relative_path: Path
    name: str
    extension: str
    size: int
    is_hidden: bool
    is_symlink: bool
    is_binary: bool
    is_large: bool
    language: str | None
    category: FileCategory

@dataclass
class DiscoveredDirectory:
    path: Path
    relative_path: Path
    name: str
    is_hidden: bool