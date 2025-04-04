#!/usr/bin/env python3
"""Clean pytest cache files and directories."""

import os
import shutil
from pathlib import Path
from typing import List, Optional


def clean_pytest_cache(root_dir: Optional[Path] = None) -> List[Path]:
    """
    Remove all pytest cache files and directories in the project.

    Args:
        root_dir: Root directory to start searching from (defaults to current directory)

    Returns:
        List of paths that were removed
    """
    root_dir = root_dir or Path.cwd()
    removed_paths: List[Path] = []

    # Find and remove .pytest_cache directories
    for path in root_dir.rglob(".pytest_cache"):
        if path.is_dir():
            shutil.rmtree(path)
            removed_paths.append(path)

    # Find and remove .coverage files
    for path in root_dir.rglob(".coverage*"):
        if path.is_file():
            os.remove(path)
            removed_paths.append(path)

    return removed_paths


if __name__ == "__main__":
    removed = clean_pytest_cache()
    print(f"Cleaned {len(removed)} pytest cache files/directories:")
    for path in removed:
        print(f"  - {path}")
