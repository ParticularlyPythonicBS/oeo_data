import os
from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from datamanager import __main__ as main_app
from datamanager.__main__ import app
from datamanager import manifest

runner = CliRunner()


def test_prepare_for_create_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the 'prepare' command for a brand-new dataset."""
    os.chdir(test_repo)
    new_file = test_repo / "new_dataset.sqlite"
    new_file.touch()

    mocker.patch("datamanager.core.get_r2_client")
    mock_upload = mocker.patch("datamanager.core.upload_to_staging")

    result = runner.invoke(app, ["prepare", "new-dataset.sqlite", str(new_file)])

    assert result.exit_code == 0, result.stdout
    assert "New dataset detected! Preparing version: v1" in result.stdout
    assert "Preparation complete!" in result.stdout

    mock_upload.assert_called_once()

    # Verify the manifest was updated correctly
    final_manifest = manifest.read_manifest()
    new_dataset = next(
        (ds for ds in final_manifest if ds["fileName"] == "new-dataset.sqlite"), None
    )
    assert new_dataset is not None
    assert new_dataset["latestVersion"] == "v1"
    history_entry = new_dataset["history"][0]
    assert "staging_key" in history_entry
    assert history_entry["commit"] == "pending-merge"


def test_prepare_for_update_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the 'prepare' command for an existing dataset."""
    os.chdir(test_repo)

    mocker.patch("datamanager.core.get_r2_client")
    mock_upload = mocker.patch("datamanager.core.upload_to_staging")

    result = runner.invoke(app, ["prepare", "core-dataset.sqlite", "new_data.sqlite"])

    assert result.exit_code == 0, result.stdout
    assert "Change detected! Preparing new version: v2" in result.stdout

    mock_upload.assert_called_once()

    core_dataset = manifest.get_dataset("core-dataset.sqlite")
    assert core_dataset is not None
    assert len(core_dataset["history"]) == 2  # Now has v1 and v2
    assert core_dataset["history"][0]["version"] == "v2"
    assert "staging_key" in core_dataset["history"][0]


def test_prepare_no_changes(test_repo: Path, mocker: MockerFixture) -> None:
    """Test 'prepare' when the file hash is identical to the latest version."""
    os.chdir(test_repo)
    mock_upload = mocker.patch("datamanager.core.upload_to_staging")

    result = runner.invoke(app, ["prepare", "core-dataset.sqlite", "old_data.sqlite"])

    assert result.exit_code == 0, result.stdout
    assert "No changes detected" in result.stdout
    mock_upload.assert_not_called()


def test_pull_command_latest_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the 'pull' command for the latest version."""
    os.chdir(test_repo)
    mock_pull = mocker.patch("datamanager.core.pull_and_verify", return_value=True)

    result = runner.invoke(app, ["pull", "core-dataset.sqlite"])

    assert result.exit_code == 0
    assert "✅ Success!" in result.stdout
    mock_pull.assert_called_once()
    call_args = mock_pull.call_args[0]
    # The key in the fixture has a different hash now, check for the version
    assert "core-dataset/v1-" in call_args[0]
    assert call_args[2] == Path("core-dataset.sqlite")


def test_pull_command_version_not_found(test_repo: Path, mocker: MockerFixture) -> None:
    """Test pulling a version that does not exist."""
    os.chdir(test_repo)
    result = runner.invoke(app, ["pull", "core-dataset.sqlite", "--version", "v99"])
    assert result.exit_code == 1
    assert "Could not find version 'v99'" in result.stdout


def test_verify_command_success(mocker: MockerFixture) -> None:
    """Test the 'verify' command with successful credentials."""
    mocker.patch(
        "datamanager.core.verify_r2_access",
        return_value=(True, "Success message!"),
    )
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0
    assert "✅ Verification successful!" in result.stdout


def test_verify_command_failure(mocker: MockerFixture) -> None:
    """Test the 'verify' command with failed credentials."""
    mocker.patch(
        "datamanager.core.verify_r2_access",
        return_value=(False, "Failure message!"),
    )
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 1
    assert "❌ Verification failed!" in result.stdout


def test_prepare_interactive_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the full interactive 'prepare' flow."""
    os.chdir(test_repo)
    new_file = test_repo / "new_dataset.sqlite"
    new_file.touch()

    mock_run_logic = mocker.patch("datamanager.__main__._run_prepare_logic")

    mocker.patch(
        "questionary.path",
        return_value=mocker.Mock(ask=mocker.Mock(return_value=str(new_file))),
    )
    mocker.patch(
        "questionary.text",
        return_value=mocker.Mock(ask=mocker.Mock(return_value="new-dataset.sqlite")),
    )
    mocker.patch(
        "questionary.confirm",
        return_value=mocker.Mock(ask=mocker.Mock(return_value=True)),
    )

    # Create a simple mock context instead of a real one.
    # We only need it to have an `obj` attribute.
    mock_ctx = mocker.MagicMock()
    mock_ctx.obj = {}  # Simulate an empty context object

    # Call the private method directly from the imported module
    main_app._prepare_interactive(mock_ctx)

    mock_run_logic.assert_called_once_with(
        mock_ctx, name="new-dataset.sqlite", file=new_file
    )


