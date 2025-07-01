# tests/conftest.py
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Generator

import pytest

# Import the hashing function from the application itself
from datamanager.core import hash_file

# The initial state of our manifest for testing
INITIAL_MANIFEST_DATA = [
    {
        "fileName": "core-dataset.sqlite",
        "latestVersion": "v1",
        "history": [
            {
                "version": "v1",
                "timestamp": "2025-06-30T10:00:00Z",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "r2_object_key": "core-dataset/v1-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.sqlite",
                "diffFromPrevious": None,
                "commit": "f4b8e7a",
            }
        ],
    }
]


@pytest.fixture
def test_repo(tmp_path: Path) -> Generator[Path, Any, None]:
    """
    Creates a temporary directory initialized as a Git repository,
    with a pre-populated and committed manifest.json and dummy sqlite files.
    The manifest hash is dynamically generated to match the created file.
    """
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    subprocess.run(["git", "init"], cwd=repo_path, check=True)

    # Create a valid, minimal SQLite DB for the 'old' file.
    old_db_path = repo_path / "old_data.sqlite"
    con = sqlite3.connect(old_db_path)
    con.execute("CREATE TABLE data (id INT)")
    con.commit()
    con.close()

    # Create a different 'new' database
    new_db_path = repo_path / "new_data.sqlite"
    con = sqlite3.connect(new_db_path)
    con.execute("CREATE TABLE data (id INT, value TEXT)")
    con.commit()
    con.close()

    actual_hash = hash_file(old_db_path)

    # Create the manifest data using the REAL hash.
    manifest_data = [
        {
            "fileName": "core-dataset.sqlite",
            "latestVersion": "v1",
            "history": [
                {
                    "version": "v1",
                    "timestamp": "2025-06-30T10:00:00Z",
                    "sha256": actual_hash,  # Use the real hash here
                    "r2_object_key": "core-dataset/v1-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.sqlite",
                    "diffFromPrevious": None,
                    "commit": "f4b8e7a",
                }
            ],
        }
    ]

    manifest_path = repo_path / "manifest.json"
    with manifest_path.open("w") as f:
        json.dump(manifest_data, f, indent=2)

    subprocess.run(["git", "add", "manifest.json"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit with manifest"],
        cwd=repo_path,
        check=True,
    )

    yield repo_path

    shutil.rmtree(repo_path)
