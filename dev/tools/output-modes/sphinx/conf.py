"""Minimal Sphinx project for the greater_tables output-mode probe.

The only extension that matters is the IPython directive: it is what the
aggregate RTD docs use for every executable block, and the open question is
whether it can surface anything richer than plain text.
"""

project = 'gt-modes'
author = 'probe'
extensions = ['IPython.sphinxext.ipython_directive']
exclude_patterns = ['_build']

# Let a failing block report its traceback into the page rather than aborting
# the build. A probe wants the evidence, not a clean exit.
ipython_warning_is_error = False

html_theme = 'basic'

# One LaTeX document, so the artifact path is predictable for the scanner.
latex_documents = [('index', 'probe.tex', 'GT mode probe', 'probe', 'howto')]
