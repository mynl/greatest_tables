API reference
=============

Everything in ``__all__`` is importable from the top-level package:

.. code:: python

   from greater_tables import (
       GT, TableSpec, HouseStyle, build,
       TableDoc, Column, Row, Cell, HeadCell, FormatSpec, IR_VERSION,
       render_html, render_text, render_tikz, Etcher,
       canonical_dict, canonical_json, doc_hash, stamp,
       Fabricator, quick_fab, load_spec,
   )

Package
-------

.. automodule:: greater_tables
   :no-index:

Specification
-------------

.. automodule:: greater_tables.spec

.. automodule:: greater_tables.config

Facade
------

.. automodule:: greater_tables.compat

The IR
------

.. automodule:: greater_tables.ir

Engine
------

.. automodule:: greater_tables.engine.build

.. automodule:: greater_tables.engine.dtypes

.. automodule:: greater_tables.engine.formats

.. automodule:: greater_tables.engine.structure

.. automodule:: greater_tables.engine.hashing

Renderers
---------

.. automodule:: greater_tables.render.html

.. automodule:: greater_tables.render.policy

.. automodule:: greater_tables.render.css

.. automodule:: greater_tables.render.notebook

.. automodule:: greater_tables.render.text

.. automodule:: greater_tables.render.tikz

.. automodule:: greater_tables.render.textlength

.. automodule:: greater_tables.render.etcher

Fixtures
--------

.. automodule:: greater_tables.fabricator
