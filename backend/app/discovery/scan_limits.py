from dataclasses import dataclass


@dataclass(frozen=True)
class ScanLimits:
    max_file_size: int | None = None
    max_files: int | None = None
    max_directories: int | None = None
    max_total_size: int | None = None