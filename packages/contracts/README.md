# Music Ear contract foundation

This bounded package sits alongside the Ableton producer subsystem. It is not
an upload service, model runtime, or completed Music Ear application.

`music_ear_contracts/schemas/1.0.json` contains Draft 2020-12 definitions for
canonical audio, slices, observations, analysis documents, jobs, runs,
corrections, memory, model and representation revisions, errors, purpose-specific
consent, and evidence-linked narrative claims. These are initial contracts;
version 1.0 is not a production compatibility commitment yet.

```python
from music_ear_contracts import validate
validate("ObservationSet", document)
```

Validation rejects non-finite JSON, invalid score/calibration combinations,
unknown fields, invalid timeline bounds, duplicate event IDs, unsupported
chord/key labels, and inconsistent analysis completion status. It does not
read artifact bytes, prove external observation IDs exist, or enforce tenant
authorization. Those checks belong to subsequent artifact/service integration.

## Audio decision requiring decoder implementation

The initial contract preserves mono or stereo and rejects other channel counts.
PCM is interleaved little-endian float32 at 48 kHz; sample_count counts frames.
Mono analysis uses identity or `(L + R) / 2`. Finite float overrange is retained
and counted, without gain scaling or clipping. This deliberately resolves the
original spec's conflicting no-normalization and [-1,1] requirements in favor
of signal preservation. NaN/Inf must be rejected by the future decoder.
Any resampling requires an immutable revision and explicit compensation count.
Pinned environment metadata records the reproducibility boundary; cross-platform
byte identity is not established until decoder fixtures pass.

## Remaining work

Generated Python/TypeScript types and drift checks; concrete valid fixtures for
every resource; audio decoding and hash verification; durable job transition,
retry and lease behavior; cross-artifact evidence validation; correction and
narrative validators; numeric evaluation gates; authentication and retention
policy. Schema presence alone does not implement those services.

Run `python -m pytest tests/test_music_ear_contracts.py tests/test_dataset_consent.py`.
