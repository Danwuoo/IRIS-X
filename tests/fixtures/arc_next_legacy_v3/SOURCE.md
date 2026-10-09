These fixed UTF-8 fixtures are the exact `NETWORK_GUARD` and `_LAUNCHER` string
bytes from `tools/arc_next_offline_environment.py` at main commit
`077bb4680706b95f196621dab4360ffe03504354`, Git blob
`31a9ca2fb1fe54fdb67e684374ce2b347bc09ed8`.

- `sitecustomize.py.txt`: 1,954 bytes; SHA-256
  `7669d1387b8429bff42428e14c0210960a465c7b7b634b661b1fb62c4cc44f82`.
- `offline-run.py.txt`: 3,050 bytes; SHA-256
  `12dca3a583c059a95db714e53f0d60952bc8e5b35d734cd21182e8487a83931c`.

The trusted legacy command flags were `-I -S`. Tests must not generate these
historical identities from the current installer or guard constants. The tiny
synthetic installation supplies only dynamic paths, interpreter and wheel
evidence. Migration preserves these historical guard and launcher bytes, adds
the digest-bound startup hook, and replaces only its two receipts. New
installations retain the current early bytecode guard and `-I -B -S` flags.
