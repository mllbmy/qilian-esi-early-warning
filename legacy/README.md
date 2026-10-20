# Legacy Chinese-manuscript validators

`verify_v8.py`, `verify_v9.py` and `verify_v10.py` are the self-check scripts of the
earlier **Chinese** manuscript rounds. They are kept for provenance only.

Why they are not in the reproduction package:

- they assert against Chinese Word files and Chinese table layouts that no longer exist;
- `verify_v8.py` contains the public GitHub URL of this repository, so shipping it with a
  double-blind package would expose the account name (see 踩坑库 07-04).

They are not imported by any 2.2 code path. `verify_v10` calls `verify_v9`, which calls
`verify_v8`, so all three stay together in this directory.
