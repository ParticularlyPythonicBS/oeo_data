# datamanager/manifest.py
"""
Handles all read and write operations for the manifest.json file.
This module ensures that the manifest is handled safely and consistently.
"""

import json
from pathlib import Path
from typing import Any, Optional

from rich.console import Console

from datamanager.config import settings

__all__ = [
    "read_manifest",
    "write_manifest",
    "get_dataset",
    "add_history_entry",
    "update_latest_history_entry",
    "get_version_entry",
    "add_new_dataset",
    "update_dataset",
]

# Initialize console for any feedback
console = Console()
MANIFEST_PATH = Path(settings.manifest_file)


def read_manifest() -> list[dict[str, Any]]:
    """
    Reads the manifest.json file from disk.

    Returns:
        A list of dataset dictionaries. Returns an empty list if the
        manifest does not exist.
    """
    if not MANIFEST_PATH.exists():
        return []
    try:
        with MANIFEST_PATH.open("r") as f:
            data: list[dict[str, Any]] = json.load(f)
            return data
    except json.JSONDecodeError:
        console.print(
            f"[bold red]Error:[/] Could not parse '{MANIFEST_PATH}'. "
            "The file may be corrupted."
        )
        raise


def write_manifest(data: list[dict[str, Any]]) -> None:
    """
    Writes the provided data structure to the manifest.json file.

    Args:
        data: The list of dataset dictionaries to write to the file.
    """
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")
    payload = json.dumps(data, indent=2) + "\n"  # ensure newline at end
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(MANIFEST_PATH)  # atomic swap


def update_latest_version(name: str, new_version: str) -> None:
    """Updates the top-level 'latestVersion' field for a dataset."""
    data = read_manifest()
    for item in data:
        if item.get("fileName") == name:
            item["latestVersion"] = new_version
            break
    write_manifest(data)


def get_dataset(name: str) -> Optional[dict[str, Any]]:
    """
    Finds and returns a single dataset from the manifest by its logical name.

    Args:
        name: The 'fileName' of the dataset to find.

    Returns:
        The dataset dictionary if found, otherwise None.
    """
    data = read_manifest()
    for item in data:
        if item.get("fileName") == name:
            return item
    return None


def add_history_entry(name: str, new_entry: dict[str, Any]) -> None:
    """
    Adds a new version entry to the beginning of a dataset's history.

    This function is used to add the temporary placeholder before the final
    commit hash is known.

    Args:
        name: The 'fileName' of the dataset to update.
        new_entry: The new history dictionary to prepend.
    """
    data = read_manifest()
    dataset_found = False
    for item in data:
        if item.get("fileName") == name:
            # Prepend the new entry to the history list
            item["history"].insert(0, new_entry)
            dataset_found = True
            break

    if not dataset_found:
        # This would be for creating a brand new dataset entry
        # For now, we assume we only update existing ones.
        # A 'datamanager create' command could use this logic.
        console.print(f"Dataset '{name}' not found. Cannot add history.")
        return

    write_manifest(data)


def update_latest_history_entry(name: str, final_entry: dict[str, Any]) -> None:
    """
    Replaces the most recent history entry of a dataset.

    This is used to amend the placeholder entry with the final, complete
    data after the commit has been made.

    Args:
        name: The 'fileName' of the dataset to update.
        final_entry: The final history dictionary that will replace the
                     current latest entry.
    """
    data = read_manifest()
    dataset_found = False
    for item in data:
        if item.get("fileName") == name:
            if not item["history"]:
                console.print(
                    f"[bold red]Error:[/] Cannot update history for '{name}' "
                    "because it is empty."
                )
                return
            # Replace the latest entry (at index 0)
            item["history"][0] = final_entry
            # Also update the top-level latestVersion convenience field
            item["latestVersion"] = final_entry["version"]
            dataset_found = True
            break

    if not dataset_found:
        console.print(f"Dataset '{name}' not found. Cannot update history.")
        return

    write_manifest(data)


def get_version_entry(
    dataset_name: str, version: str = "latest"
) -> Optional[dict[str, Any]]:
    """
    Finds the history entry for a specific version of a dataset.

    Args:
        dataset_name: The 'fileName' of the dataset.
        version: The version string (e.g., "v1") or "latest".

    Returns:
        The history entry dictionary if found, otherwise None.
    """
    dataset = get_dataset(dataset_name)
    if not dataset:
        return None

    history = dataset.get("history")
    if not isinstance(history, list):
        return None

    if version == "latest":
        return history[0] if history else None

    for entry in history:
        if isinstance(entry, dict) and entry.get("version") == version:
            return entry

    return None


def add_new_dataset(dataset_object: dict[str, Any]) -> None:
    """
    Appends a new dataset object to the manifest file.

    Args:
        dataset_object: The complete dictionary for the new dataset.
    """
    data = read_manifest()
    data.append(dataset_object)
    write_manifest(data)


def update_dataset(name: str, updated_dataset: dict[str, Any]) -> None:
    """
    Finds a dataset by name and replaces the entire object.
    Used for amending the commit hash after the initial commit.
    """
    data = read_manifest()
    for i, item in enumerate(data):
        if item.get("fileName") == name:
            data[i] = updated_dataset
            break
    write_manifest(data)
