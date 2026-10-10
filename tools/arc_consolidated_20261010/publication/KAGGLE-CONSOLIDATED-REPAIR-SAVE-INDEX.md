# IRIS-X consolidated tokenizer/output repair: verified Kaggle save

[IRIS-X Consolidated Offline 20261010](https://www.kaggle.com/code/danielwuu/iris-x-consolidated-offline-20261010)

- Existing notebook ID: 138033807
- Kaggle version: 3; predecessor version 2 retained.
- One private QUICK_SAVE update; zero automatic retries or redirect replays.
- Saved defaults: MANUAL_START=False, ENABLE_MODEL=False, PROFILE=SMOKE, RESUME=False.
- Fresh output root: irisx-consolidated-20261010-repair001.
- GPU, TPU and Internet disabled.
- Exact reviewed notebook source and settings verified after provider readback.
- Existing Docker image and ARC3 metadata association preserved; no competition data read or submission.
- The five existing Dataset references remain unchanged; no Dataset upload/version change.
- No model/GPU/training session was requested.

## Exact artifact identity

- Approved notebook SHA-256: eac5ca3e70443e30a6049645256296d06bb9f5d377053dad701fc1aa2b525b36
- Predecessor v2 source SHA-256: 582f1b4e209c8e30f637760f94e334147592426184166c0413cb1d7d6b4ea4cf
- Normalized request SHA-256: 887f13ba2052171c6ddb8bab530a013d9feedc47d294e60cc1d7e3db930af764
- Saved provider source SHA-256: 5db5774b9a8e4a034723c17df2442588143879c38c56643f763d84af49497e99
- Publication receipt SHA-256: c409cbee5da4eb937457b6975e44241501e781c5dc64f4d77faba6a11bbabd08

## Existing Dataset references

- danielwuu/iris-arc-granite42-run003-adapter-20261009/1
- danielwuu/iris-arc-next-cpython312-offline/2
- danielwuu/iris-arc-granite42-8b-offline/2
- danielwuu/iris-arc-next-runtime/8
- danielwuu/iris-arc-next-cu128-cp312-wheels/1

## Use and verification limits

Start with a fresh runtime and the new output root. The repaired source has a new identity; old source-bound ledgers cannot be resumed with it. Previous versions, output evidence and the owner’s failed-v2 configuration snapshot are retained.

This release fixes the tokenizer return contract and bounds the displayed final summary while retaining complete evidence in files. CPU contract/regression/SMOKE checks passed. Actual pinned Granite tokenization, weights and GPU execution remain unverified in this repair.

Exact version-qualified Dataset requests and approved source were verified. Provider metadata returns Dataset identities without version suffixes, so actual live-mounted versions/bytes are not independently established by this save.

The provider reached COMPLETE; logs show nbconvert rendering and no recognized execution markers. The archived output-file listing records the provider response, rather than independently proving no execution. The API has no conditional version-update primitive; fresh predecessor/source/settings preflight and the resulting same-ID v3 readback are the conflict checks.

Demo coverage remains engineering evidence, not a held-out score or N14 promotion.
