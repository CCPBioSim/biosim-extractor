Usage
=====

Command Line
------------

To extract metadata from a log file:

.. code-block:: bash

   biosim-extractor <schema.json> --engine gromacs --logfile md.log --output metadata.json

To extract topology and trajectory metadata:

.. code-block:: bash

   python -m biosim_extractor.mdanalysis.toptraj topology.top trajectory.xtc

Python API
----------

You can also use the API in your own scripts:

.. code-block:: python

   from biosim_extractor.schema.populatemetadata import MetadataPopulator

   populator = MetadataPopulator(
       schema_path="schema.json",
       log_file="md.log",
       engine="gromacs"
   )
   metadata = populator.populate()
   print(metadata)