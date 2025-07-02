import os
import json
import subprocess
import boto3
from botocore.exceptions import ClientError

# Load config from environment
ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
PROD_BUCKET = os.environ["R2_PRODUCTION_BUCKET"]
STAGING_BUCKET = os.environ["R2_STAGING_BUCKET"]
ENDPOINT_URL = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
MANIFEST_FILE = "manifest.json"

print("Starting dataset publish process...")

client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
)

with open(MANIFEST_FILE, "r") as f:
    manifest_data = json.load(f)

needs_update = False
for dataset in manifest_data:
    for i, entry in enumerate(dataset["history"]):
        # Find the entry that was just merged
        if entry.get("commit") == "pending-merge":
            needs_update = True

            # --- Get commit details from Git ---
            # Get the hash of the merge commit
            commit_hash = (
                subprocess.check_output(
                    ["git", "log", "-1", "--pretty=%h", "--", MANIFEST_FILE]
                )
                .decode()
                .strip()
            )
            # Get the subject line (title) of the merge commit
            commit_subject = (
                subprocess.check_output(
                    ["git", "log", "-1", "--pretty=%s", "--", MANIFEST_FILE]
                )
                .decode()
                .strip()
            )

            entry["commit"] = commit_hash
            entry["description"] = commit_subject  # Set the description
            # --- End of Git details ---

            # If it was a staged file, process it. Otherwise, it was a rollback.
            if "staging_key" in entry and entry["staging_key"]:
                staging_key = entry.pop("staging_key")
                final_key = entry["r2_object_key"]
                print(f"Publishing: {dataset['fileName']} v{entry['version']}")
                print(f"  Description: {commit_subject}")
                try:
                    copy_source = {"Bucket": STAGING_BUCKET, "Key": staging_key}
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
                print(f"Finalizing rollback: {dataset['fileName']} v{entry['version']}")
                print(f"  Description: {entry['description']}")

            dataset["history"][i] = entry
            break  # Process one entry per dataset per run

    if needs_update:
        break  # Process one dataset per run

if needs_update:
    print("\nFinalizing manifest file with new commit details...")
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add a trailing newline for linters

    print("Committing and pushing finalized manifest...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"])
    subprocess.run(
        ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"]
    )
    subprocess.run(["git", "add", MANIFEST_FILE])
    subprocess.run(["git", "commit", "-m", "ci: Finalize manifest after publish"])
    subprocess.run(["git", "push"])
    print("✅ Manifest finalized.")
else:
    print("No staged datasets found to publish.")

print("\nPublish process complete.")
