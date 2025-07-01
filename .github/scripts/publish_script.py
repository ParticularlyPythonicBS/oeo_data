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
    latest_entry = dataset["history"][0]
    if "staging_key" in latest_entry and latest_entry["staging_key"]:
        needs_update = True
        staging_key = latest_entry.pop("staging_key")  # Remove the key
        final_key = latest_entry["r2_object_key"]
        commit_hash = (
            subprocess.check_output(
                ["git", "log", "-1", "--pretty=%h", "--", MANIFEST_FILE]
            )
            .decode()
            .strip()
        )
        latest_entry["commit"] = commit_hash

        print(f"Publishing: {dataset['fileName']} v{latest_entry['version']}")
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

if needs_update:
    print("\nFinalizing manifest file with new commit hash...")
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest_data, f, indent=2)

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
