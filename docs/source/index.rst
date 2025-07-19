.. OEO Data Management documentation master file, created by
   sphinx-quickstart on Wed Jul  9 16:27:43 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

OEO Data Management
___________________

.. image:: https://codecov.io/gh/TemoaProject/data/graph/badge.svg?token=I7IU95ZY51
   :target: https://codecov.io/gh/TemoaProject/data
   :alt: codecov

.. image:: https://results.pre-commit.ci/badge/github/TemoaProject/data/main.svg
   :target: https://results.pre-commit.ci/latest/github/TemoaProject/data/main
   :alt: pre-commit.ci status

.. image:: https://github.com/TemoaProject/data/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/TemoaProject/data/actions/workflows/ci.yml
   :alt: CI

.. image:: https://github.com/TemoaProject/data/actions/workflows/publish.yml/badge.svg?branch=develop
   :target: https://github.com/TemoaProject/data/actions/workflows/publish.yml
   :alt: Publish Dataset to R2

.. image:: https://github.com/TemoaProject/data/actions/workflows/cleanup.yml/badge.svg
   :target: https://github.com/TemoaProject/data/actions/workflows/cleanup.yml
   :alt: Cleanup Staging Bucket


This is the official repository for versioned input databases used by the Open Energy Outlook (OEO) initiative. It contains a command‐line tool (``datamanager``) designed to manage these Temoa-compatible SQLite databases using a secure, auditable, and CI/CD-driven workflow.

About the Data
--------------

The SQLite databases hosted here are designed to be used as inputs for `Temoa <https://github.com/TemoaProject/temoa>`_, an open-source energy system optimization model.
This data is curated and maintained by the Open Energy Outlook (OEO) team. The goal is to provide a transparent, version-controlled, and publicly accessible set of data for energy systems modeling and analysis.

The Core Concept
----------------

The system works by treating your Git repository as a source of truth for *metadata*. The final publication of data is handled by a trusted, automated GitHub Actions workflow after a Pull Request has been reviewed and merged.

This two-phase process ensures security and consistency:

#. **Prepare Phase (Local):**
   A developer prepares a new data version. The large file is uploaded to a temporary **staging bucket**, and a change to ``manifest.json`` is proposed.
#. **Publish Phase (Automated):**
   After the proposal is approved and merged into the ``main`` branch, a GitHub Action performs a secure, server-side copy from the staging bucket to the final **production bucket**, making the data live.

.. mermaid::

   flowchart TD
     subgraph Developer_Machine["Developer Machine"]
       A["datamanager prepare"]
       B["Staging R2 Bucket"]
       C["New Git Branch"]
       D["GitHub"]
     end
     subgraph GitHub["GitHub"]
       E["Open Pull Request"]
       F["main branch"]
       G["Publish Workflow"]
     end
     subgraph Cloudflare_R2["Cloudflare R2"]
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

Features
--------

- **CI/CD-Driven Publishing:**
  Data publication is transactional and automated via GitHub Actions after a pull request is merged, preventing inconsistent states.
- **Enhanced Security:**
  Production credentials are never stored on developer machines; they are only used by the trusted GitHub Actions runner.
- **Interactive TUI:**
  Run ``datamanager`` with no arguments for a user-friendly, menu-driven interface.
- **Data Lifecycle Management:**
  A full suite of commands for rollback, deletion, and pruning, all gated by the same secure PR workflow.
- **Integrity Verification:**
  All downloaded files are automatically checked against their SHA256 hash from the manifest.
- **Credential Verification:**
  A detailed verify command reports read/write/delete permissions for both production and staging buckets.

Prerequisites
-------------

- Python 3.12+
- Git
- ``sqlite3`` command-line tool
- An active Cloudflare account with **two** R2 buckets (one for production, one for staging)
- For the data in this repo, contact the OEO team for access to the R2 buckets.


.. toctree::
   :maxdepth: 1
   :caption: Contents:

   setup
   workflow
   usage
   api/index
