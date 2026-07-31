greater_tables
==============

|image1| |image2| |image3|

**Greater Tables** produces high-quality static display tables — for journal
articles, books, formal reports, and printed financial statements. A pandas
DataFrame (or CSV, or markdown table) goes in; a clean, typographically sound
table comes out in HTML, LaTeX (via TikZ), or plain text. No sparklines, no
color, no shading: just your data, rendered cleanly.

.. code:: python

   from greater_tables import GT
   GT(df)

This documentation covers **GT2**, the ground-up rewrite that publishes as
``greater-tables`` 6.0. Between the DataFrame and the page sits a versioned,
JSON-serializable **table document** — the IR. Python owns *semantics*
(dtypes, format inference, multi-index hierarchy, spans, break depths); each
renderer owns *geometry and style*. Nothing in the IR names a width, a rule
weight, a font, or a CSS property, so the HTML renderer, the TikZ renderer,
the text oracle, and the bundled JavaScript walker all draw the same table —
and are conformance tested against each other.

Designed for **JupyterLab**, **Quarto**, and scripting: the output format is
auto-detected. Display tables are small and focused — the end result of your
analysis, after selecting rows and columns, ordering, and labeling. Greater
Tables gets those raw materials onto the page, cleanly and consistently.

Also included: **Fabricator**, a flexible test DataFrame generator — specify
row count, index and column hierarchies, data types, missing values, and more.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   design
   ir
   migration
   api
   versions

Installation
------------

.. code:: bash

   pip install greater-tables

6.0 is not on PyPI yet — until it is, ``pip install greater-tables`` gives you
the frozen 5.3 engine. Install this rewrite from source
(``pip install git+https://github.com/mynl/greatest_tables``), and pin
``greater-tables<6`` anywhere you want to stay on 5.x. The import name never
changes: ``from greater_tables import GT`` works on both.

Source
------

`GitHub <https://github.com/mynl/greatest_tables>`__. The repo keeps the
development codename ``greatest-tables``; the package it publishes is
``greater-tables``. greater_tables 5.x stays pinnable on PyPI forever, with
its source and issue archive at
`mynl/greater_tables_project <https://github.com/mynl/greater_tables_project>`__.

Licence
-------

MIT.

The Name
--------

Obviously, the name is a play on the ``great_tables`` package. I have been
maintaining a set of macros called
`GREATools <https://www.mynl.com/old/GREAT/home.html>`__ (generalized,
reusable, extensible actuarial tools) in VBA and Python since the late 1990s,
and call all my macro packages *GREAT*. The rewrite was codenamed *greatest*
while it grew up next to its parent; the repo kept the codename, the package
did not.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |image1| image:: https://img.shields.io/github/commit-activity/y/mynl/greatest_tables
.. |image2| image:: https://img.shields.io/pypi/v/greater-tables
.. |image3| image:: https://img.shields.io/readthedocs/greater-tables
