# docs/source/conf.py

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "OEO Data Management"
copyright = "2025, Open Energy Outlook"
author = "Open Energy Outlook"
release = "0.1.0"

extensions = [
    "sphinx.ext.napoleon",  # google / numpy style
    "myst_parser",  # markdown support
    "autoapi.extension",
    "sphinxcontrib.mermaid",
    "sphinx_last_updated_by_git",
]

# Mermaid
mermaid_version = "10.4.0"

# autoapi configuration
autoapi_type = "python"
autoapi_dirs = [os.path.abspath("../../src/datamanager")]
autoapi_root = "api"  # <--- where to write .rst under docs/source/api/
autoapi_options = [
    "members",
    "special-members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]
autoapi_keep_files = True  # keep generated .rst in source tree
autoapi_member_order = "bysource"

templates_path = ["_templates"]
exclude_patterns = []

# HTML
html_theme = "furo"
html_static_path = ["_static", os.path.abspath("../../assets")]

# Favicon
html_favicon = "../../assets/icon.png"
