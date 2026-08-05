greater_tables output-mode probe: Sphinx
========================================

Five blocks. A prints a string to stdout, which is the path ``qd`` takes
today. B and C hand the display machinery a real GT object. D and E hand it a
shim advertising a chosen mimebundle, to establish what the consumer would do
if ``text/plain`` were on offer.

Setup
-----

.. ipython:: python

    from fixture import table, Bundle
    from IPython.display import display

A. print path: a string on stdout
---------------------------------

.. ipython:: python

    print(table('A print').text)

B. display path: bare expression
--------------------------------

.. ipython:: python

    table('B expr')

C. display path: explicit display()
-----------------------------------

.. ipython:: python

    display(table('C display'))

D. shim: text/plain only
------------------------

.. ipython:: python

    display(Bundle('D plain', ['text/plain']))

E. shim: text/html plus text/plain
----------------------------------

.. ipython:: python

    display(Bundle('E both', ['text/html', 'text/plain']))
