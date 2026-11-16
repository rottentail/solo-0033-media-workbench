# Media Workbench product specification

The source-location workflow separates an asset's immutable original content
identity from its movable original path and optional immutable audition proxy.
Proxy preparation reserves publication precedence in a short transaction,
performs FFmpeg and media verification outside the writer lock, then installs
only the current generation's receipt. A previous accepted proxy remains
usable throughout a pending or failed refresh. Publication never rewrites the
original location. Unaccepted proxy files and build directories are removed.

Batch reconnection probes and hashes candidates without a writer transaction,
then checks every location revision and candidate file stamp before updating
any original paths. Wrong bytes and stale requests have no partial batch
effects. Location revisions are independent of timeline edit revisions and
proxy generations. Offline previews may use a receipt-verified proxy; delivery
must resolve and verify the original identity. Pending pre-move jobs and saved
mix plans resolve newly accepted original locations without changing their
frozen editing decisions. Audition proxies preserve duration and timing and
cannot be used as replacement originals. This is local trusted-operator media
management; hostile concurrent file mutation and power-loss durability are
outside its guarantee.

The service lets a trusted media operator assemble an ordered sequence of independently trimmed and weighted video occurrences, export a normalized MP4, and recover an interrupted export without changing its accepted content. The product is an audio/video processing backend with a loopback JSON HTTP interface.

The source asset records the media path, SHA-256 and probed streams. A project owns a revision and ordered clip occurrences; two occurrences can reference the same asset without sharing trim or gain. Atomic whole-timeline replacement requires the expected revision. Appends acquire a short SQLite write transaction so concurrent editors receive distinct positions and revisions. Export submission takes a consistent short read view and saves a separate immutable plan.

The render record is the public result. New records also own a durable job containing destination, cache root, monotonically increasing claim epoch, owner, expiry and optional assembled-artifact intent. Ordered segment checkpoints reference content identities and checksums. States are queued → running → completed/failed/cancelled. An expired running job may be claimed again. A failed job may explicitly return to queued; cancellation and completion are terminal.

Three connected workflows are implemented:

1. Asset intake and timeline editing: HTTP → stream probing and fingerprinting → clip validation and atomic revision change → consistent timeline read. Invalid cuts, missing assets and stale replacements have no partial edit effects.
2. Synchronous media export: HTTP → frozen timeline → occurrence-specific planning → segment normalization/cache → ordered assembly → protected publication and completed result. Encoding runs outside long database transactions so editing can continue.
3. Persistent export recovery: enqueue and persist the plan → acquire/renew an expiring claim → revalidate or rebuild segment checkpoints → assemble and record a durable artifact intent → publish under the current claim. Cancellation invalidates the claim. A new process can take over an expired claim and recognize this job's interrupted link without replacing another writer's file.

Concurrency and recovery rules span distinct owners. SQLite controls claims, revision edits and checkpoints; the cache controls immutable media bytes; publication must reconcile a file link with a database status. Locks on individual cache identities prevent concurrent encoders from exposing incomplete pairs of bytes and metadata. The worker checks its epoch even if its owner name is reused. A stale worker cannot mark failure, publish, renew or overwrite progress for its successor. Each checkpoint is an occurrence position, even when its encoded bytes are shared.

Video is fixed at 640×360, 25 fps and square pixels. Audio is AAC, stereo 48 kHz. No-audio and short-audio inputs are padded to the clip's selected duration; per-occurrence gain is applied before assembly. Source hashes are checked before accepting the plan, before using cached results and after encoding a new segment. Existing target paths are protected through hard-link publication. Failure and cancellation retain any already-published output rather than unlinking a public name that an external writer could replace concurrently. The artifact intent remains inspectable. A failed job can adopt its own verified artifact on explicit retry; cancelled jobs remain terminal. Corrupt published artifacts require operator inspection before retry.

The runtime requires Python 3.10+, POSIX filesystem locks and FFmpeg/FFprobe. Processing is bounded per subprocess, and claim checks can terminate the child. The service does not provide authentication, an autonomous scheduler, automatic retry, cache eviction, arbitrary output codecs or a distributed filesystem protocol. Worker-process interruption is recoverable; hardware/power failure across SQLite and the filesystem is outside the guarantee. Old databases gain only additive tables, and old renders remain readable.

Validation uses generated media, real public HTTP requests, FFprobe, sampled pixels and decoded audio. The production workflow check covers editing/revision rejection, normalized export, expired-claim takeover and cancellation. Automated test files are deliberately deferred to the later task-verification stage; independent baseline fault experiments are retained outside the repository. A baseline with these mechanisms offers more task capacity, but each future difficult Bugfix still requires its own prompt-only review, real healthy/defective probes, narrow repair experiment and source admission.

The independent voice-ducking workflow adds editable positioned voice
occurrences, persisted audition plans and separate WAV export. It measures
post-gain stereo RMS on occurrence-local 20 ms windows, converts those spans
to absolute sample positions, then constructs the lower envelope of linear
attack/release curves with exact intersections. Background ducking is applied
once regardless of the number of simultaneous voices. Each saved plan owns
its selected revision, per-occurrence trims, gains, activity and envelope.

The render resource contract is at most 600 seconds and 16 voices, one decode
per occurrence per export, fixed-size PCM blocks, private temporary disk
storage and a complete-programme peak scan before applying one global scale.
This reconciles bounded RAM with late high peaks and preserved stem balance.
Memory and temporary-file lifetime are production behavior, not task metadata.
Original MP4 rendering, resumable jobs and existing database records remain
compatible through additive tables and separate routes.
