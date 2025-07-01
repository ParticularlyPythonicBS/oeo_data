# datamanager/__main__.py
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import questionary
import typer
from rich.console import Console
from rich.table import Table

from typing import Callable

from datamanager.config import config
from datamanager import core, manifest

# Initialize Typer app and Rich console
app = typer.Typer(
    name="datamanager",
    help="A CLI for managing versioned data in R2.",
    add_completion=False,
)
console = Console()


@app.command()
def verify():
    """Verifies the Cloudflare R2 credentials and bucket access."""
    console.print("🔍 Verifying Cloudflare R2 configuration...")
    with console.status("[bold yellow]Connecting to R2...[/]"):
        success, message = core.verify_r2_access()

    if success:
        console.print(f"[bold green]✅ Verification successful![/] {message}")
    else:
        console.print(f"[bold red]❌ Verification failed![/] {message}")
        raise typer.Exit(1)


@app.command()
def list_datasets():
    """Lists all datasets tracked in the manifest."""
    data = manifest.read_manifest()
    table = Table("Dataset Name", "Latest Version", "Last Updated", "SHA256")
    for item in data:
        latest = item["history"][0]
        table.add_row(
            item["fileName"],
            latest["version"],
            latest["timestamp"],
            f"{latest['sha256'][:12]}...",
        )
    console.print(table)


@app.command()  # type: ignore[misc]
def update(
    name: str = typer.Argument(..., help="The logical name of the dataset."),
    file: Path = typer.Argument(..., help="Path to the new .sqlite file.", exists=True),
):
    """Updates a dataset with a new version, committing and pushing the result."""
    console.print(f"🚀 Starting update for [bold cyan]{name}[/]...")

    # --- 1. Local Preparation ---
    new_hash = core.hash_file(file)
    dataset = manifest.get_dataset(name)
    if not dataset:
        console.print(f"[bold red]Error:[/] Dataset '{name}' not found.")
        raise typer.Exit(1)

    latest_version = dataset["history"][0]
    if new_hash == latest_version["sha256"]:
        console.print(
            "✅ No changes detected. File is identical to the latest version."
        )
        return

    prev_version_num = int(latest_version["version"].lstrip("v"))
    new_version = f"v{prev_version_num + 1}"
    console.print(
        f"Change detected! New version will be [bold magenta]{new_version}[/]."
    )

    client = core.get_r2_client()
    with tempfile.TemporaryDirectory() as tempdir:
        old_file_path = Path(tempdir) / "old_version.sqlite"
        core.download_from_r2(client, latest_version["r2_object_key"], old_file_path)
        diff_content = core.generate_sql_diff(old_file_path, file)

    diff_git_path = None
    if diff_content.count("\n") <= config.MAX_DIFF_LINES:
        diff_filename = f"diff-{latest_version['version']}-to-{new_version}.diff"
        diff_git_path = Path(name).with_suffix("") / diff_filename
        diff_git_path.parent.mkdir(exist_ok=True)
        diff_git_path.write_text(diff_content)
        subprocess.run(["git", "add", str(diff_git_path)])
        console.print(f"📝 Diff stored in Git at: [green]{diff_git_path}[/]")
    else:
        console.print("📝 Diff is too large, will not be stored in Git.")

    manifest.add_history_entry(name, {})  # Add a temporary placeholder
    subprocess.run(["git", "add", config.MANIFEST_FILE])

    # --- 2. Prompt and Commit Locally ---
    commit_message = questionary.text(
        "Enter commit message:", default=f"Update {name} to {new_version}"
    ).ask()

    if not commit_message:
        console.print("[bold red]Commit cancelled. Aborting update.[/]")
        subprocess.run(["git", "reset"])  # Unstage all files
        raise typer.Exit()

    # We commit *before* the upload. The commit hash will be added to the manifest later.
    subprocess.run(["git", "commit", "-m", commit_message], check=True)
    commit_hash = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .decode()
        .strip()
    )

    # --- 3. Transactional Upload and Push ---
    r2_dir = Path(latest_version["r2_object_key"]).parent
    new_r2_key = f"{r2_dir}/{new_version}-{new_hash}.sqlite"

    try:
        # Finalize the manifest entry with the correct commit hash
        new_entry = {
            "version": new_version,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sha256": new_hash,
            "r2_object_key": new_r2_key,
            "diffFromPrevious": str(diff_git_path) if diff_git_path else None,
            "commit": commit_hash,
        }
        manifest.update_latest_history_entry(name, new_entry)
        # Amend the previous commit to include the final manifest content
        subprocess.run(["git", "add", config.MANIFEST_FILE])
        subprocess.run(["git", "commit", "--amend", "--no-edit"], check=True)

        console.print(f"Uploading [green]{file.name}[/] to R2...")
        core.upload_to_r2(client, file, new_r2_key)

        console.print("Pushing changes to remote repository...")
        subprocess.run(["git", "push"], check=True, capture_output=True)

    except (subprocess.CalledProcessError, Exception) as e:
        console.print("\n[bold red]An error occurred during the finalization step![/]")
        if isinstance(e, subprocess.CalledProcessError):
            console.print(f"[red]Error during git operation:\n{e.stderr.decode()}[/]")
        else:
            console.print(f"[red]Error during R2 upload: {e}[/]")

        console.print("\n[bold yellow]Rolling back changes...[/]")
        core.delete_from_r2(client, new_r2_key)
        subprocess.run(["git", "reset", "--hard", "HEAD~1"])
        console.print(
            "\n[bold yellow]Rollback complete. Your repository is in its previous state.[/]"
        )
        raise typer.Exit(1)

    console.print("\n[bold green]🎉 Update complete and pushed successfully![/]")


@app.callback(invoke_without_command=True)  # type: ignore[misc]
def main(ctx: typer.Context):
    """Entrypoint that shows a TUI if no command is given."""
    if ctx.invoked_subcommand is not None:
        return

    console.print("[bold yellow]Welcome to the Data Manager TUI![/]")

    actions: dict[str, Callable[[], None] | str] = {
        "List all datasets": list_datasets,
        "Update an existing dataset": "update_interactive",
        "Exit": "exit",
    }

    choice = questionary.select(
        "What would you like to do?", choices=list(actions.keys())
    ).ask()

    if choice == "Exit" or choice is None:
        console.print("Goodbye!")
        raise typer.Exit()

    action = actions[choice]
    if action == "update_interactive":
        # This is a placeholder for the interactive update flow
        console.print("\nStarting interactive update...")
        # You would use questionary.select for dataset and questionary.path for file
        # then call the update() function with the results.
        # TODO: Implement interactive update flow
    elif callable(action):
        # Call the function directly
        action()


if __name__ == "__main__":
    app()
