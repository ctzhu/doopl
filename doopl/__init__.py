# --------------------------------------------------------------------------
# Source file provided under Apache License, Version 2.0, January 2004,
# http://www.apache.org/licenses/
# (c) Copyright IBM Corp. 2018
# --------------------------------------------------------------------------

# gendoc: ignore
"""
IBM OPL connector for Python (DOopl)
-------------------------------------

Welcome to the IBM OPL connector for Python.
Licensed under the Apache License v2.0.

With this library, you can quickly and easily add the power of optimization to
your Python application. You can model your problems by using the OPL language and IDE, and integrate it in Python via Python/pandas/sql alchemy inputs/outputs.

Solving with CPLEX requires that IBM ILOG CPLEX Optimization Studio V12.8.0 is installed on your machine.

Install the library
~~~~~~~~~~~~~~~~~~~

::

    pip install doopl


Get the examples
~~~~~~~~~~~~~~~~

* `Examples <https://github.com/IBMDecisionOptimization/doopl-examples>`_.

Get your IBM ILOG CPLEX Optimization Studio edition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- You can get a free `Community Edition <http://www-01.ibm.com/software/websphere/products/optimization/cplex-studio-community-edition>`_
  of CPLEX Optimization Studio, with limited solving capabilities in term of problem size.

- Faculty members, research professionals at accredited institutions can get access to an unlimited version of CPLEX through the
  `IBM Academic Initiative <http://www-304.ibm.com/ibm/university/academic/pub/page/ban_ilog_programming>`_.

License
~~~~~~~

This library is delivered under the  Apache License Version 2.0, January 2004 (see LICENSE.txt).

Starting point
~~~~~~~~~~~~~~

The API is very compact and simple.
You must have the OPL binaries in your PATH/LD_LIBRARY_PATH or
DYLD_LIBRARY_PATH, depending on your platform. They are located in
``<cplex_studio_dir>/opl/bin/<platform>`` where:

   * ``cplex_studio_dir`` is the installation directory of CPLEX 12.8
   * ``platform`` is your plaform (OPL nomenclature, that is ``x64_win64``, ``x86-64_linux`` or ``x86-64_osx``)

Here is small sumup of the capabilities:

   * Inputs can be tuple lists, panda's dataframe, sql alchemy fetch statements.
   * Generate, solve and get output tuplesets as panda's dataframe
   * Get the CPLEX problem statistics and quality metrics for the solution
   * Convert all integer variables to floating point variables and vice-versa.
   * Run the conflict/relaxation mechanism.
   * Call the 'RunSeed' diagnosis for CPLEX/CPO based problems.

Each of these features are demonstrated with simple examples.

Here is a small example to start working with the API::

    from doopl.factory import *

    # Create an OPL model from a .mod file
    with create_opl_model(model="file.mod") as opl:
        # tuple can be a list of tuples, a pandas dataframe...
        opl.set_input("TupleSet1", tuples)

        # Generate the problem and solve it.
        opl.run()

        # Get the names of post processing tables
        print("Table names are: "+ str(opl.output_table_names))

        # Get all the post processing tables as dataframes.
        for name, table in iteritems(opl.report):
            print("Table : " + name)
            for t in table.itertuples(index=False):
                print(t)
"""



from doopl.version import opl_version_major, opl_version_minor, opl_version_micro

# The line that follows is updated at build time, please do not edit !
__version__ = '12.8.0.3' # updated at build time
__version_info__ = __version__.split('.')

__opl_version__ = (opl_version_major, opl_version_minor, opl_version_micro)