"""Configuration file for the Sphinx documentation builder.

Mirrors the greater_tables 5.x docs setup (Read the Docs theme, autodoc,
copy button, bibliography-free) minus the extensions that have since been
deprecated upstream. Requires the package to be installed — Read the Docs
does that via ``.readthedocs.yaml``; locally use ``uv sync --extra docs``.
"""

import greater_tables as gt

# -- Project information -----------------------------------------------------

project = 'greater_tables'
copyright = '2025-2026, Stephen J Mildenhall'
author = 'Stephen J Mildenhall'
release = gt.__version__
version = gt.__version__

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',            # numpy-style docstrings
    'sphinx.ext.viewcode',
    'sphinx.ext.mathjax',
    'sphinx.ext.intersphinx',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.githubpages',
    'sphinx_copybutton',
    'myst_parser',                    # CHANGELOG.md include
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
master_doc = 'index'
pygments_style = 'sphinx'

# section labels are page-scoped; the included CHANGELOG repeats
# Added/Changed/Fixed under every release, so its duplicates are expected
# (autosectionlabel_maxdepth trips a Sphinx bug on myst-included files)
autosectionlabel_prefix_document = True
suppress_warnings = ['autosectionlabel.versions']

autodoc_member_order = 'bysource'
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
}

napoleon_google_docstring = False
napoleon_numpy_docstring = True

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'pandas': ('https://pandas.pydata.org/docs', None),
    'numpy': ('https://numpy.org/doc/stable', None),
}

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'logo_only': False,
    'prev_next_buttons_location': 'both',
    'style_external_links': False,
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 3,
    'includehidden': True,
    'titles_only': False,
}
html_logo = '_static/greater-tables-logo.png'
html_favicon = '_static/favicon.ico'
html_static_path = ['_static']
