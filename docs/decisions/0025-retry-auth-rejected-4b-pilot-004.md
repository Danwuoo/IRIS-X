# Decision 0025: Retry the authentication-rejected pilot 004 transport once

Status: Accepted

Date: 2026-09-24

## Context

Decision 0024 authorized one exact pilot 004 submission. Its `SaveKernel`
request returned HTTP 401 before a kernel/version receipt. The local OAuth
access token had expired at `2026-09-23T16:00:14Z`, seven minutes before the
request. A Kaggle status request could not access the intended kernel while
the token was expired. After refreshing the existing credential, a successful
read of the owner's ten newest kernels showed no pilot 004 entry. There is no
evidence of notebook execution, model loading, training or generation.

The owner previously directed that a submission rejected before any run be
retried because it cannot affect a model result. That instruction persists.
This case is a local authentication failure, rather than a Kaggle payload
validation failure. The exact package can be sent once after credential
refresh without changing the run or kernel identity.

## Decision

Authorize one additional `SaveKernel` call for the unchanged approved
`nvarc-4b-compat-pilot-004` package and kernel ID
`danielwuu/iris-x-4b-lora-pilot-004`. Bind its draft-plan SHA-256
`57f581383f96661fc980a15e5a877654c8f324e6ddeb00da9865c1c907d024cd`
and approved plan, wheel, notebook and metadata SHA-256 values
`cca98adaab611c2eff11f099b875785fe9d4b64443d4bbeb27ba6533fdf5ef46`,
`70241f00764bad3849a29aae20dbde7d6e20657c76ebca6f374c0f279c8f6e22`,
`08627fa4ba2cbaff101bb6fb7ed4f0d4c5af291f1b88685dca69d61513886ea9`,
and `b4907d434348128fe0db9f495963e0ef5b8fb88ea6c5a099db4480c462e8b013`.
Atomically reserve this transport retry in a separate local ledger before the
call. If accepted, make bounded status checks to terminal and one terminal
retrieval with UTF-8 local CLI output. If rejected again, stop; no third call.

All Decision 0024 notebook, model, data, privacy, Internet, hardware, time,
USD 0, two-step, 128-token and zero-generation limits stay unchanged. No
Dataset update, package mutation, model retry, ARC scoring, competition
submission or publication is authorized. The first 401 request remains
retained evidence and is not recast as a successful execution.
