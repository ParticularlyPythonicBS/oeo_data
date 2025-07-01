# tests/test_core.py
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from datamanager import core
from datamanager.config import config


def test_hash_file(tmp_path: Path):
    """Test SHA256 hash calculation."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")
    # Known SHA256 hash for "hello world"
    expected_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert core.hash_file(test_file) == expected_hash


def test_generate_sql_diff(tmp_path: Path):
    """Test creating a diff between two sqlite files."""
    old_db_path = tmp_path / "old.sqlite"
    new_db_path = tmp_path / "new.sqlite"

    # Create old DB
    con = sqlite3.connect(old_db_path)
    con.execute("CREATE TABLE users (id INT, name TEXT)")
    con.execute("INSERT INTO users VALUES (1, 'Alice')")
    con.commit()
    con.close()

    # Create new DB with a change
    con = sqlite3.connect(new_db_path)
    con.execute("CREATE TABLE users (id INT, name TEXT)")
    con.execute("INSERT INTO users VALUES (2, 'Bob')")  # Changed data
    con.commit()
    con.close()

    diff = core.generate_sql_diff(old_db_path, new_db_path)
    assert "-INSERT INTO users VALUES(1,'Alice');" in diff
    assert "+INSERT INTO users VALUES(2,'Bob');" in diff


def test_r2_interactions(mocker, tmp_path: Path):
    """Test that our code calls the boto3 client correctly."""
    mock_client = MagicMock()
    mocker.patch("datamanager.core.get_r2_client", return_value=mock_client)

    # Create a dummy file so that `file_path.stat()` doesn't fail.
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.touch()

    # Test upload
    core.upload_to_r2(mock_client, dummy_file, "my/object/key")
    mock_client.upload_file.assert_called_once()

    # Test delete
    core.delete_from_r2(mock_client, "my/object/key")
    mock_client.delete_object.assert_called_once_with(
        Bucket=config.R2_BUCKET, Key="my/object/key"
    )


def test_verify_r2_access_success(mocker):
    """Test successful R2 access verification."""
    mock_client = MagicMock()
    mocker.patch("datamanager.core.get_r2_client", return_value=mock_client)

    success, message = core.verify_r2_access()

    assert success is True
    assert "Successfully connected" in message
    mock_client.head_bucket.assert_called_once()


def test_verify_r2_access_no_such_bucket(mocker):
    """Test R2 verification failure due to a non-existent bucket."""
    mock_client = MagicMock()
    mocker.patch("datamanager.core.get_r2_client", return_value=mock_client)
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")

    success, message = core.verify_r2_access()

    assert success is False
    assert "not found" in message


def test_verify_r2_access_access_denied(mocker):
    """Test R2 verification failure due to permissions."""
    mock_client = MagicMock()
    mocker.patch("datamanager.core.get_r2_client", return_value=mock_client)
    error_response = {"Error": {"Code": "403", "Message": "Access Denied"}}
    mock_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")

    success, message = core.verify_r2_access()

    assert success is False
    assert "Access Denied" in message
