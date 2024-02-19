Notes on Myopic Tables
======================

MyopicEfficiency
----------------

- Largely similar to baseline Efficiency table
- Built sequentially during myopic run from capacity built or not-built in previous period
  - Note:  Items NOT built in previous myopic windows that do not have a capacity entry are excluded
- Uses base-year field (column) as reference to when added, and ``-1`` indicates original existing capacity
- Adds a computed Lifetime field, which is handy for future computations

MyopicNetCapacity
----------------

- Reflects the current net capacity of a technology by period
- Net capacity = original capacity built net of retirements to date
- Used as existing capacity in follow-on myopic windows
- Includes unlimited capacity technologies with an empty entry in the capacity field

MyopicFlowOut
-------------

- Currently duplicates data from the ``Output_VFlow_Out`` table
  - Note:  Field names are slightly improved over ``Output_VFlow_Out``
- Used as verification, possibly choose one-or-the-other at later date
