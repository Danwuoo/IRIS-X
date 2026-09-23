# 4B compatibility pilot 002 repair attempt

Status: **one push rejected by Kaggle HTTP 400; Decision 0022 consumed**.

The completed `nvarc-4b-compat-pilot-001` kernel had an empty
`competition_sources` list and failed its GPU gate before model loading. The
retained output does not identify the observed GPU count, type or memory, so
the missing competition mount is an observed configuration difference, not a
proven cause of that failure. Earlier successful Trial 002 smoke 002 and
prompt-pilot baseline 002 notebooks mounted
`arc-prize-2026-arc-agi-2` and recorded a separate PyTorch/`nvidia-smi`
hardware inventory before model work. Trial 002 smoke 001 also had an empty
competition source and reported only two GPUs; its replacement mounted the
competition and verified four L4s. These precedents motivate the draft.

The proposed **new** identity is `nvarc-4b-compat-pilot-002`. It reuses the
same pinned private model Dataset v2 and synthetic-only two-step LoRA workload
as pilot 001. Its metadata requests `NvidiaL4`, is private and Internet
disabled, and includes exactly `arc-prize-2026-arc-agi-2` in
`competition_sources`. The notebook resolves only the official current or
legacy challenge mount path, checks that
`arc-agi_training_challenges.json` exists, and does not open its contents or
any competition solution file. It records PyTorch GPU names, memory and UUIDs
plus `nvidia-smi` rows before dependency installation. The runner independently
records the same hardware inventory in its atomic ledger and result before
hashing model material; a hardware failure therefore reports the observed
condition. It still uses only device 0 and requires an L4 with at least
22,000 MiB. This draft changes neither solver data nor training/generation
ceilings: at most two LoRA steps, 128 synthetic tokens and zero generations.

The [draft plan](configs/draft-4b-pilot-002.json) has `approved: false` and a
`DRAFT-DO-NOT-PUSH/` kernel ID. Offline staging uses
`tools/stage_nvarc_4b_pilot_002.py` and embeds a notebook that refuses all
provider work without Decision 0022 authorization bound to the exact
draft SHA-256, new run ID and proposed final kernel ID. The prepared package
is local only. The final review stage under
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-002-review-002/` records draft-plan
SHA-256 `a2396c1ea45a783477353c088bad7dc8153a4edb93ee2c80418f4437adf7d7bb`,
wheel SHA-256 `17663445b53dba8b3ce78a517fa0252c9340d4423999d10c9356e4d772f8ce97`,
notebook SHA-256 `f476eb311c50978e1fe0ab07c0921a4de983f6553a7964016660cff23571a13d`,
and metadata SHA-256 `597f5125819c823084ec5c703ac4c16b29a8a1865fed8a7c40d9dc231bd7270c`.
Decision 0022 supplied the distinct owner authorization for one private push,
bounded status checks and one terminal retrieval under the stated resource,
stop and retention bounds. The draft remains unapproved; the exact approved
stage was retained locally. Pilot 001's submitted bytes and result remain
frozen.

## Attempted launch and terminal disposition

The approved stage in
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-launch-002/package/` passed local
static checks. It bound the official competition source, existing private
model Dataset, private/Internet-disabled `NvidiaL4` request, unchanged
synthetic workload and zero-generation ceiling. Its approved plan SHA-256 was
`0da977237686f1f0aec82a503a8fd366f471ea2210b4b42faeb91095a54b0955`,
wheel SHA-256 `17663445b53dba8b3ce78a517fa0252c9340d4423999d10c9356e4d772f8ce97`,
notebook SHA-256 `a63fc1f3f004d122660b797da09487e446983961f45e820c37985b8ce6e3a0c8`,
and metadata SHA-256 `8dc72fbb869d56b2cb6c8d5c21a6d1941ff88b7bbf6ee8216d424918f77cfa91`.
The local launch ledger reserved one push before the CLI call.

The single `kaggle kernels push` call with `--accelerator NvidiaL4 --timeout
1800` returned `400 Client Error: Bad Request` from `SaveKernel`, without a
more specific server validation message or a kernel/version receipt. One
status check could not access the intended kernel; a read-only list of the
ten newest own kernels did not contain pilot 002. These observations do not
prove which metadata field the server rejected. The proposed kernel slug has
54 characters, versus 50 in the accepted pilot 001 slug; a length limit is a
local hypothesis, not a diagnosed provider error. No kernel execution or
hardware preflight is evidenced, and no output retrieval was attempted. The
one push allowance is consumed. The unused retrieval does not authorize a
second push. The exact local ledger is at
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-launch-002/launch-ledger.json`.
