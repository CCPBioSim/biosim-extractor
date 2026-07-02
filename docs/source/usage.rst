Usage
=====

Command Line
------------

The ``biosim-extractor`` CLI supports both local schema files and auto-fetched schema bundles.

Basic log-file extraction:

.. code-block:: bash

   biosim-extractor mappings.json --engine gromacs --logfile md.log --output metadata.json

The mappings.json file used is created from ``biosim-schema`` `here <https://github.com/CCPBioSim/biosim-schema/blob/main/project/schema_enginemappings.json>`_.

Using an explicit biosim schema file for validation:

.. code-block:: bash

   biosim-extractor mappings.json \
     --biosimschema biosim_schema.yaml \
     --engine amber \
     --logfile md.log \
     --output metadata.json

Using fetched schema bundle (no local schema paths required):

.. code-block:: bash

   biosim-extractor \
     --schema-version latest \
     --schema-cache-dir /tmp/biosim-schema-cache \
     --engine gromacs \
     --logfile md.log

Force refresh of cached schema bundle:

.. code-block:: bash

   biosim-extractor --update-schema --engine gromacs --logfile md.log

Topology/trajectory mode via ``biosim-extractor``:

.. code-block:: bash

   biosim-extractor mappings.json --top topology.top --traj traj1.xtc traj2.xtc --output metadata.json

Control file metadata inclusion:

.. code-block:: bash

   biosim-extractor mappings.json --engine gromacs --logfile md.log --no-file-metadata
   biosim-extractor mappings.json --engine gromacs --logfile md.log --file-metadata

Other available options:

- ``--config``: path to configuration file.
- ``-o, --output``: output file path (prints to stdout when omitted).

Toptraj standalone parser:

.. code-block:: bash

   python -m biosim_extractor.mdanalysis.toptraj topology.top trajectory.xtc --output toptraj.json

Python API
----------

You can also use the API directly in your own scripts.

Log-file mode (Amber/GROMACS):

.. code-block:: python

   from biosim_extractor.metadata.populatemetadata import MetadataPopulator

   populator = MetadataPopulator(
       schema_path="mappings.json",
       log_file="md.log",
       engine="gromacs",
       store_file_metadata=True,  # set False to skip file hash/size collection
   )

   metadata = populator.populate()
   populator.validate(metadata, biosimschema_path="biosim_schema.yaml")
   print(metadata)

Topology/trajectory mode:

.. code-block:: python

   from biosim_extractor.metadata.populatemetadata import MetadataPopulator

   populator = MetadataPopulator(
       schema_path="mappings.json",
       top_file="topology.top",
       traj_file=["traj1.xtc", "traj2.xtc"],
       store_file_metadata=False,
   )

   metadata = populator.populate()
   print(metadata)
