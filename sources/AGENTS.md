# Sources Boundary

Everything under `sources/` is preserved imported material. Inspect it freely, quote it with its stable registry ID and evidence path, but do not edit, format, refactor, or "clean up" it during ordinary research.

Edit an imported tree only when the user explicitly requires a hygiene or compatibility fix. In that case:

1. state the exact files and reason before editing;
2. keep IRIS-X analysis outside the imported tree;
3. update `corpus/sources.yaml` with a new snapshot-history entry;
4. run `python tools\repository_check.py` and describe the intentional content change.

Do not treat an imported repository's structure, license, or claims as authority over IRIS-X.
