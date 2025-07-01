# tests/test_main.py
import os
import subprocess
from pathlib import Path
from typing import Any

from pytest_mock import MockerFixture


from typer.testing import CliRunner

from datamanager.__main__ import app
from datamanager import manifest

runner = CliRunner()

# Keep a reference to the original function to call it for non-mocked commands
original_subprocess_run = subprocess.run


def selective_mock_subprocess_run(
    *args: Any, **kwargs: Any
) -> subprocess.CompletedProcess[bytes] | Any:
    """
    A side_effect for mocking subprocess.run.
    It mocks 'git push' but lets all other commands pass through to the original.
    """
    command = args[0]
    if command and command[0] == "git" and command[1] == "push":
        # For 'git push', return a successful dummy process instead of calling it
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout=b"", stderr=b""
        )
    # For all other commands, call the original function
    return original_subprocess_run(*args, **kwargs)


def test_update_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the full, successful update workflow."""
    os.chdir(test_repo)

    mock_r2_client = mocker.patch("datamanager.core.get_r2_client").return_value

    mock_r2_client.head_object.return_value = {"ContentLength": 12345}

    mock_prompt = mocker.patch("questionary.text").return_value
    mock_prompt.ask.return_value = "feat: Update core dataset"
    # FIX: Use the selective mock that only intercepts 'git push'
    mocker.patch("subprocess.run", side_effect=selective_mock_subprocess_run)

    result = runner.invoke(app, ["update", "core-dataset.sqlite", "new_data.sqlite"])

    assert result.exit_code == 0, result.stdout
    assert "🎉 Update complete and pushed successfully!" in result.stdout
    mock_r2_client.upload_file.assert_called_once()


def test_update_failure_and_rollback(test_repo: Path, mocker: MockerFixture) -> None:
    """Test that a failure during R2 upload triggers a full rollback."""
    os.chdir(test_repo)

    mock_r2_client = mocker.patch("datamanager.core.get_r2_client").return_value

    mock_r2_client.head_object.return_value = {"ContentLength": 12345}

    mock_r2_client.upload_file.side_effect = Exception("R2 Connection Error")
    mock_prompt = mocker.patch("questionary.text").return_value
    mock_prompt.ask.return_value = "A failed update"

    initial_commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    with open("manifest.json") as f:
        initial_manifest_content = f.read()

    result = runner.invoke(app, ["update", "core-dataset.sqlite", "new_data.sqlite"])

    assert result.exit_code != 0, result.stdout
    assert "Rolling back changes..." in result.stdout

    mock_r2_client.delete_object.assert_called_once()
    final_commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    assert initial_commit_hash == final_commit_hash

    with open("manifest.json") as f:
        final_manifest_content = f.read()
    assert initial_manifest_content == final_manifest_content


def test_update_no_changes(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the command when the file hash is identical."""
    os.chdir(test_repo)
    mocker.patch("datamanager.core.get_r2_client").return_value

    # This test will now pass because the 'old_data.sqlite' file is a valid DB,
    # so the diffing logic doesn't crash the application.
    result = runner.invoke(app, ["update", "core-dataset.sqlite", "old_data.sqlite"])

    assert result.exit_code == 0, result.stdout
    assert "No changes detected" in result.stdout


def test_verify_command_success(mocker: MockerFixture) -> None:
    """Test the 'verify' command with successful credentials."""
    mocker.patch(
        "datamanager.core.verify_r2_access",
        return_value=(True, "Success message!"),
    )
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0
    assert "✅ Verification successful!" in result.stdout
    assert "Success message!" in result.stdout


def test_verify_command_failure(mocker: MockerFixture) -> None:
    """Test the 'verify' command with failed credentials."""
    mocker.patch(
        "datamanager.core.verify_r2_access",
        return_value=(False, "Failure message!"),
    )
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 1
    assert "❌ Verification failed!" in result.stdout
    assert "Failure message!" in result.stdout


def test_pull_command_latest_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the 'pull' command for the latest version."""
    os.chdir(test_repo)
    mock_pull = mocker.patch("datamanager.core.pull_and_verify", return_value=True)

    result = runner.invoke(app, ["pull", "core-dataset.sqlite"])

    assert result.exit_code == 0
    assert "✅ Success!" in result.stdout
    # Verify it called the core function with the latest version's info
    mock_pull.assert_called_once()
    call_args = mock_pull.call_args[0]
    assert "v1-e3b0c442" in call_args[0]  # Check r2_object_key
    assert call_args[2] == Path("core-dataset.sqlite")  # Check output path


def test_pull_command_version_not_found(test_repo: Path, mocker: MockerFixture) -> None:
    """Test pulling a version that does not exist."""
    os.chdir(test_repo)
    result = runner.invoke(app, ["pull", "core-dataset.sqlite", "--version", "v99"])
    assert result.exit_code == 1
    assert "Could not find version 'v99'" in result.stdout


def test_create_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test creating a new dataset successfully."""
    os.chdir(test_repo)
    new_file = test_repo / "new_dataset.sqlite"
    new_file.touch()

    mock_r2_client = mocker.patch("datamanager.core.get_r2_client").return_value
    mock_prompt = mocker.patch("questionary.text").return_value
    mock_prompt.ask.return_value = "feat: Add new dataset"
    mocker.patch("subprocess.run", side_effect=selective_mock_subprocess_run)

    result = runner.invoke(app, ["create", "new-dataset.sqlite", str(new_file)])

    assert result.exit_code == 0, result.stdout
    assert "🎉 New dataset created and pushed successfully!" in result.stdout

    # Verify R2 upload was called with a v1 key
    mock_r2_client.upload_file.assert_called_once()
    r2_key = mock_r2_client.upload_file.call_args[0][2]
    assert "new-dataset/v1-" in r2_key

    # Verify the manifest was updated
    final_manifest = manifest.read_manifest()
    assert len(final_manifest) == 2
    assert final_manifest[1]["fileName"] == "new-dataset.sqlite"
    assert final_manifest[1]["latestVersion"] == "v1"


def test_create_failure_already_exists(test_repo: Path, mocker: MockerFixture) -> None:
    """Test that 'create' fails if the dataset name already exists."""
    os.chdir(test_repo)
    new_file = test_repo / "another.sqlite"
    new_file.touch()

    result = runner.invoke(app, ["create", "core-dataset.sqlite", str(new_file)])

    assert result.exit_code == 1
    assert "already exists" in result.stdout


def test_create_failure_and_rollback(test_repo: Path, mocker: MockerFixture) -> None:
    """Test that 'create' rolls back correctly on R2 upload failure."""
    os.chdir(test_repo)
    new_file = test_repo / "new_dataset.sqlite"
    new_file.touch()

    mock_r2_client = mocker.patch("datamanager.core.get_r2_client").return_value
    mock_r2_client.upload_file.side_effect = Exception("R2 Connection Error")
    mock_prompt = mocker.patch("questionary.text").return_value
    mock_prompt.ask.return_value = "A failed create"

    initial_commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()

    result = runner.invoke(app, ["create", "new-dataset.sqlite", str(new_file)])

    assert result.exit_code == 1
    assert "Rolling back changes..." in result.stdout
    mock_r2_client.delete_object.assert_called_once()
    final_commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    assert initial_commit_hash == final_commit_hash
