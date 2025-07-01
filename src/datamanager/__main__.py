# datamanager/__main__.py
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import questionary
import typer
from rich.console import Console
from rich.table import Table

from typing import Callable, Optional

from datamanager.config import settings
from datamanager import core, manifest

# Git helpers


def _stage_all() -> None:
    """Stage every working-tree change."""
    subprocess.run(["git", "add", "-A"], check=True)


def _build_detached_commit(message: str) -> str:
    """
    Create a commit object from the **current index** without
    moving HEAD.  Returns the full commit SHA.
    """
    tree = subprocess.check_output(["git", "write-tree"], text=True).strip()
    parent = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    sha = subprocess.check_output(
        ["git", "commit-tree", tree, "-p", parent, "-m", message],
        text=True,
    ).strip()
    return sha


# Initialize Typer app and Rich console
app = typer.Typer(
    name="datamanager",
    help="A CLI for managing versioned data in R2.",
    add_completion=False,
)
console = Console()


@app.command()
def verify() -> None:
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
def list_datasets() -> None:
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


def _run_update_logic(name: str, file: Path) -> None:
    console.print(f"🚀  Updating [cyan]{name}[/]…")

    # Step 1. Pre-flight & diff
    new_hash = core.hash_file(file)
    ds = manifest.get_dataset(name)
    if not ds:
        console.print(f"[red]Dataset '{name}' not found.[/]")
        raise typer.Exit(1)

    latest = ds["history"][0]
    if new_hash == latest["sha256"]:
        console.print("✅  No changes detected (identical file).")
        return

    new_ver = f"v{int(latest['version'].lstrip('v')) + 1}"
    console.print(f"Detected change → next version will be [magenta]{new_ver}[/]")

    client = core.get_r2_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        old_path = Path(tmpdir) / "prev.sqlite"
        core.download_from_r2(client, latest["r2_object_key"], old_path)
        diff_text = core.generate_sql_diff(old_path, file)

    diff_git_path: Path | None = None
    if diff_text.count("\n") <= settings.max_diff_lines:
        diff_git_path = (
            Path("diffs") / name / f"diff-{latest['version']}-to-{new_ver}.diff"
        )
        diff_git_path.parent.mkdir(parents=True, exist_ok=True)
        diff_git_path.write_text(diff_text)
        subprocess.run(["git", "add", str(diff_git_path)])
        console.print(f"📝  Diff stored at [green]{diff_git_path}[/]")
    else:
        console.print("📝  Diff too large – omitted from Git.")

    # Step 2. Commit message
    msg = questionary.text(
        "Enter commit message:",
        default=f"Update {name} → {new_ver}",
    ).ask()
    if not msg:
        console.print("[red]Commit cancelled.[/]")
        raise typer.Exit()

    # Step 3. Build provisional commit (without manifest)
    _stage_all()
    provisional_sha = _build_detached_commit(msg)
    subprocess.run(["git", "reset", "--soft", provisional_sha], check=True)

    # Step 4. Write manifest entry with the provisional hash
    r2_dir = Path(latest["r2_object_key"]).parent
    new_r2_key = f"{r2_dir}/{new_ver}-{new_hash}.sqlite"
    entry = {
        "version": new_ver,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sha256": new_hash,
        "r2_object_key": new_r2_key,
        "diffFromPrevious": str(diff_git_path) if diff_git_path else None,
        "commit": provisional_sha[:7],  # short form
    }
    manifest.update_latest_history_entry(name, entry)
    subprocess.run(["git", "add", settings.manifest_file], check=True)

    # Step 5. Amend once – manifest now included
    subprocess.run(["git", "commit", "--amend", "-m", msg], check=True)

    # Step 6. Upload & push (rollback on failure)
    try:
        core.upload_to_r2(client, file, new_r2_key)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        console.print("\n[bold green]🎉  Update complete and pushed![/]")
    except (subprocess.CalledProcessError, Exception) as exc:
        console.print("\n[bold red]Error during finalisation![/]")
        core.delete_from_r2(client, new_r2_key)
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)
        console.print("[yellow]Rollback complete – repo restored.[/]")
        raise typer.Exit() from exc


@app.command()
def update(
    name: str = typer.Argument(..., help="The logical name of the dataset."),
    file: Path = typer.Argument(..., help="Path to the new .sqlite file.", exists=True),
) -> None:
    """Updates a dataset with a new version, committing and pushing the result."""
    _run_update_logic(name, file)


