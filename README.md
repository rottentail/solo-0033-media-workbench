# Media Workbench

A trusted-operator HTTP service for assembling sequential media into normalized MP4s. It supports ordered timeline edits, frozen exports, persistent render jobs, verified segment reuse, cancellation and recovery after a worker process disappears. Video is normalized to 640×360 at 25 fps; audio is stereo 48 kHz. Silent clips receive a bounded silent track. Each occurrence retains its own trim and gain even when the source is reused.

## Runtime

Python 3.10+ on Linux or macOS, SQLite and FFmpeg/FFprobe with libx264/AAC support. The segment cache uses POSIX advisory locks. Set `MEDIA_FFMPEG` and `MEDIA_FFPROBE` to executable paths when needed. Start with `python3 -m mediaworkbench.server`; `MEDIA_PORT` (default 8765) and `MEDIA_DATABASE` (default `media-workbench.sqlite3`) configure the service. Keep it bound to loopback: there is no authentication, and the operator may read and write paths accessible to the process.

Existing databases are extended with job and checkpoint tables on opening. Original assets, projects, clips and render records remain readable. Old renders have no resumable job metadata and are available through the original inspection route.

## Timeline and synchronous export

Send JSON objects to these routes:

- `POST /assets`: `{"path":"/absolute/source.mp4"}` probes the media and records its content hash.
- `POST /projects`: `{"name":"Example"}` creates an empty timeline.
- `POST /clips`: `{"project_id":1,"asset_id":1,"start_ms":0,"end_ms":1000,"gain":0.5}` appends an occurrence and increments the revision.
- `POST /projects/1/timeline`: `{"expected_revision":1,"clips":[{"asset_id":1,"start_ms":1000,"end_ms":2000,"gain":1}]}` atomically replaces and reorders the whole timeline. A stale revision or invalid occurrence rejects the entire edit. Up to 512 occurrences are allowed per replacement.
- `GET /projects/1` returns one consistent timeline view.
- `POST /renders`: `{"project_id":1,"destination":"/absolute/new.mp4"}` executes a complete synchronous export.
- `GET /renders/1` returns the stored revision, frozen plan, status and output/error. New jobs also include lease and segment progress.

Clip endpoints use integer milliseconds. Gain is a finite number from 0 to 2. A source must remain unchanged after intake. Existing destinations, including dangling symlinks, are rejected. Rendering never replaces another writer's destination.

## Persistent jobs

`POST /render-jobs` accepts the same project and destination fields as `/renders` and returns immediately with a queued, immutable plan. Later timeline edits affect future exports only. A worker is explicitly driven with `POST /render-jobs/1/run` and an empty object `{}`. That request runs synchronously, while other HTTP threads may continue editing or inspecting the job. There is no automatic background scheduler.

`GET /render-jobs/1` inspects progress. `POST /render-jobs/1/cancel` with `{}` cancels a queued/running job and invalidates the claim; active FFmpeg processes stop when the worker next checks its lease. `POST /render-jobs/1/retry` with `{}` requeues a failed job using the same frozen plan; a separate `/run` request resumes it. Cancellation is terminal and completed exports cannot be cancelled.

A live claim excludes other workers. Claims expire after 30 seconds without renewal; after a process disappears, another `/run` request may take over the expired claim. Each acquisition increments an epoch. Heartbeats, checkpoints, failure updates and final publication all require the current, unexpired epoch and owner. Source hashing, FFmpeg execution and cache-lock waits renew the lease without holding a long SQLite write transaction.

The default cache is `.media-workbench-cache` next to the database. A segment identity includes source content, trim, gain, audio presence and the encoding profile version. Shared segments have process locks, atomic metadata replacement and byte checksums. Every cache hit and resumed checkpoint is revalidated; corrupt or missing segments are rebuilt. Repeated occurrences may reuse the same encoded bytes but keep separate positions in the plan and concatenation list. Final assemblies retain unique hidden directories beside the destination so an interrupted publication can be recognized by inode ownership and resumed. A competing destination is preserved. Public output paths are never automatically unlinked, because another process may replace the name between an ownership check and deletion. If a process already linked its artifact before a failure or cancellation, those bytes are retained and the job exposes its artifact intent. An explicit retry may adopt a valid own link; cancellation never marks that file completed. A corrupt published artifact requires operator inspection/removal before retry, and another writer's file is never replaced.

