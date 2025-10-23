GTFS JP Kit
***********

.. image:: https://github.com/mrcagney/gtfs_kit/actions/workflows/test.yml/badge.svg

**GTFS JP Kit** is a fork of `GTFS Kit <https://github.com/mrcagney/gtfs_kit>`_ by Alex Raichev.  
GTFS JP Kit is a Python 3.10+ library for analyzing `General Transit Feed Specification (GTFS) <https://en.wikipedia.org/wiki/GTFS>`_ data in memory without a database.  
It adapts and extends the original library to support the GTFS JP transit data specification and related workflows, as defined by `MLIT <https://www.mlit.go.jp/sogoseisaku/transport/content/001419163.pdf#page=7>`_.

The original GTFS Kit (© Alex Raichev, 2019–present) is licensed under the MIT License.  
This project remains under the same license.

It uses Pandas and GeoPandas to do the heavy lifting.

Installation
============

Install it from PyPI with UV, for example:

.. code-block:: bash

   uv add gtfs_jp_kit

Examples
========

Examples can be found in the Marimo notebook ``notebooks/examples.py``.

Install dependencies and run the notebook as follows from the project root:

.. code-block:: bash

   uv sync
   uv run --no-project marimo run notebooks/examples.py

Note that the notebook uses ``japan_data`` rather than ``data``.

Authors
=======

- Kushal Chattopadhyay (2025-10), editor  
- Alex Raichev (2019-09), maintainer

Documentation
=============

The documentation is built via Sphinx from the source code in the ``docs`` directory, then published to GitHub Pages at  
`mrcagney.github.io/gtfs_kit_docs <https://mrcagney.github.io/gtfs_kit_docs>`_.

**Note to the maintainer:**  
To update the docs, run:

.. code-block:: bash

   uv run publish-sphinx-docs

Then push to the docs remote:

.. code-block:: bash

   git push git@github.com:mrcagney/gtfs_kit_docs
