
.. contents:: Quick navigation
   :depth: 2


Impute2 Merger - Options and Parameters
========================================


General options
----------------

.. table::

    +-----------------------+-------------------------------------------------+
    | Option                | Description                                     |
    +=======================+=================================================+
    | ``-h``, ``--help``    | Show this help message and exit.                |
    +-----------------------+-------------------------------------------------+
    | ``-v``, ``--version`` | Show program's version number and exit.         |
    +-----------------------+-------------------------------------------------+
    | ``--debug``           | Set the logging level to debug.                 |
    +-----------------------+-------------------------------------------------+


Input files
------------

.. table::

    +-------------------------------+-----------------------------------------+
    | Option                        | Description                             |
    +===============================+=========================================+
    | ``--impute2 FILE [FILE ...]`` | The output from IMPUTE2.                |
    +--------------------+----------------------------------------------------+


Options
--------

.. table::

    +-------------------------+-----------------------------------------------+
    | Option                  | Description                                   |
    +=========================+===============================================+
    | ``--chr CHR``           | The chromosome on witch the imputation was    |
    |                         | made.                                         |
    +-------------------------+-----------------------------------------------+
    | ``--probability FLOAT`` | The probability threshold for no calls.       |
    |                         | [``<0.9``]                                    |
    +-------------------------+-----------------------------------------------+
    | ``--completion FLOAT``  | The completion rate threshold for site        |
    |                         | exclusion. [``<0.98``]                        |
    +-------------------------+-----------------------------------------------+
    | ``--info FLOAT``        | The measure of the observed statistical       |
    |                         | information associated with the allele        |
    |                         | frequency estimate threshold for site         |
    |                         | exclusion. [``<0.00``]                        |
    +-------------------------+-----------------------------------------------+


Output files
-------------

.. table::

    +-------------------+-----------------------------------------------------+
    | Option            | Description                                         |
    +===================+=====================================================+
    | ``--prefix FILE`` | The prefix for the output files. [``imputed``]      |
    +-------------------+-----------------------------------------------------+

