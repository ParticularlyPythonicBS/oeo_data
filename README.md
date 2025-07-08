# OEO Data Management

This repository provides a command-line tool (`datamanager`) to manage large, versioned datasets (like SQLite files) using Git for metadata and Cloudflare R2 for object storage.

This approach avoids the pitfalls of storing large binary files directly in Git while still providing a robust, auditable version history for your data assets through a secure, CI/CD-driven workflow.

## The Core Concept

The system works by treating your Git repository as a source of truth for *metadata*. The final publication of data is handled by a trusted, automated GitHub Actions workflow after a Pull Request has been reviewed and merged.

This two-phase process ensures security and consistency:

1. **Prepare Phase (Local):** A developer prepares a new data version. The large file is uploaded to a temporary **staging bucket**, and a change to `manifest.json` is proposed.
2. **Publish Phase (Automated):** After the proposal is approved and merged into the `main` branch, a GitHub Action performs a secure, server-side copy from the staging bucket to the final **production bucket**, making the data live.

```mermaid
---
config:
  layout: elk
  theme: mc
  look: classic
---

flowchart TD
 subgraph Developer_Machine["Developer_Machine"]
        B["Staging R2 Bucket"]
        A["datamanager prepare"]
        C["New Git Branch"]
        D["GitHub"]
  end
 subgraph GitHub["GitHub"]
        E["Open Pull Request"]
        F["main branch"]
        G["Publish Workflow"]
  end
 subgraph Cloudflare_R2["Cloudflare_R2"]
        H["Production R2 Bucket"]
  end
    A -- Upload GBs --> B
    A -- Commit manifest change --> C
    C -- Push Branch --> D
    D --> E
    E -- Review & Merge --> F
    F -- Triggers --> G
    G -- "Server-Side Copy" --> B
    B -- "...to" --> H
    G -- Finalize manifest --> F

```

## Features

- **CI/CD-Driven Publishing:** Data publication is transactional and automated via GitHub Actions after a pull request is merged, preventing inconsistent states.
- **Enhanced Security:** Production credentials are never stored on developer machines; they are only used by the trusted GitHub Actions runner.
- **Interactive TUI:** Run `datamanager` with no arguments for a user-friendly, menu-driven interface.
- **Data Lifecycle Management:** A full suite of commands for rollback, deletion, and pruning, all gated by the same secure PR workflow.
- **Integrity Verification:** All downloaded files are automatically checked against their SHA256 hash from the manifest.
- **Credential Verification:** A detailed verify command reports read/write/delete permissions for both production and staging buckets.

## Prerequisites

- Python 3.12+
- Git
- `sqlite3` command-line tool
- An active Cloudflare account with **two** R2 buckets (one for production, one for staging).
- For the data in this repo, contact the OEO team for access to the R2 buckets.

## ⚙️ Setup and Installation

1. **Clone the Repository:**

    ```bash
    git clone git@github.com:ParticularlyPythonicBS/oeo_data.git
    cd oeo_data
    ```

2. **Install Dependencies:**
    This project uses and recommends `uv` for fast and reliable dependency management.

    ```bash
    # Create a virtual environment and install dependencies
    uv venv
    source .venv/bin/activate
    uv pip install -e .
    ```

    The `-e` flag installs the package in "editable" mode, so changes to the source code are immediately reflected.

3. **Configure Environment Variables:**
    The tool is configured using a `.env` file. Create one by copying the example:

    ```bash
    cp .env.example .env
    ```

    Now, edit the `.env` file with your Cloudflare R2 credentials. **This file should be in your `.gitignore` and never committed to the repository.**

    **`.env`**

    ```ini
    # Get these from your Cloudflare R2 dashboard
    R2_ACCOUNT_ID="your_cloudflare_account_id"
    R2_ACCESS_KEY_ID="your_r2_access_key"
    R2_SECRET_ACCESS_KEY="your_r2_secret_key"
    R2_PRODUCTION_BUCKET="your-production-bucket-name"
    R2_STAGING_BUCKET="your-staging-bucket-name"
    ```

4. **Verify Configuration:**
    Run the `verify` command to ensure your credentials and bucket access are correct.

    ```bash
    uv run datamanager verify
    ```

    ![Verify Output](assets/verification.png)

## 🚀 Usage

The primary workflow is now to **prepare** a dataset, then use standard Git practices to propose the change.

### Interactive TUI

For a guided experience, simply run the command with no arguments:

```bash
uv run datamanager
```

This will launch a menu where you can choose your desired action, including the new "Prepare a dataset for release" option.

![TUI](assets/tui.png)

### Command-Line Interface (CLI)

You can also use the command-line interface directly for specific tasks or for scripting purposes.

![CLI](assets/cli.png)

### Core Commands

#### `prepare`

Prepares a dataset for release by uploading it to the staging area and updating the manifest locally. This command intelligently handles both creating new datasets and updating existing ones.

**This is the first step of the new workflow.**

```bash
uv run datamanager prepare <dataset-name.sqlite> <path/to/local/file.sqlite>
```

After running `prepare`, follow the on-screen instructions:

1. `git add manifest.json`
2. `git commit -m "Your descriptive message"`
3. `git push`
4. Open a Pull Request in GitHub.

![prepare](assets/prepare.png)

#### `list-datasets`

Lists all datasets currently tracked in `manifest.json`.

```bash
uv run datamanager list-datasets
```

![list_datasets](assets/list_datasets.png)

#### `pull`

Downloads a dataset from the **production** R2 bucket and verifies its integrity.

```bash
# Pull the latest version
uv run datamanager pull user-profiles.sqlite

# Pull a specific version
uv run datamanager pull user-profiles.sqlite --version v2
```

![pull](assets/pull.png)

### Maintenance Commands

#### `rollback`

Prepares a rollback to a previous stable version by creating a new version entry that points to the old data.

```bash
uv run datamanager rollback <dataset-name.sqlite> --to-version v1
```

#### `delete`

Prepares the **permanent** deletion of an entire dataset and all its versions. Requires strong confirmation.

```bash
uv run datamanager delete <dataset-name.sqlite>
```

#### `prune-versions`

Prepares the permanent deletion of old versions of a dataset, keeping a specified number of recent versions.

```bash
uv run datamanager prune-versions <dataset-name.sqlite> --keep 5
```

#### `verify`

Checks R2 credentials and reports granular read/write/delete permissions for both production and staging buckets.

```bash
uv run datamanager verify
```

## 🧑‍💻 Development and Testing

To contribute to the tool's development:

1. Install development dependencies using `uv pip install -e .[dev]`.
2. Run the test suite using `pytest`:

    ```bash
    uv run pytest
    ```

3. For code quality checks, run `pre-commit`:

    ```bash
    uv run pre-commit run --all-files
    ```
