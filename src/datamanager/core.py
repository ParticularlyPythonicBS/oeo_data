# datamanager/core.py
import hashlib
import subprocess
import tempfile
from pathlib import Path
import os

from botocore.exceptions import ClientError

import boto3
from rich.progress import Progress
from rich.console import Console

from types_boto3_s3.client import S3Client

from datamanager.config import config


console = Console()


def get_r2_client() -> S3Client:
    """Initializes and returns a boto3 S3 client for R2."""
    return boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT_URL,
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def hash_file(file_path: Path) -> str:
    """Calculates and returns the SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def upload_to_r2(client, file_path: Path, object_key: str):
    """Uploads a file to R2 with a progress bar."""
    file_size = file_path.stat().st_size
    with Progress() as progress:
        task = progress.add_task(
            f"[cyan]Uploading {file_path.name}...", total=file_size
        )
        client.upload_file(
            str(file_path),
            config.R2_BUCKET,
            object_key,
            Callback=lambda bytes_transferred: progress.update(
                task, advance=bytes_transferred
            ),
        )


def download_from_r2(client, object_key: str, download_path: Path):
    """Downloads a file from R2 with a progress bar."""
    try:
        file_size = client.head_object(Bucket=config.R2_BUCKET, Key=object_key)[
            "ContentLength"
        ]
        with Progress() as progress:
            task = progress.add_task(
                f"[cyan]Downloading {download_path.name}...", total=file_size
            )
            client.download_file(
                config.R2_BUCKET,
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
    """Generates a textual SQL diff between two sqlite files."""
    with tempfile.TemporaryDirectory() as tempdir:
        old_sql = Path(tempdir) / "old.sql"
        new_sql = Path(tempdir) / "new.sql"

        subprocess.run(
            ["sqlite3", str(old_file), ".dump"],
            check=True,
            text=True,
            stdout=old_sql.open("w"),
        )
        subprocess.run(
            ["sqlite3", str(new_file), ".dump"],
            check=True,
            text=True,
            stdout=new_sql.open("w"),
        )

        # Use diff to compare the SQL dumps
        result = subprocess.run(
            ["diff", "-u", str(old_sql), str(new_sql)],
            capture_output=True,
            text=True,
        )
        # diff exits with 1 if files differ, so we don't check for success
        return result.stdout


def delete_from_r2(client, object_key: str):
    """Deletes an object from the R2 bucket."""
    console.print(f"Attempting to delete [yellow]{object_key}[/] from R2...")
    try:
        client.delete_object(Bucket=config.R2_BUCKET, Key=object_key)
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
        console.print(f"Attempting to access bucket: [cyan]{config.R2_BUCKET}[/]...")
        client.head_bucket(Bucket=config.R2_BUCKET)
        return (
            True,
            f"Successfully connected to bucket '{config.R2_BUCKET}'.",
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404" or "NoSuchBucket" in str(e):
            return (
                False,
                f"Bucket '{config.R2_BUCKET}' not found. Please check the name.",
            )
        if error_code == "403" or "AccessDenied" in str(e):
            return (
                False,
                "Access Denied. The provided credentials do not have permission "
                f"to access the bucket '{config.R2_BUCKET}'.",
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
