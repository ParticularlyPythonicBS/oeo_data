import os
import json
import subprocess
from typing import Any, Dict, List
import boto3
from botocore.exceptions import ClientError

# --- Configuration ---
ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
PROD_BUCKET = os.environ["R2_PRODUCTION_BUCKET"]
STAGING_BUCKET = os.environ["R2_STAGING_BUCKET"]
ENDPOINT_URL = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
MANIFEST_FILE = "manifest.json"

# --- Boto3 S3 Client ---
client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
)


def get_commit_details() -> Dict[str, str]:
    """Gets the hash and subject of the latest commit affecting the manifest."""
    commit_hash = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=%h", "--", MANIFEST_FILE]
        )
        .decode()
        .strip()
    )
    commit_subject = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=%s", "--", MANIFEST_FILE]
        )
        .decode()
        .strip()
    )
    return {"hash": commit_hash, "subject": commit_subject}


def finalize_manifest(updated_data: List[Dict[str, Any]], commit_message: str) -> None:
    """Writes the updated manifest, commits, and pushes the changes."""
    print("\nFinalizing manifest file...")
    with open(MANIFEST_FILE, "w") as f:
        json.dump(updated_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Committing and pushing finalized manifest...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"])
    subprocess.run(
        ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"]
    )
    subprocess.run(["git", "add", MANIFEST_FILE])
    subprocess.run(["git", "commit", "-m", commit_message])
    subprocess.run(["git", "push"])
    print("✅ Manifest finalized.")


def handle_deletions(manifest_data: List[Dict[str, Any]]) -> bool:
    """
    Scans for and processes all pending deletions.
    Returns True if any deletions were processed.
    """
    print("--- Phase 1: Checking for pending deletions ---")
    datasets_to_keep = []
    objects_to_delete_from_r2 = []
    processed_deletion = False

    for dataset in manifest_data:
        if dataset.get("status") == "pending-deletion":
            processed_deletion = True
            print(f"Found dataset marked for full deletion: {dataset['fileName']}")
            for entry in dataset.get("history", []):
                if "r2_object_key" in entry:
                    objects_to_delete_from_r2.append({"Key": entry["r2_object_key"]})
        else:
            versions_to_keep = []
            for entry in dataset.get("history", []):
                if entry.get("status") == "pending-deletion":
                    processed_deletion = True
                    print(
                        f"Found version marked for deletion: {dataset['fileName']} v{entry['version']}"
                    )
                    if "r2_object_key" in entry:
                        objects_to_delete_from_r2.append(
                            {"Key": entry["r2_object_key"]}
                        )
                else:
                    versions_to_keep.append(entry)
            dataset["history"] = versions_to_keep
            datasets_to_keep.append(dataset)

    if not processed_deletion:
        print("No pending deletions found.")
        return False

    if objects_to_delete_from_r2:
        print(
            f"\nDeleting {len(objects_to_delete_from_r2)} objects from production R2 bucket..."
        )
        for i in range(0, len(objects_to_delete_from_r2), 1000):
            chunk = objects_to_delete_from_r2[i : i + 1000]
            response = client.delete_objects(
                Bucket=PROD_BUCKET, Delete={"Objects": chunk, "Quiet": True}
            )
            if response.get("Errors"):
                print("  ❌ ERROR during batch deletion:", response["Errors"])
                exit(1)
        print("✅ Successfully deleted objects from R2.")

    finalize_manifest(datasets_to_keep, "ci: Finalize manifest after data deletion")
    return True


def handle_publications(manifest_data: List[Dict[str, Any]]) -> bool:
    """
    Scans for and processes one pending publication or rollback.
    Returns True if a publication was processed.
    """
    print("\n--- Phase 2: Checking for pending publications ---")
    for dataset in manifest_data:
        for i, entry in enumerate(dataset["history"]):
            if entry.get("commit") == "pending-merge":
                commit_details = get_commit_details()
                entry["commit"] = commit_details["hash"]
                # Only overwrite description if it's the placeholder
                if entry.get("description") == "pending-merge":
                    entry["description"] = commit_details["subject"]

                if "staging_key" in entry and entry["staging_key"]:
                    staging_key = entry.pop("staging_key")
                    final_key = entry["r2_object_key"]
                    print(f"Publishing: {dataset['fileName']} v{entry['version']}")
                    print(f"  Description: {entry['description']}")
                    try:
                        copy_source: Any = {
                            "Bucket": STAGING_BUCKET,
                            "Key": staging_key,
                        }
                        client.copy_object(
                            CopySource=copy_source, Bucket=PROD_BUCKET, Key=final_key
                        )
                        print("  ✅ Server-side copy successful.")
                        client.delete_object(Bucket=STAGING_BUCKET, Key=staging_key)
                        print("  ✅ Staging object deleted.")
                    except ClientError as e:
                        print(f"  ❌ ERROR: Could not process object. Reason: {e}")
                        exit(1)
                else:
                    print(
                        f"Finalizing rollback: {dataset['fileName']} v{entry['version']}"
                    )
                    print(f"  Description: {entry['description']}")

                dataset["history"][i] = entry
                finalize_manifest(
                    manifest_data,
                    f"ci: Publish {dataset['fileName']} v{entry['version']}",
                )
                return True  # Process only one publication per run

    print("No pending publications found.")
    return False


def main():
    """Main execution block."""
    print("Starting dataset publish/cleanup process...")
    with open(MANIFEST_FILE) as f:
        manifest_data = json.load(f)

    # Prioritize deletions. If any are found, the script will exit after handling them.
    deletions_processed = handle_deletions(manifest_data)
    if deletions_processed:
        print("\nDeletions were processed. Exiting to allow for a clean next run.")
        return

    # If no deletions, check for publications.
    handle_publications(manifest_data)
    print("\nProcess complete.")


if __name__ == "__main__":
    main()