Retain the cache alongside the database while jobs may need recovery. There is no cache eviction API, automatic retry loop or power-loss durability guarantee across filesystem and database. Recovery covers worker process interruption; it does not cover storage hardware failure or malicious mutation of database/cache files. Completed MP4s remain valid if the cache is later removed.

## Modules and validation

`timeline` owns atomic edits and revisions; `planner` owns frozen occurrence identities; `jobs` owns durable claims and checkpoints; `segment_cache` owns encoded bytes and manifests; `worker` coordinates recovery; `publication` joins database ownership with destination ownership. `encoder`, `assets`, `tools` and `server` implement media processing, intake, bounded subprocesses and HTTP access.

Automated test files remain deferred to the later task-verification stage. Bounded executable workflow checks are provided in `mediaworkbench.check`:

```sh
python3 -m mediaworkbench.check
python3 -m mediaworkbench.check --workflow timeline
python3 -m mediaworkbench.check --workflow render
python3 -m mediaworkbench.check --workflow recovery
```

They generate temporary media and databases, exercise real production operations and inspect the resulting MP4 with FFprobe. Independent concurrency, corruption and process-interruption verification is kept outside the delivered baseline.

## Voice ducking and saved audio mixes

The audio mix workflow exports a separate stereo 48 kHz, 16-bit WAV from the
project's sequential background timeline and up to 16 positioned voice
occurrences. It does not change the MP4 render-job workflow. Programmes are
limited to 600 seconds and 512 detected audible spans across the voice layer. Background occurrences may be audio-only sources;
MP4 exports retain their existing requirement for video.

- `POST /projects/1/voices`: `{"expected_revision":2,"voices":[{"asset_id":3,"start_ms":200,"end_ms":1800,"at_ms":500,"gain":0.7,"duck_db":-12}]}`
  atomically replaces the voice occurrences and increments the shared project
  revision. Voice sources must contain audio, and edits reject stale revisions.
- `GET /projects/1/audio` returns one consistent background and voice view.
- `POST /mix-plans`: `{"project_id":1,"threshold_db":-38,"attack_ms":40,"release_ms":160}`
  freezes a saved audition plan. Defaults are shown. A 20 ms stereo RMS window
  after occurrence gain identifies audible intervals; silence, muted voices,
  trims and short final windows retain their actual meaning.
- `GET /mix-plans/1` returns the immutable plan, audible spans and piecewise
  linear background-gain envelope. Times in these arrays are 48 kHz sample
  positions. The stored payload checksum is checked on reading.
- `POST /mix-plans/1/render`: `{"destination":"/absolute/new.wav"}` exports
  that saved plan and reports its revision, checksum, peak and whole-programme
  output scale. Later edits do not affect it; changed source bytes are refused.

Each audible span contributes a linear attack, constant duck gain and linear
release. Overlap uses the strongest attenuation, including intersections
between ramps; it never multiplies duck gains. The foreground remains at its
specified relative gains. Mixing sums all active foreground occurrences with
the attenuated background before measuring peak. One scale of at most 1 keeps
the complete programme below 0.98 sample peak, preserving relative loudness
between early and late material without independently normalizing blocks.

Render decodes each occurrence once to private temporary PCM, reads fixed-size
blocks twice (peak scan and output), and deletes temporary files on success or
failure. Its working memory does not grow with programme length; temporary
storage scales with decoded duration and is required. A 300-second programme
is independently checked in an OrbStack container capped at 192 MiB. This is
sample-peak protection, not a broadcast loudness or intersample-peak limiter.
Existing output names and symlinks are preserved. No live audio playback,
background mixing scheduler or network source reader is provided.
