# docs/source/conf.py

import os
import sys
from sphinx.ext import apidoc

# 1) make sure your package is on PYTHONPATH
sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------
project = "OEO Data Management"
copyright = "2025, Open Energy Outlook"
author = "Open Energy Outlook"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",  # docstrings → docs
    "sphinx.ext.napoleon",  # google / numpy style
    "myst_parser",  # markdown support
]

templates_path = ["_templates"]
exclude_patterns = []

# -- HTML output -------------------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]


# -- auto‐apidoc hook --------------------------------------------------------
def run_apidoc(app):
    """Automatically run sphinx-apidoc before build."""
    # where to put the generated .rst files
    output_dir = os.path.join(app.srcdir, "datamanager")
    # your actual python package
    module_dir = os.path.abspath(
        os.path.join(app.srcdir, "..", "..", "src", "datamanager")
    )
    apidoc_args = [
        "--force",  # overwrite old files
        "--no-toc",  # no module index in each file
        "--separate",  # one file per module
        "-o",
        output_dir,
        module_dir,
    ]
    apidoc.main(apidoc_args)


def setup(app):
    app.connect("builder-inited", run_apidoc)