@app.command()
def pull(
    name: str = typer.Argument(..., help="The logical name of the dataset to pull."),
    version: str = typer.Option(
        "latest",
        "--version",
        "-v",
        help="Version to pull (e.g., 'v1'). Defaults to latest.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for the file. Defaults to the dataset name in the current directory.",
    ),
) -> None:
    """Pulls a specific version of a dataset from R2 and verifies its integrity."""
    console.print(f"🔎 Locating version '{version}' for dataset '{name}'...")
    version_entry = manifest.get_version_entry(name, version)

    if not version_entry:
        console.print(
            f"[bold red]Error:[/] Could not find version '{version}' for dataset '{name}'."
        )
        raise typer.Exit(1)

    # Determine final output path
    if output is None:
        final_path = Path(name)
    elif output.is_dir():
        final_path = output / name
    else:
        final_path = output

    console.print(
        f"Pulling version [magenta]{version_entry['version']}[/] (commit: {version_entry['commit']}) to [cyan]{final_path}[/]"
    )

    success = core.pull_and_verify(
        version_entry["r2_object_key"], version_entry["sha256"], final_path
    )

    if success:
        console.print(
            f"\n[bold green]✅ Success![/] File saved to [cyan]{final_path}[/]"
        )
    else:
        console.print(
            "\n[bold red]❌ Pull failed.[/] Please check the error messages above."
        )
        raise typer.Exit(1)


@app.command()
def create(
    name: str = typer.Argument(...),
    file: Path = typer.Argument(..., exists=True),
) -> None:
    """Add a brand-new dataset (v1) to the manifest."""
    console.print(f"🚀  Creating dataset [cyan]{name}[/]…")
    if manifest.get_dataset(name):
        console.print(f"[red]Dataset '{name}' already exists.[/]")
        raise typer.Exit(1)

    new_hash = core.hash_file(file)
    r2_dir = Path(name).stem
    r2_key = f"{r2_dir}/v1-{new_hash}.sqlite"

    msg = questionary.text(
        "Commit message:", default=f"feat: add dataset '{name}'"
    ).ask()
    if not msg:
        console.print("[red]Commit cancelled.[/]")
        raise typer.Exit()

    # Stage everything first (diffs none for create)
    temp_dataset = {"fileName": name, "history": [{}]}
    manifest.add_new_dataset(temp_dataset)
    _stage_all()
    provisional_sha = _build_detached_commit(msg)
    subprocess.run(["git", "reset", "--soft", provisional_sha], check=True)

    final_dataset = {
        "fileName": name,
        "latestVersion": "v1",
        "history": [
            {
                "version": "v1",
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "sha256": new_hash,
                "r2_object_key": r2_key,
                "diffFromPrevious": None,
                "commit": provisional_sha[:7],
            }
        ],
    }
    manifest.update_dataset(name, final_dataset)
    subprocess.run(["git", "add", settings.manifest_file], check=True)
    subprocess.run(["git", "commit", "--amend", "-m", msg], check=True)

    try:
        core.upload_to_r2(core.get_r2_client(), file, r2_key)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        console.print("\n[bold green]🎉  Dataset created & pushed![/]")
    except (subprocess.CalledProcessError, Exception) as exc:
        console.print("\n[red]Error during finalisation – rolling back.[/]")
        core.delete_from_r2(core.get_r2_client(), r2_key)
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)
        raise typer.Exit() from exc


def _update_interactive() -> None:
    """Guides the user through updating a dataset interactively."""
    console.print("\n[bold]Interactive Dataset Update[/]")

    # Step 1: Select the dataset
    all_datasets = manifest.read_manifest()
    if not all_datasets:
        console.print("[yellow]No datasets found in the manifest to update.[/]")
        return

    dataset_names = [ds["fileName"] for ds in all_datasets]
    selected_name = questionary.select(
        "Which dataset would you like to update?", choices=dataset_names
    ).ask()

    if selected_name is None:
        console.print("Update cancelled.")
        return

    # Step 2: Select the file
    selected_file = questionary.path(
        "Enter the path to the new .sqlite file:",
        validate=lambda path: Path(path).is_file() and Path(path).suffix == ".sqlite",
        file_filter=lambda path: path.endswith(".sqlite"),
    ).ask()

    if selected_file is None:
        console.print("Update cancelled.")
        return

    # Step 3: Confirmation
    console.print(
        f"\nYou are about to update [cyan]{selected_name}[/] with the file [green]{selected_file}[/]."
    )
    proceed = questionary.confirm("Do you want to continue?", default=False).ask()

    if not proceed:
        console.print("Update cancelled.")
        return

    # Step 4: Execute the update logic
    try:
        _run_update_logic(name=selected_name, file=Path(selected_file))
    except typer.Exit:
        # Catch the Exit exception to prevent it from crashing the TUI loop
        # The error messages are already printed by _run_update_logic
        pass


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Entrypoint that shows a TUI if no command is given."""
    if ctx.invoked_subcommand is not None:
        return

    console.print("[bold yellow]Welcome to the Data Manager TUI![/]")

    actions: dict[str, Callable[[], None] | str] = {
        "List all datasets": list_datasets,
        "Update an existing dataset": _update_interactive,
        "Exit": "exit",
    }

    choice = questionary.select(
        "What would you like to do?", choices=list(actions.keys())
    ).ask()

    if choice == "Exit" or choice is None:
        console.print("Goodbye!")
        raise typer.Exit()

    action = actions[choice]
    if callable(action):
        # Call the function directly
        action()

    else:
        raise NotImplementedError(f"Action '{choice}' is not implemented yet.")


if __name__ == "__main__":
    app()
