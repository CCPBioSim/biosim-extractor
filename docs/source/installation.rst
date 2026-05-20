Installation
============

You can install BioSim Extractor using pip:

.. code-block:: bash

   conda create -n biosim-extractor python=3.12
   conda activate biosim-extractor
   git clone https://github.com/CCPBioSim/biosim-extractor.git
   cd biosim-extractor
   pip install -e .

To install with documentation dependencies::

   pip install ".[docs]"

To install with testing dependencies::

   pip install ".[testing]"
