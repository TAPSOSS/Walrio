# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add the project root to the Python path so autodoc can find the modules
sys.path.insert(0, os.path.abspath('../../'))
sys.path.insert(0, os.path.abspath('../../modules'))
sys.path.insert(0, os.path.abspath('../../modules/libraries'))
sys.path.insert(0, os.path.abspath('../../modules/addons'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Walrio'
copyright = '2024, Walrio Contributors'
author = 'Walrio Contributors'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '1.0'
# The full version, including alpha/beta/rc tags.
release = '1.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.mathjax',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx.ext.napoleon',  # For Google/NumPy style docstrings
]

templates_path = ['_templates']
exclude_patterns = []

# The master toctree document.
master_doc = 'index'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# -- Extension configuration -------------------------------------------------

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
}

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for autodoc extension -------------------------------------------

# This value selects what content will be inserted into the main body of an autoclass directive.
autoclass_content = 'both'

# This value selects if automatically documented members are sorted alphabetical (value 'alphabetical'), 
# by member type (value 'groupwise') or by source order (value 'bysource').
autodoc_member_order = 'bysource'

# Automatically generate stub files for autosummary
autosummary_generate = True

# Include private members (starting with _) in documentation
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'special-members': '__init__',
    'exclude-members': '__weakref__'
}

# Mock imports for external dependencies that might not be available during doc build
autodoc_mock_imports = ['mutagen', 'sqlite3']

# -- Options for napoleon extension ------------------------------------------

# Enable parsing of Google style docstrings
napoleon_google_docstring = True
# Enable parsing of NumPy style docstrings  
napoleon_numpy_docstring = True
# Include __init__ docstrings in class documentation
napoleon_include_init_with_doc = False
# Include private members in documentation
napoleon_include_private_with_doc = False
# Use admonitions for sections like Note, Warning, etc.
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
# Use :param: directive instead of parameter lists
napoleon_use_param = True
# Use :rtype: directive for return types
napoleon_use_rtype = True
