# Active Tools

`repository_check.py` performs deterministic offline checks of the active P1
layout, product authority and policy set, forbidden runtime integrations,
archive catalog, Git recovery, and archive separation. It permits authorized
files within the governed top-level layout rather than relying on the former P0
exact-file allowlist.

`irisx_build_backend.py` is the dependency-free PEP 517/660 backend used for
offline editable installs and pure-Python wheels. It is intentionally limited to
the single `src/irisx` package and the declared `irisx` console entry point.

Historical tools are recoverable from the cold-archive tag and are not active
commands.
