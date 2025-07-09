# The Data Publishing Workflow

All changes to the data---whether creating, updating, or deleting---follow a strict, safe, and reviewable Git-based workflow.

### Step 1: Create a New Branch

Always start by creating a new branch from the latest version of `main`.

```bash
git checkout main
git pull
git checkout -b feat/update-energy-data
```

### Step 2: Prepare Your Changes

Use the `datamanager` tool to stage your changes. The `prepare` command handles both creating new datasets and updating existing ones.

```bash
uv run datamanager prepare energy-data.sqlite ./local-files/new-energy.sqlite
```

### Step 3: Commit and Push

Commit the modified `manifest.json` file with a descriptive message. This message will become the official description for the new data version.

```bash
git add manifest.json
git commit -m "feat: Add 2025 energy data with new demographic columns"
git push --set-upstream origin feat/update-energy-data
```

### Step 4: Open a Pull Request

Go to GitHub and open a pull request from your feature branch to `main`.

### Step 5: Merge and Automate

Once the PR is reviewed, approved, and all status checks pass, merge it. The CI/CD pipeline takes over automatically, publishing the data to the production bucket and finalizing the manifest.
