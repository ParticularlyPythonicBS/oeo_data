# datamanager/core.py
import difflib
import hashlib
import io
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path, PurePath
import os

from botocore.exceptions import ClientError

import boto3
from rich.progress import Progress
from rich.console import Console

from types_boto3_s3.client import S3Client

from datamanager.config import settings


console = Console()


def get_r2_client() -> S3Client:
    """Initializes and returns a boto3 S3 client for R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name="auto",
    )


def hash_file(file_path: Path) -> str:
    """Calculates and returns the SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def upload_to_r2(client: S3Client, file_path: Path, object_key: str) -> None:
    """Uploads a file to R2 with a progress bar."""
    file_size = file_path.stat().st_size
    with Progress() as progress:
        task = progress.add_task(
            f"[cyan]Uploading {file_path.name}...", total=file_size
        )
        client.upload_file(
            str(file_path),
            settings.bucket,
            object_key,
            Callback=lambda bytes_transferred: progress.update(
                task, advance=bytes_transferred
            ),
        )


def download_from_r2(client: S3Client, object_key: str, download_path: Path) -> None:
    """Downloads a file from R2 with a progress bar."""
    try:
        file_size = client.head_object(Bucket=settings.bucket, Key=object_key)[
            "ContentLength"
        ]
        with Progress() as progress:
            task = progress.add_task(
                f"[cyan]Downloading {download_path.name}...", total=file_size
            )
            client.download_file(
                settings.bucket,
                object_key,
                str(download_path),
                Callback=lambda bytes_transferred: progress.update(
                    task, advance=bytes_transferred
                ),
            )
    except ClientError as e:
        # Handle cases where the object might not exist
        console.print(f"[bold red]Error downloading from R2: {e}[/]")
        raise


def pull_and_verify(object_key: str, expected_hash: str, output_path: Path) -> bool:
    """
    Downloads a file from R2, verifies its hash, and cleans up on failure.

    Returns:
        True if download and verification succeed, False otherwise.
    """
    client = get_r2_client()
    try:
        download_from_r2(client, object_key, output_path)
    except Exception:
        return False  # Error message is printed inside download_from_r2

    console.print("Verifying file integrity...")
    downloaded_hash = hash_file(output_path)

    if downloaded_hash == expected_hash:
        return True
    else:
        console.print("[bold red]Integrity check FAILED![/]")
        console.print(f"  Expected SHA256: {expected_hash}")
        console.print(f"  Actual SHA256:   {downloaded_hash}")
        console.print(f"Deleting corrupted file: [yellow]{output_path}[/]")
        os.remove(output_path)
        return False


def generate_sql_diff(old_file: Path, new_file: Path) -> str:
    """
    Return a unified diff of the SQL schema/data between two SQLite files.

    - If both sqlite cli and diff are available, use them (fast path).
    - Otherwise fall back to std-lib `sqlite3` + `difflib` (pure-Python).
    """

    has_cli = shutil.which("sqlite3") and shutil.which("diff")

    if has_cli:
        with tempfile.TemporaryDirectory() as tmp:
            old_dump, new_dump = Path(tmp) / "old.sql", Path(tmp) / "new.sql"
            subprocess.run(
                ["sqlite3", str(old_file), ".dump"],
                text=True,
                check=True,
                stdout=old_dump.open("w"),
            )
            subprocess.run(
                ["sqlite3", str(new_file), ".dump"],
                text=True,
                check=True,
                stdout=new_dump.open("w"),
            )
            proc = subprocess.run(
                ["diff", "-u", str(old_dump), str(new_dump)],
                text=True,
                capture_output=True,
            )
            return proc.stdout

    # pure-Python fallback

    def _dump(db: Path) -> str:
        buf = io.StringIO()
        con = sqlite3.connect(db)
        for line in con.iterdump():
            buf.write(f"{line}\n")
        con.close()
        return buf.getvalue()

    old_sql, new_sql = _dump(old_file), _dump(new_file)
    diff_iter = difflib.unified_diff(
        old_sql.splitlines(keepends=True),
        new_sql.splitlines(keepends=True),
        fromfile=str(PurePath(old_file).name),
        tofile=str(PurePath(new_file).name),
    )
    return "".join(diff_iter)


def delete_from_r2(client: S3Client, object_key: str) -> None:
    """Deletes an object from the R2 bucket."""
    console.print(f"Attempting to delete [yellow]{object_key}[/] from R2...")
    try:
        client.delete_object(Bucket=settings.bucket, Key=object_key)
        console.print("✅ Rollback deletion successful.")
    except Exception as e:
        # This is a best-effort cleanup. We notify the user if it fails.
        console.print(
            f"[bold red]Warning:[/] Failed to delete R2 object during rollback: {e}"
        )
        console.print("You may need to manually delete the object from your R2 bucket.")


def verify_r2_access() -> tuple[bool, str]:
    """
    Verifies that the configured R2 credentials and bucket are accessible.

    Returns:
        A tuple containing a boolean for success and a status message.
    """
    try:
        client = get_r2_client()
        console.print(f"Attempting to access bucket: [cyan]{settings.bucket}[/]...")
        client.head_bucket(Bucket=settings.bucket)
        return (
            True,
            f"Successfully connected to bucket '{settings.bucket}'.",
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404" or "NoSuchBucket" in str(e):
            return (
                False,
                f"Bucket '{settings.bucket}' not found. Please check the name.",
            )
        if error_code == "403" or "AccessDenied" in str(e):
            return (
                False,
                "Access Denied. The provided credentials do not have permission "
                f"to access the bucket '{settings.bucket}'.",
            )
        return (
            False,
            f"A client error occurred: {e}. Please check your credentials and endpoint.",
        )
    except Exception as e:
        return (
            False,
            f"An unexpected error occurred. This could be a network issue or an "
            f"incorrect R2 endpoint URL. Error: {e}",
        )