def test_prepare_interactive_cancel(test_repo: Path, mocker: MockerFixture) -> None:
    """Test cancelling the interactive 'prepare' flow."""
    os.chdir(test_repo)
    mock_run_logic = mocker.patch("datamanager.__main__._run_prepare_logic")

    mocker.patch(
        "questionary.path",
        return_value=mocker.Mock(ask=mocker.Mock(return_value=None)),
    )

    mock_ctx = mocker.MagicMock()
    mock_ctx.obj = {}

    main_app._prepare_interactive(mock_ctx)

    mock_run_logic.assert_not_called()


def test_pull_command_with_output_dir(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the 'pull' command with the -o flag pointing to a directory."""
    os.chdir(test_repo)
    mock_pull = mocker.patch("datamanager.core.pull_and_verify", return_value=True)

    output_dir = test_repo / "downloads"
    output_dir.mkdir()

    result = runner.invoke(app, ["pull", "core-dataset.sqlite", "-o", str(output_dir)])

    assert result.exit_code == 0
    mock_pull.assert_called_once()
    # Verify it constructed the correct final path inside the directory
    final_path = mock_pull.call_args[0][2]
    assert final_path == output_dir / "core-dataset.sqlite"


def test_pull_interactive_success(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the full interactive 'pull' flow."""
    os.chdir(test_repo)
    mock_run_logic = mocker.patch("datamanager.__main__._run_pull_logic")

    # Simulate a user answering all prompts successfully
    mocker.patch(
        "questionary.select",
        side_effect=[
            mocker.Mock(ask=mocker.Mock(return_value="core-dataset.sqlite")),
            mocker.Mock(ask=mocker.Mock(return_value="v1 (commit: f4b8e7a, ...)")),
        ],
    )
    mocker.patch(
        "questionary.path",
        return_value=mocker.Mock(ask=mocker.Mock(return_value="./pulled-file.sqlite")),
    )

    mock_ctx = mocker.MagicMock()
    mock_ctx.obj = {}
    main_app._pull_interactive(mock_ctx)

    # Verify the core logic was called with the user's answers
    mock_run_logic.assert_called_once_with(
        name="core-dataset.sqlite",
        version="v1",
        output=Path("./pulled-file.sqlite"),
    )


def test_pull_interactive_no_datasets(test_repo: Path, mocker: MockerFixture) -> None:
    """Test the interactive pull flow when the manifest is empty."""
    os.chdir(test_repo)
    # Mock the manifest read to return an empty list
    mocker.patch("datamanager.manifest.read_manifest", return_value=[])
    mock_select = mocker.patch("questionary.select")

    mock_ctx = mocker.MagicMock()
    mock_ctx.obj = {}
    main_app._pull_interactive(mock_ctx)

    # Verify that no prompts were shown because there were no datasets
    mock_select.assert_not_called()
