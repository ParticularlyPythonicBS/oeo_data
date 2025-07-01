# tests/test_main.py
import os
import subprocess

from typer.testing import CliRunner

from datamanager.__main__ import app

runner = CliRunner()

# Keep a reference to the original function to call it for non-mocked commands
original_subprocess_run = subprocess.run


def selective_mock_subprocess_run(*args, **kwargs):
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


def test_update_success(test_repo, mocker):
    """Test the full, successful update workflow."""
    os.chdir(test_repo)

    mock_r2_client = mocker.patch("datamanager.core.get_r2_client").return_value
    mock_prompt = mocker.patch("questionary.text").return_value
    mock_prompt.ask.return_value = "feat: Update core dataset"
    # FIX: Use the selective mock that only intercepts 'git push'
    mocker.patch("subprocess.run", side_effect=selective_mock_subprocess_run)

    result = runner.invoke(app, ["update", "core-dataset.sqlite", "new_data.sqlite"])

    assert result.exit_code == 0, result.stdout
    assert "🎉 Update complete and pushed successfully!" in result.stdout
    mock_r2_client.upload_file.assert_called_once()


def test_update_failure_and_rollback(test_repo, mocker):
    """Test that a failure during R2 upload triggers a full rollback."""
    os.chdir(test_repo)

    mock_r2_client = mocker.patch("datamanager.core.get_r2_client").return_value
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


def test_update_no_changes(test_repo, mocker):
    """Test the command when the file hash is identical."""
    os.chdir(test_repo)
    mocker.patch("datamanager.core.get_r2_client").return_value

    # This test will now pass because the 'old_data.sqlite' file is a valid DB,
    # so the diffing logic doesn't crash the application.
    result = runner.invoke(app, ["update", "core-dataset.sqlite", "old_data.sqlite"])

    assert result.exit_code == 0, result.stdout
    assert "No changes detected" in result.stdout


def test_verify_command_success(mocker):
    """Test the 'verify' command with successful credentials."""
    mocker.patch(
        "datamanager.core.verify_r2_access",
        return_value=(True, "Success message!"),
    )
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0
    assert "✅ Verification successful!" in result.stdout
    assert "Success message!" in result.stdout


def test_verify_command_failure(mocker):
    """Test the 'verify' command with failed credentials."""
    mocker.patch(
        "datamanager.core.verify_r2_access",
        return_value=(False, "Failure message!"),
    )
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 1
    assert "❌ Verification failed!" in result.stdout
    assert "Failure message!" in result.stdout
